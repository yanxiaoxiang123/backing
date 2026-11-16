"""数据维护 CLI（数据生命周期：清理 / 归档 / 备份）。

用法（在 backend/ 下，conda env 激活后）::

    python maintenance_cli.py jobs --days 30
    python maintenance_cli.py analysis --days 180
    python maintenance_cli.py backtests --days 365
    python maintenance_cli.py archive-klines --before 2015-01-01
    python maintenance_cli.py backup --out /backup/backing-20260814.db
    python maintenance_cli.py all [--archive-klines-before 2015-01-01]

生产环境建议挂 systemd timer 每日执行 ``all``（见
deploy/systemd/stockbacking-maintenance.{service,timer}）。
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from app.logging_config import setup_logging
from app.services import maintenance


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="maintenance_cli",
        description="Backing 数据生命周期维护：清理、归档、备份",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("jobs", help="清理过期任务记录").add_argument(
        "--days", type=int, default=maintenance.DEFAULT_JOB_RETENTION_DAYS
    )
    sub.add_parser("analysis", help="清理过期分析记录").add_argument(
        "--days", type=int, default=maintenance.DEFAULT_ANALYSIS_RETENTION_DAYS
    )
    sub.add_parser("backtests", help="清理过期回测结果").add_argument(
        "--days", type=int, default=maintenance.DEFAULT_BACKTEST_RETENTION_DAYS
    )
    sub.add_parser("alerts", help="清理过期告警记录").add_argument(
        "--days", type=int, default=maintenance.DEFAULT_ALERT_RETENTION_DAYS
    )
    p = sub.add_parser("archive-klines", help="归档指定日期之前的日 K 线")
    p.add_argument("--before", type=date.fromisoformat, required=True)

    p = sub.add_parser("backup", help="备份 SQLite 数据库文件")
    p.add_argument(
        "--out",
        type=Path,
        required=True,
        help="目标文件路径；若为目录则自动命名 backing-YYYYMMDD.db",
    )

    p = sub.add_parser("all", help="按默认保留期执行全部清理")
    p.add_argument(
        "--archive-klines-before",
        type=date.fromisoformat,
        default=None,
        help="可选：同时归档该日期之前的 K 线",
    )

    p_tdx = sub.add_parser("update-mootdx", help="并发测速并自动更新 MOOTDX_SERVERS 服务器列表")
    p_tdx.add_argument("--limit", type=int, default=5, help="保留的最优服务器数量（默认 5）")
    p_tdx.add_argument("--timeout", type=float, default=1.0, help="单服务器探测超时时间（秒，默认 1.0）")
    p_tdx.add_argument("--env-file", type=Path, default=None, help="目标 .env 文件路径（默认自动定位）")
    p_tdx.add_argument("--dry-run", action="store_true", help="仅显示测速结果，不写回 .env 文件")

    return parser


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    setup_logging()

    if args.command == "jobs":
        print({"jobs_purged": maintenance.cleanup_old_jobs(days=args.days)})
    elif args.command == "analysis":
        print({"analysis_purged": maintenance.purge_old_analysis(days=args.days)})
    elif args.command == "backtests":
        print({"backtests_purged": maintenance.purge_old_backtests(days=args.days)})
    elif args.command == "alerts":
        print({"alerts_purged": maintenance.purge_old_alerts(days=args.days)})
    elif args.command == "archive-klines":
        print(maintenance.archive_klines(args.before))
    elif args.command == "backup":
        out = args.out
        # 无扩展名视为目录：自动创建并命名 backing-YYYYMMDD.db
        if out.suffix == "":
            from datetime import datetime, timezone

            out.mkdir(parents=True, exist_ok=True)
            out = out / f"backing-{datetime.now(timezone.utc).strftime('%Y%m%d')}.db"
        print({"backup": str(maintenance.backup_database(out))})
    elif args.command == "all":
        print(maintenance.run_all(archive_klines_before=args.archive_klines_before))
    elif args.command == "update-mootdx":
        res = maintenance.update_mootdx_servers(
            limit=args.limit,
            timeout_s=args.timeout,
            env_file=args.env_file,
            dry_run=args.dry_run,
        )
        print("\n[MOOTDX] 通达信行情服务器测速完成：")
        print("--------------------------------------------------------------------------------")
        print(f"{'排名':<6}{'IP 地址':<18}{'端口':<8}{'延迟':<12}{'有效股票数':<12}{'状态'}")
        print("--------------------------------------------------------------------------------")
        for idx, s in enumerate(res["servers"], 1):
            ip_str = s["host"]
            port_str = str(s["port"])
            lat_str = f"{s['latency_ms']:.1f} ms"
            sec_str = str(s["security_count"])
            print(f"{idx:<6}{ip_str:<18}{port_str:<8}{lat_str:<12}{sec_str:<12}[PASS] 可用")
        print("--------------------------------------------------------------------------------")
        if res.get("dry_run"):
            print("[Dry Run] 未修改配置文件。推荐配置行：")
            server_str = ",".join(f"{s['host']}:{s['port']}" for s in res["servers"])
            print(f"MOOTDX_SERVERS={server_str}\n")
        else:
            print(f"[OK] 已成功更新配置文件：{res['env_file']}")
            print(f"MOOTDX_SERVERS={res['mootdx_servers']}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
