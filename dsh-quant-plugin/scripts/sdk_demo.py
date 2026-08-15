"""DSH 量化对话外壳演示（切片 11 E2E）。

启动 DeepSeek Harness 运行时（node carrier 或 exe），加载 quant profile，
用自然语言驱动：查 K 线 → 发起分析/回测 run（后端网关执行，工具调用可追溯）。

用法：
    QUANT_API_KEY=<后端 API_KEY> DEEPSEEK_API_KEY=<模型 key> \
        DSH_RUNTIME_MODE=node python scripts/sdk_demo.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PROFILE = _HERE.parent / "cordis" / "quant.cordis.yml"


def main() -> int:
    from deepseek_harness import DeepSeekHarness

    prompts = sys.argv[1:] or [
        "查询 sh.600000 最近 5 个交易日的日 K 线，并说明数据来源。",
        "发起一次完整分析：生成 ma_cross 策略并回测验证 sh.600000，然后总结回测审计结论。",
    ]
    print(f"[quant-shell] profile: {_PROFILE}")
    print(f"[quant-shell] runtime mode: {os.environ.get('DSH_RUNTIME_MODE', 'exe')}")

    with DeepSeekHarness(
        provider="deepseek-official",
        model="deepseek-chat",
        cordis=str(_PROFILE),
    ) as harness:
        for prompt in prompts:
            print(f"\n>>> {prompt}")
            result = harness.run(prompt)
            print("<<<", (getattr(result, "final_response", None) or str(result))[:2000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
