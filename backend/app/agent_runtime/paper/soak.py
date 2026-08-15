"""模拟盘 soak 运行器（规格 v2 决策 21；US-3.5）。

后台常驻线程周期性执行撮合循环；循环可重入（订单单次处理、事务原子），
进程被杀/重启后恢复不会重复成交（恢复演练由切片 12 验证）。
"""

from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)


class PaperSoakRunner:
    """后台撮合循环（daemon 线程；间隔可配置）。"""

    def __init__(self, interval_s: float = 60.0, enabled: bool = True):
        self.interval_s = max(interval_s, 1.0)
        self.enabled = enabled
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if not self.enabled or self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="paper-soak", daemon=True
        )
        self._thread.start()
        logger.info("paper soak runner started (interval=%ss)", self.interval_s)

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def _loop(self) -> None:
        from app.agent_runtime.paper.service import run_matching_cycle
        from app.config import SessionLocal

        while not self._stop.wait(self.interval_s):
            try:
                db = SessionLocal()
                try:
                    summary = run_matching_cycle(db)
                    if summary["processed"]:
                        logger.info("paper soak cycle: %s", summary)
                finally:
                    db.close()
            except Exception:
                logger.exception("paper soak cycle failed")
