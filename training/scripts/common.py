# -*- coding: utf-8 -*-
"""training 公共工具：配置加载、日志、路径、Unsloth 模型/分词器加载。

训练脚本 / 数据准备 / 评估脚本统一通过本模块复用一致的配置与产物目录约定：
    /models/{stage}/{yyyyMMdd_hhmm}

环境变量：
    BASE_MODEL   覆盖配置中的 base_model
    OUTPUT_ROOT  覆盖 /models 产物根目录
    TRAIN_CONFIG 覆盖配置文件路径
"""
import argparse
import logging
import os
from datetime import datetime

import yaml

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPTS_DIR)  # = training/

DEFAULT_CONFIG_PATH = os.path.join(PROJECT_ROOT, "config", "train.yaml")

# Unsloth 推荐的 LoRA 目标模块（Qwen 系列：全注意力 + MLP 门控）
DEFAULT_TARGET_MODULES = [
    "q_proj",
    "k_proj",
    "v_proj",
    "o_proj",
    "gate_proj",
    "up_proj",
    "down_proj",
]


# --------------------------------------------------------------------------- #
# 基础工具
# --------------------------------------------------------------------------- #
def get_timestamp(fmt="%Y%m%d_%H%M"):
    return datetime.now().strftime(fmt)


def setup_logging(name=None, level=None):
    level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger(name or "trullex-train")


def load_yaml(path):
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def deep_merge(base, override):
    result = dict(base or {})
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def resolve_path(path):
    """把相对路径解析为相对项目根目录 training/ 的绝对路径。"""
    if not path:
        return path
    if os.path.isabs(path):
        return path
    return os.path.join(PROJECT_ROOT, path)


# --------------------------------------------------------------------------- #
# 配置与产物路径
# --------------------------------------------------------------------------- #
def load_config(config_path=None):
    path = config_path or os.getenv("TRAIN_CONFIG", DEFAULT_CONFIG_PATH)
    cfg = load_yaml(path)
    # 环境变量优先
    if os.getenv("BASE_MODEL"):
        cfg["base_model"] = os.getenv("BASE_MODEL")
    if os.getenv("OUTPUT_ROOT"):
        cfg.setdefault("output", {})["root"] = os.getenv("OUTPUT_ROOT")
    return cfg


def output_root(cfg):
    return cfg.get("output", {}).get("root", "/models")


def make_output_dir(cfg, stage, subdir=None):
    """返回并创建 /models/{stage}/{yyyyMMdd_hhmm}（或显式 subdir）。"""
    root = output_root(cfg)
    tail = subdir if subdir else get_timestamp()
    path = os.path.join(root, stage, tail)
    os.makedirs(path, exist_ok=True)
    return path


def build_arg_parser(description, extra=None):
    """构造统一的命令行参数解析器（含通用训练超参）。"""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--config", type=str, default=None,
                        help="配置文件路径，默认 config/train.yaml")
    parser.add_argument("--base_model", type=str, default=None,
                        help="覆盖配置文件中的 base_model")
    parser.add_argument("--output_dir", type=str, default=None,
                        help="覆盖输出目录（默认 /models/{stage}/{时间戳}）")
    parser.add_argument("--max_seq_len", type=int, default=None)
    parser.add_argument("--epochs", type=float, default=None)
    parser.add_argument("--batch_size", type=int, default=None)
    parser.add_argument("--lr", type=float, default=None)
    if extra:
        extra(parser)
    return parser


def apply_overrides(cfg, args, stage=None):
    """把命令行通用超参覆盖到 cfg（以及 cfg[stage]）。"""
    if getattr(args, "base_model", None):
        cfg["base_model"] = args.base_model
    if stage:
        section = cfg.setdefault(stage, {})
        if getattr(args, "max_seq_len", None) is not None:
            section["max_seq_len"] = args.max_seq_len
        if getattr(args, "epochs", None) is not None:
            section["epochs"] = args.epochs
        if getattr(args, "batch_size", None) is not None:
            section["batch_size"] = args.batch_size
        if getattr(args, "lr", None) is not None:
            section["lr"] = args.lr


# --------------------------------------------------------------------------- #
# Unsloth 模型与 LoRA
# --------------------------------------------------------------------------- #
def _parse_dtype(dtype):
    if dtype in (None, "", "auto", "none"):
        return None
    import torch

    mapping = {
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
        "float32": torch.float32,
    }
    return mapping.get(str(dtype))


def get_target_modules(cfg):
    mods = cfg.get("lora", {}).get("target_modules") or DEFAULT_TARGET_MODULES
    return list(mods)


def load_model_and_tokenizer(cfg, max_seq_len=None):
    """用 Unsloth 加载基座模型并挂载 LoRA，返回 (model, tokenizer)。"""
    from unsloth import FastLanguageModel

    model_name = cfg.get("base_model", "unsloth/Qwen2.5-7B-Instruct")
    max_len = max_seq_len or cfg.get("max_seq_len", 2048)
    load_in_4bit = bool(cfg.get("load_in_4bit", True))
    dtype = _parse_dtype(cfg.get("dtype"))

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_name,
        max_seq_length=int(max_len),
        dtype=dtype,
        load_in_4bit=load_in_4bit,
    )

    lora = cfg.get("lora", {})
    model = FastLanguageModel.get_peft_model(
        model,
        r=int(lora.get("r", 16)),
        target_modules=get_target_modules(cfg),
        lora_alpha=int(lora.get("lora_alpha", 16)),
        lora_dropout=float(lora.get("lora_dropout", 0.0)),
        bias=lora.get("bias", "none"),
        use_gradient_checkpointing="unsloth",
        random_state=int(cfg.get("seed", 3407)),
        use_rslora=bool(lora.get("use_rslora", False)),
        loftq_config=None,
    )
    return model, tokenizer


def load_base_model_tokenizer(cfg, max_seq_len=None):
    """仅加载基座（不挂 LoRA），用于权重合并与导出。"""
    from unsloth import FastLanguageModel

    model_name = cfg.get("base_model", "unsloth/Qwen2.5-7B-Instruct")
    max_len = max_seq_len or cfg.get("max_seq_len", 2048)
    load_in_4bit = bool(cfg.get("load_in_4bit", True))
    dtype = _parse_dtype(cfg.get("dtype"))

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_name,
        max_seq_length=int(max_len),
        dtype=dtype,
        load_in_4bit=load_in_4bit,
    )
    return model, tokenizer


def ensure_pad_token(tokenizer):
    """Qwen 默认无 pad_token，统一用 eos_token 兜底。"""
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    return tokenizer