"""Close-only adapter for the pinned official TimesFM 2.5 PyTorch implementation."""

from pathlib import Path
import sys

CONFIG = {
    "max_context": 512,
    "max_horizon": 128,
    "per_core_batch_size": 1,
    "normalize_inputs": True,
    "use_continuous_quantile_head": False,
    "force_flip_invariance": True,
    "infer_is_positive": True,
    "fix_quantile_crossing": True,
}


class TimesFMAdapter:
    config = CONFIG

    def __init__(self, root: Path, device: str):
        import torch

        sys.path.insert(0, str(root / "vendor/TimesFM/src"))
        from timesfm.configs import ForecastConfig
        from timesfm.timesfm_2p5.timesfm_2p5_torch import TimesFM_2p5_200M_torch

        self.predictor = TimesFM_2p5_200M_torch(torch_compile=False)
        # Upstream defaults to cuda:0 and all visible GPUs. Select before loading.
        self.predictor.model.device = torch.device(device)
        self.predictor.model.device_count = 1
        self.predictor.load_checkpoint(str(root / "models/TimesFM-2.5-200M"), torch_compile=False)
        self.predictor.model.requires_grad_(False).eval()
        self.predictor.compile(ForecastConfig(**CONFIG))

    def predict(self, closes: list[float], horizon: int) -> list[float]:
        import numpy as np

        point, _ = self.predictor.forecast(
            horizon=horizon, inputs=[np.asarray(closes, dtype=np.float32)],
        )
        return np.asarray(point, dtype=float)[0].tolist()
