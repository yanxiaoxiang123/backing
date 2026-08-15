#!/usr/bin/env python
"""HTTP 直连探针：验证 DSH 插件将要使用的后端 HTTP 面（任务 11 POC）。

流程：创建 run（inline 同步执行 Supervisor 流水线）→ 拉取 run 记录 →
SSE 回放事件。全部走 X-API-Key 认证，与 DSH 插件直连路径一致。
"""

import argparse
import json
import os
import sys
import time

import requests

DEFAULT_BASE = os.environ.get("QUANT_GATEWAY_BASE", "http://127.0.0.1:8808/api/v1")


def _headers(api_key: str) -> dict:
    return {"X-API-Key": api_key, "Content-Type": "application/json"}


def main() -> int:
    parser = argparse.ArgumentParser(description="量化网关 HTTP 直连探针")
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--api-key", default=os.environ.get("API_KEY", ""))
    parser.add_argument("--objective", default="研究 sh.600000 趋势")
    args = parser.parse_args()

    if not args.api_key:
        print("错误：需要 --api-key 或环境变量 API_KEY", file=sys.stderr)
        return 2

    headers = _headers(args.api_key)

    # 1) 创建 run（inline 同步执行，便于确定性验证）
    resp = requests.post(
        f"{args.base}/agent-runs",
        headers=headers,
        json={"objective": args.objective, "execute_inline": True},
        timeout=120,
    )
    resp.raise_for_status()
    created = resp.json()
    print(f"[1] 创建 run: {created['run_id']} status={created['status']}")

    # 2) run 记录
    run_id = created["run_id"]
    run = requests.get(f"{args.base}/agent-runs/{run_id}", headers=headers, timeout=30)
    run.raise_for_status()
    record = run.json()
    print(f"[2] run 状态: {record['status']} 目标: {record['objective'][:40]}")

    # 3) SSE 回放事件
    print("[3] SSE 事件:")
    with requests.get(
        f"{args.base}/agent-runs/{run_id}/events",
        headers=headers,
        stream=True,
        timeout=60,
    ) as stream:
        step_count = tool_count = 0
        for line in stream.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "{}":
                continue
            event = json.loads(payload)
            if event.get("type") == "step":
                step_count += 1
                print(f"    step seq={event.get('seq')} node={event.get('node')} "
                      f"status={event.get('status')}")
            elif event.get("type") == "tool_call":
                tool_count += 1
                print(f"    tool {event.get('tool')} status={event.get('status')}")
        print(f"    合计: {step_count} 节点事件, {tool_count} 工具事件")

    # 4) 产物
    arts = requests.get(f"{args.base}/agent-runs/{run_id}/artifacts", headers=headers, timeout=30)
    arts.raise_for_status()
    print(f"[4] artifacts: {len(arts.json()['artifacts'])} 条")

    print("探针通过 ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
