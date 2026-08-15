"""模拟盘黄金路径 E2E 演示（切片 12；US-3.1..3.4）。

研究 → 策略 → 回测 → paper 提议 → 审批 → 撮合 → 归因 → 告警。
通过 HTTP API 驱动 live 后端（X-API-Key 认证），逐段打印证据。

用法：
    API_KEY=<后端 API_KEY> python scripts/paper_e2e_demo.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ 入路径

BASE = os.environ.get("BACKEND_URL", "http://127.0.0.1:8808/api/v1")
API_KEY = os.environ.get("API_KEY", "")


def _call(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    req = Request(
        f"{BASE}{path}",
        method=method,
        headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
        data=json.dumps(body or {}).encode() if body is not None else None,
    )
    with urlopen(req) as resp:
        return json.loads(resp.read().decode())


def step(title: str, payload: dict[str, Any]) -> None:
    print(f"\n[{title}]")
    print(json.dumps(payload, ensure_ascii=False, indent=1)[:800])


def ensure_next_day_bar() -> str | None:
    """若审批后下一交易日 bar 缺失（周末/同步滞后），注入演示 bar 并返回日期。"""
    from datetime import datetime

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.config import Base, settings
    from app.models.models import DailyKline

    engine = create_engine(settings.DATABASE_URL)
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    try:
        last = (
            db.query(DailyKline)
            .filter(DailyKline.stock_code == "sh.600000")
            .order_by(DailyKline.date.desc())
            .first()
        )
        if last is None:
            return None
        target = last.date + timedelta(days=1)
        if target <= date.today():
            target = date.today() + timedelta(days=1)  # 下一自然日（演示）
        if (
            db.query(DailyKline)
            .filter(DailyKline.stock_code == "sh.600000", DailyKline.date == target)
            .first()
        ):
            return target.isoformat()
        prev_close = float(last.close)
        db.add(
            DailyKline(
                stock_code="sh.600000",
                date=target,
                open=round(prev_close + 0.05, 2),
                high=round(prev_close + 0.4, 2),
                low=round(prev_close - 0.1, 2),
                close=round(prev_close + 0.25, 2),
                volume=120000,
                amount=(prev_close + 0.25) * 120000,
            )
        )
        db.commit()
        return target.isoformat()
    finally:
        db.close()


def main() -> int:
    if not API_KEY:
        print("缺少 API_KEY 环境变量")
        return 2

    step("1. 创建 run（策略 + 回测）", {})
    run = _call(
        "POST",
        "/agent-runs",
        {"objective": "生成 ma_cross 策略并回测验证 sh.600000", "execute_inline": True},
    )
    run_id = run["run_id"]
    step("run 已创建", run)

    detail = _call("GET", f"/agent-runs/{run_id}")
    nodes = {s["node"]: s["status"] for s in detail.get("steps", [])}
    step("2. Supervisor 专家执行", {"nodes": nodes})

    approvals = _call("GET", f"/agent-runs/{run_id}/approvals")["approvals"]
    step("3. 模拟盘订单提议（审批卡）", {"approvals": approvals})
    if not approvals:
        print("无审批卡——组合风控未提议订单")
        return 1
    approval_id = approvals[0]["id"]

    decided = _call(
        "POST",
        f"/agent-runs/{run_id}/approvals/{approval_id}/decide",
        {"decision": "approved", "decided_by": "e2e-demo"},
    )
    step("4. 人工审批（一次性窗口）", decided)

    target = ensure_next_day_bar()
    if target:
        print(f"\n[5. 注入演示 bar {target}（下一交易日；周末/同步滞后演示）]")

    summary = _call("POST", "/paper/match")
    step("5. 撮合循环", summary)

    account = _call("GET", "/paper/account")
    step("6. 账户状态（持仓/现金）", account)

    attribution = _call(
        "GET", f"/paper/attribution?start_date={(date.today() - timedelta(days=30)).isoformat()}&end_date={date.today().isoformat()}"
    )
    step("7. 盘后归因", {k: attribution.get(k) for k in ("alpha", "beta", "cost_drag", "benchmark_available")})

    alerts = _call("POST", "/paper/alerts/check")
    step("8. 告警检查", {"created": len(alerts.get("created", []))})

    events = _call("GET", "/paper/events")
    step(
        "9. 事件（append-only，重放审计输入）",
        {
            "order_events": len(events.get("order_events", [])),
            "cash_events": len(events.get("cash_events", [])),
        },
    )
    print("\nE2E 黄金路径完成 ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
