"""
LSTM+FinanceLlama 模型加载器
懒加载模式，避免启动时就加载torch
"""

import os
import sys
import pickle
import builtins as _builtins
import numpy as np
from typing import Any, Optional
import logging
from pathlib import Path
import importlib.util

from app.config import settings

logger = logging.getLogger(__name__)

# 受限反序列化 —— 只允许安全模块，防止 pickle 任意代码执行（B403）
_SAFE_PICKLE_MODULES = frozenset(
    {
        "numpy",
        "numpy._globals",
        "numpy.core",
        "numpy.core.multiarray",
        "numpy.core.numeric",
        "numpy.core.numerictypes",
        "sklearn.preprocessing._data",
        "sklearn.utils._metadata",
    }
)
_SAFE_BUILTINS = frozenset(
    {
        "dict",
        "list",
        "tuple",
        "set",
        "str",
        "int",
        "float",
        "bool",
        "bytes",
        "slice",
        "range",
        "complex",
        "frozenset",
        "type",
        "object",
        "property",
        "staticmethod",
        "classmethod",
        "enumerate",
        "zip",
        "map",
        "filter",
        "reversed",
        "iter",
        "next",
        "len",
        "range",
    }
)


class _RestrictedUnpickler(pickle.Unpickler):
    """限制反序列化到 numpy / sklearn / 安全内置类型"""

    def find_class(self, module, name):
        if module == "builtins":
            if name not in _SAFE_BUILTINS:
                raise pickle.UnpicklingError(f"禁止反序列化 builtins.{name}")
            return getattr(_builtins, name)
        if module not in _SAFE_PICKLE_MODULES:
            raise pickle.UnpicklingError(
                f"禁止反序列化 {module}.{name}，不在安全白名单中"
            )
        return super().find_class(module, name)


def _restricted_load(file) -> Any:
    """使用受限 unpickler 加载 pickle 文件"""
    return _RestrictedUnpickler(file).load()


# 全局变量用于懒加载
_torch = None
_nn = None
_transformers = None
_model = None
_stock_model_class = None


def _get_torch():
    """懒加载 torch"""
    global _torch, _nn
    if _torch is None:
        try:
            import torch

            _torch = torch
            _nn = torch.nn
            logger.info("torch 加载成功")
        except Exception as e:
            error_msg = str(e)
            # 提供更详细的错误诊断信息
            if "DLL" in error_msg or "1114" in error_msg:
                logger.error("=" * 60)
                logger.error("PyTorch DLL 加载失败，常见原因和解决方案:")
                logger.error("1. 缺少 Visual C++ Redistributable")
                logger.error("   解决: 安装 Visual C++ 2015-2022 Redistributable")
                logger.error("2. PyTorch 版本与CUDA版本不匹配")
                logger.error(
                    "   解决: pip install torch --index-url https://download.pytorch.org/whl/cpu"
                )
                logger.error("3. DLL依赖缺失")
                logger.error("   解决: 使用 Dependency Walker 或 pyDependencyView 检查")
                logger.error("4. Anaconda环境冲突")
                logger.error(
                    "   解决: 创建独立的虚拟环境: conda create -n stock_env python=3.10"
                )
                logger.error("=" * 60)
            logger.error(f"torch 加载失败: {e}")
            raise ImportError(f"torch 加载失败: {e}")
    return _torch, _nn


def _get_stock_model_class():
    """Load StockLSTM_FinanceLlama class from models/llm/mg.py."""
    global _stock_model_class
    if _stock_model_class is not None:
        return _stock_model_class

    mg_path = Path(__file__).resolve().parents[3] / "models" / "llm" / "mg.py"
    if not mg_path.exists():
        raise FileNotFoundError(f"未找到训练模型定义文件: {mg_path}")

    if str(mg_path.parent) not in sys.path:
        sys.path.insert(0, str(mg_path.parent))

    spec = importlib.util.spec_from_file_location("dl_mg_runtime", str(mg_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载模块定义: {mg_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "StockLSTM_FinanceLlama"):
        raise ImportError("mg.py 中未找到 StockLSTM_FinanceLlama")

    _stock_model_class = module.StockLSTM_FinanceLlama
    return _stock_model_class


class StockLSTM_FinanceLlama:
    """与训练时相同的模型架构"""

    def __init__(
        self,
        input_size,
        hidden_size,
        output_size,
        num_layers,
        dropout=0.1,
        finance_llama_cache_size=16,
    ):
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.output_size = output_size

        self.finance_llama_cache = {}
        self.finance_llama_cache_order = []
        self.finance_llama_cache_size = finance_llama_cache_size
        self.finance_llama_is_dispatched = False
        # 显式记录目标设备，避免 DataParallel 下 next(self.parameters()).device 不可靠
        self._target_device = None

        # 懒加载
        torch, nn = _get_torch()

        # 加载Finance-Llama模型
        llama_path = settings.DL_LLAMA_PATH
        from transformers import AutoModel, AutoTokenizer, AutoConfig

        revision = "main" if not os.path.isabs(llama_path) else None
        finance_llama_config = AutoConfig.from_pretrained(llama_path, revision=revision)
        model_kwargs = {"config": finance_llama_config}
        if settings.DL_DEVICE.startswith("cuda") and torch.cuda.is_available():
            model_kwargs["torch_dtype"] = torch.float16
            # 不使用 device_map，避免模型分散到多个 GPU
            # 改为加载后手动移动到目标设备
        # 使用 revision 确保固定版本，防止 HuggingFace 供应链风险
        if revision is not None:
            model_kwargs["revision"] = revision
        self.finance_llama = AutoModel.from_pretrained(llama_path, **model_kwargs)
        self.finance_llama_is_dispatched = hasattr(self.finance_llama, "hf_device_map")

        # 强制将 Finance-Llama 移到指定设备（避免 device_map 导致的设备分散）
        if settings.DL_DEVICE.startswith("cuda") and torch.cuda.is_available():
            llama_device = torch.device(settings.DL_DEVICE)
            self.finance_llama = self.finance_llama.to(llama_device)
            self.finance_llama_is_dispatched = False  # 已手动指定设备，禁用 dispatch
            self._target_device = llama_device
            logger.info(f"Finance-Llama 已强制移动到 {llama_device}")
        self.finance_llama_tokenizer = AutoTokenizer.from_pretrained(
            llama_path, revision=revision
        )

        if self.finance_llama_tokenizer.pad_token is None:
            self.finance_llama_tokenizer.pad_token = (
                self.finance_llama_tokenizer.eos_token
            )

        # 冻结Finance-Llama模型
        for param in self.finance_llama.parameters():
            param.requires_grad = False

        # 获取模型隐藏层大小
        if hasattr(self.finance_llama.config, "hidden_size"):
            model_hidden_size = self.finance_llama.config.hidden_size
        elif hasattr(self.finance_llama.config, "n_embd"):
            model_hidden_size = self.finance_llama.config.n_embd
        else:
            model_hidden_size = 768

        self.finance_llama_fc = nn.Linear(model_hidden_size, hidden_size // 2)

        # 网络结构
        self.input_norm = nn.BatchNorm1d(input_size)
        self.input_fc = nn.Linear(input_size, hidden_size // 2)
        self.lstm1 = nn.LSTM(
            input_size=hidden_size,
            hidden_size=hidden_size,
            num_layers=1,
            batch_first=True,
            dropout=0,
        )
        self.lstm2 = nn.LSTM(
            input_size=hidden_size,
            hidden_size=hidden_size,
            num_layers=1,
            batch_first=True,
            dropout=0,
        )
        self.attention = nn.MultiheadAttention(
            hidden_size, num_heads=4, batch_first=True
        )
        self.layer_norm1 = nn.LayerNorm(hidden_size)
        self.layer_norm2 = nn.LayerNorm(hidden_size)
        self.fc1 = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.LeakyReLU(),
            nn.Dropout(dropout),
        )
        self.fc2 = nn.Sequential(
            nn.Linear(hidden_size // 2, hidden_size // 4),
            nn.LeakyReLU(),
            nn.Dropout(dropout / 2),
        )
        self.fc3 = nn.Linear(hidden_size // 4, output_size)

    def clear_finance_llama_cache(self):
        self.finance_llama_cache.clear()
        self.finance_llama_cache_order.clear()

    def _get_finance_llama_input_device(self):
        """获取 finance_llama 所在的实际设备"""
        if self.finance_llama_is_dispatched:
            try:
                return self.finance_llama.get_input_embeddings().weight.device
            except Exception:
                pass
        # 直接使用 finance_llama 的实际设备
        return self.finance_llama.device

    def get_finance_llama_features(self, prompt, device=None):
        torch, _ = _get_torch()

        # 使用显式传入的 device 作为目标设备
        target_device = device if device is not None else self._target_device
        if target_device is None:
            raise ValueError("device must be provided or _target_device must be set")

        if isinstance(prompt, str):
            key = ("STR", prompt)
        elif isinstance(prompt, (list, tuple)):
            key = ("LIST", tuple(prompt))
        else:
            key = ("OTHER", str(prompt))

        # 检查缓存
        if key in self.finance_llama_cache:
            feat = self.finance_llama_cache[key]
            if feat.device != target_device:
                feat = feat.to(target_device)
                self.finance_llama_cache[key] = feat
            return feat

        # 确保 finance_llama 在 target_device 上
        # 同时检查 _target_device 和 finance_llama.device，避免因状态不一致导致设备不匹配
        llama_actual_device = self.finance_llama.device
        if llama_actual_device != target_device:
            self.finance_llama = self.finance_llama.to(target_device)
            llama_actual_device = target_device
            # 同步更新 _target_device
            self._target_device = target_device

        with torch.no_grad():
            if isinstance(prompt, str):
                texts = [prompt]
            else:
                texts = list(prompt)

            encodings = self.finance_llama_tokenizer(
                texts,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=128,
            )
            # input_ids 和 attention_mask 必须在 finance_llama 相同的设备上
            input_ids = encodings.input_ids.to(llama_actual_device)
            attention_mask = (
                encodings.attention_mask.to(llama_actual_device)
                if "attention_mask" in encodings
                else None
            )

            finance_llama_output = self.finance_llama(
                input_ids=input_ids, attention_mask=attention_mask
            )
            last_hidden = finance_llama_output.last_hidden_state[:, -1, :]

            # 确保 finance_llama_fc 在 last_hidden 相同的设备上
            if self.finance_llama_fc.weight.device != last_hidden.device:
                self.finance_llama_fc = self.finance_llama_fc.to(last_hidden.device)

            finance_llama_feature = self.finance_llama_fc(last_hidden)
            finance_llama_feature = finance_llama_feature.detach()

            # 缓存时记录在 target_device 上
            if finance_llama_feature.device != target_device:
                finance_llama_feature = finance_llama_feature.to(target_device)

            self.finance_llama_cache[key] = finance_llama_feature
            self.finance_llama_cache_order.append(key)
            if len(self.finance_llama_cache_order) > self.finance_llama_cache_size:
                oldest = self.finance_llama_cache_order.pop(0)
                try:
                    del self.finance_llama_cache[oldest]
                except KeyError:
                    pass

            return finance_llama_feature

    def forward(self, x, prompt):
        torch, nn = _get_torch()

        batch_size = x.size(0)
        seq_length = x.size(1)
        device = x.device

        # 确保所有模块都在正确的设备上（不依赖不可靠的 device 检查，避免 DataParallel 设备不一致）
        self.input_norm = self.input_norm.to(device)
        self.input_fc = self.input_fc.to(device)
        self.lstm1 = self.lstm1.to(device)
        self.lstm2 = self.lstm2.to(device)
        self.attention = self.attention.to(device)
        self.layer_norm1 = self.layer_norm1.to(device)
        self.layer_norm2 = self.layer_norm2.to(device)
        self.fc1 = self.fc1.to(device)
        self.fc2 = self.fc2.to(device)
        self.fc3 = self.fc3.to(device)
        # 确保 finance_llama_fc 也在正确设备上
        self.finance_llama_fc = self.finance_llama_fc.to(device)

        x_reshaped = x.reshape(-1, x.size(-1))
        x_normalized = self.input_norm(x_reshaped)
        x_normalized = x_normalized.reshape(batch_size, seq_length, -1)
        x_features = self.input_fc(x_normalized)

        # 确保 x_features 和 finance_llama_feat 在同一设备
        finance_llama_feat = self.get_finance_llama_features(prompt, device=device)

        if finance_llama_feat.size(0) == 1:
            finance_llama_features = finance_llama_feat.expand(batch_size, -1)
        elif finance_llama_feat.size(0) == batch_size:
            finance_llama_features = finance_llama_feat
        else:
            p = finance_llama_feat.size(0)
            if p < batch_size:
                reps = (batch_size + p - 1) // p
                finance_llama_features = finance_llama_feat.repeat(reps, 1)[:batch_size]
            else:
                finance_llama_features = finance_llama_feat[:batch_size]

        finance_llama_features = finance_llama_features.unsqueeze(1).expand(
            -1, seq_length, -1
        )
        # 确保拼接前两者在同一设备
        if finance_llama_features.device != x_features.device:
            finance_llama_features = finance_llama_features.to(x_features.device)

        combined_features = torch.cat((x_features, finance_llama_features), dim=2)

        lstm1_out, _ = self.lstm1(combined_features)
        lstm1_out = self.layer_norm1(lstm1_out)
        lstm2_out, _ = self.lstm2(lstm1_out)
        lstm1_out = lstm1_out + lstm2_out  # 残差连接

        lstm1_out = self.layer_norm2(lstm1_out)

        attn_out, _ = self.attention(lstm1_out, lstm1_out, lstm1_out)
        attn_out = lstm1_out + attn_out
        final_hidden = attn_out[:, -1, :]

        out = self.fc1(final_hidden)
        out = self.fc2(out)
        out = self.fc3(out)
        return out

    def to(self, device):
        """移动到指定设备"""
        if not self.finance_llama_is_dispatched:
            self.finance_llama = self.finance_llama.to(device)
        self.finance_llama_fc = self.finance_llama_fc.to(device)
        # 记录目标设备，避免后续 DataParallel 下 next(self.parameters()).device 不可靠
        self._target_device = device
        self.input_norm = self.input_norm.to(device)
        self.input_fc = self.input_fc.to(device)
        self.lstm1 = self.lstm1.to(device)
        self.lstm2 = self.lstm2.to(device)
        self.attention = self.attention.to(device)
        self.layer_norm1 = self.layer_norm1.to(device)
        self.layer_norm2 = self.layer_norm2.to(device)
        self.fc1 = self.fc1.to(device)
        self.fc2 = self.fc2.to(device)
        self.fc3 = self.fc3.to(device)
        return self

    def parameters(self):
        """返回模型参数迭代器"""
        params = []
        for module in [
            self.finance_llama_fc,
            self.input_norm,
            self.input_fc,
            self.lstm1,
            self.lstm2,
            self.attention,
            self.layer_norm1,
            self.layer_norm2,
            self.fc1,
            self.fc2,
            self.fc3,
        ]:
            params.extend(module.parameters())
        return iter(params)


class DLModelLoader:
    """LSTM+FinanceLlama 模型加载器 - 懒加载模式"""

    _instance: Optional["DLModelLoader"] = None
    _model = None
    _scaler_X = None
    _scaler_y = None
    _device = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self._device = None

    @staticmethod
    def _extract_state_dict(checkpoint):
        if isinstance(checkpoint, dict):
            if "state_dict" in checkpoint:
                return checkpoint["state_dict"]
            if "model_state_dict" in checkpoint:
                return checkpoint["model_state_dict"]
        return checkpoint

    @staticmethod
    def _filter_runtime_state_dict(state_dict):
        runtime_prefixes = {
            "finance_llama_fc",
            "input_norm",
            "input_fc",
            "lstm1",
            "lstm2",
            "attention",
            "layer_norm1",
            "layer_norm2",
            "fc1",
            "fc2",
            "fc3",
        }
        if not isinstance(state_dict, dict):
            return state_dict
        original_count = len(state_dict)
        removed_finance_llama = sum(
            1 for k in state_dict.keys() if k.startswith("finance_llama.")
        )
        filtered = {
            k: v for k, v in state_dict.items() if k.split(".")[0] in runtime_prefixes
        }
        if removed_finance_llama > 0:
            logger.info(
                f"检测到checkpoint包含finance_llama权重，已跳过 {removed_finance_llama} 项"
            )
        if len(filtered) == 0:
            return state_dict
        if len(filtered) != original_count:
            logger.info(f"运行时权重精简: {original_count} -> {len(filtered)}")
        return filtered

    def load_model(self):
        """加载模型权重"""
        if self._model is not None:
            return self._model

        try:
            # 懒加载 torch
            torch, _ = _get_torch()

            self._device = torch.device(
                settings.DL_DEVICE if torch.cuda.is_available() else "cpu"
            )
            if (
                torch.cuda.is_available()
                and self._device.type == "cuda"
                and self._device.index is None
            ):
                self._device = torch.device("cuda:0")

            # 模型参数
            input_size = 19  # 19个特征
            hidden_size = settings.DL_HIDDEN_SIZE
            output_size = settings.DL_OUTPUT_SIZE
            num_layers = settings.DL_NUM_LAYERS

            # 使用训练时的模型类定义，确保权重结构一致
            model_cls = _get_stock_model_class()

            # 获取是否使用LLM的配置
            use_llm = getattr(settings, "DL_USE_LLM", True)
            logger.info(
                f"创建模型: input_size={input_size}, hidden_size={hidden_size}, output_size={output_size}, use_llm={use_llm}"
            )

            # 创建模型
            self._model = model_cls(
                input_size=input_size,
                hidden_size=hidden_size,
                output_size=output_size,
                num_layers=num_layers,
                dropout=0.1,
                use_llm=use_llm,
            )

            # 加载权重
            model_path = os.path.join(settings.DL_MODEL_PATH, settings.DL_MODEL_NAME)
            logger.info(f"加载模型权重: {model_path}")

            if not os.path.exists(model_path):
                raise FileNotFoundError(f"模型文件不存在: {model_path}")

            runtime_model_path = f"{model_path}.runtime_heads.pth"
            load_path = (
                runtime_model_path if os.path.exists(runtime_model_path) else model_path
            )
            # 先在CPU上加载权重，避免直接占用GPU显存
            checkpoint = torch.load(load_path, map_location="cpu")
            state_dict = self._extract_state_dict(checkpoint)
            state_dict = self._filter_runtime_state_dict(state_dict)
            if (
                load_path == model_path
                and not os.path.exists(runtime_model_path)
                and isinstance(state_dict, dict)
            ):
                try:
                    torch.save({"state_dict": state_dict}, runtime_model_path)
                    logger.info(f"已生成运行时精简权重: {runtime_model_path}")
                except Exception as save_error:
                    logger.warning(f"生成运行时精简权重失败: {save_error}")

            if not hasattr(self._model, "load_state_dict"):
                raise TypeError(
                    f"模型对象不支持 load_state_dict: {type(self._model).__name__}. "
                    "请确认模型类继承 torch.nn.Module。"
                )

            missing, unexpected = self._model.load_state_dict(state_dict, strict=False)
            if missing:
                logger.warning(f"加载权重时缺失参数: {len(missing)} 项")
            if unexpected:
                logger.warning(f"加载权重时多余参数: {len(unexpected)} 项")

            # 确保权重与LLM的dtype一致（LLM使用float16）
            if torch.cuda.is_available():
                self._model = self._model.half()
                logger.info("模型权重已转换为float16以匹配LLM")

            if torch.cuda.is_available():
                logger.info(f"使用单GPU: {self._device}")
            self._model.to(self._device)
            self._model.eval()

            logger.info("模型加载成功")

            # 加载 scaler
            scaler_X_path = os.path.join(settings.DL_MODEL_PATH, "scaler_X.pkl")
            scaler_y_path = os.path.join(settings.DL_MODEL_PATH, "scaler_y.pkl")

            if os.path.exists(scaler_X_path):
                with open(scaler_X_path, "rb") as f:
                    self._scaler_X = _restricted_load(f)
                logger.info("scaler_X 加载成功")

            if os.path.exists(scaler_y_path):
                with open(scaler_y_path, "rb") as f:
                    self._scaler_y = _restricted_load(f)
                logger.info("scaler_y 加载成功")

            return self._model

        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            raise

    def predict(self, features: np.ndarray) -> np.ndarray:
        """
        预测未来N天价格

        Args:
            features: 标准化后的特征数据，shape=(time_steps, 19)

        Returns:
            预测价格，shape=(output_size,)
        """
        if self._model is None:
            self.load_model()

        torch, _ = _get_torch()

        # 标准化
        if self._scaler_X is not None:
            features_scaled = self._scaler_X.transform(features)
        else:
            features_scaled = features

        # 转换为 tensor
        input_tensor = (
            torch.FloatTensor(features_scaled).unsqueeze(0).to(self._device).half()
        )

        # 推理
        prompt = "stock prediction"
        try:
            param_dev = next(self._model.parameters()).device
            if param_dev != self._device:
                logger.warning(
                    f"模型参数设备 {param_dev} 与目标设备 {self._device} 不一致，自动迁移"
                )
                self._model.to(self._device)
        except Exception:
            pass
        if hasattr(self._model, "check_device_consistency"):
            try:
                self._model.check_device_consistency(
                    input_tensor, prompt_name="pre_forward"
                )
            except Exception:
                pass
        with torch.no_grad():
            pred_scaled = self._model(input_tensor, prompt)
            pred_scaled = pred_scaled.cpu().numpy()

        # 反标准化
        if self._scaler_y is not None:
            pred_scaled_reshaped = pred_scaled.reshape(-1, 1)
            pred_prices = self._scaler_y.inverse_transform(pred_scaled_reshaped)
            return pred_prices.flatten()
        else:
            return pred_scaled.flatten()

    def clear_model(self):
        """清除模型，释放 CUDA 显存"""
        if self._model is not None:
            del self._model
            self._model = None
        if self._scaler_X is not None:
            self._scaler_X = None
        if self._scaler_y is not None:
            self._scaler_y = None

        torch, _ = _get_torch()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()

        # 重置 StockLSTM_FinanceLlama 全局缓存
        global _stock_model_class
        _stock_model_class = None

        logger.info("模型已清除，CUDA 显存已释放")

    def get_scaler_X(self):
        """获取特征标准化器"""
        if self._scaler_X is None:
            self.load_model()
        return self._scaler_X

    def get_scaler_y(self):
        """获取目标标准化器"""
        if self._scaler_y is None:
            self.load_model()
        return self._scaler_y
