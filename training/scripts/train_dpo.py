# -*- coding: utf-8 -*-
"""阶段三：偏好对齐 DPO（trl.DPOTrainer + 三元组 prompt/chosen/rejected）。

读取 DPO 偏好对数据 JSONL，在 SFT 后的 LoRA 上做直接偏好优化：
chosen 覆盖效果偏好与安全偏好，rejected 覆盖粗劣回答、拒答红线、越权结论、幻觉法条。

用法：
    python scripts/train_dpo.py
    python scripts/train_dpo.py --train_data data/processed/dpo.jsonl \\
        --batch_size 1 --lr 5e-5
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datasets import Dataset
from trl import DPOConfig, DPOTrainer

from common import (
    apply_overrides,
    build_arg_parser,
    ensure_pad_token,
    load_config,
    load_model_and_tokenizer,
    make_output_dir,
    resolve_path,
    setup_logging,
)


def load_dataset(path):
    if not path or not os.path.exists(path):
        raise FileNotFoundError(
            "DPO 数据不存在：%s，请先运行 scripts/prepare_dpo.py 生成" % path
        )
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                obj = json.loads(line)
                # 兼容字符串与消息列表两种形态
                rows.append({
                    "prompt": obj["prompt"],
                    "chosen": obj["chosen"],
                    "rejected": obj["rejected"],
                })
    return Dataset.from_list(rows)


def main():
    parser = build_arg_parser("阶段三：偏好对齐 DPO")
    parser.add_argument("--train_data", type=str, default=None, help="DPO JSONL 路径")
    args = parser.parse_args()

    cfg = load_config(args.config)
    apply_overrides(cfg, args, stage="dpo")
    log = setup_logging("train-dpo")

    stage = cfg.get("dpo", {})
    train_data = (args.train_data or stage.get("train_data")
                  or cfg.get("data", {}).get("dpo_file"))
    train_data = resolve_path(train_data)

    output_dir = args.output_dir or make_output_dir(cfg, "dpo")
    max_len = int(stage.get("max_length", cfg.get("max_seq_len", 2048)))

    log.info("基座模型：%s", cfg.get("base_model"))
    log.info("输出目录：%s", output_dir)

    model, tokenizer = load_model_and_tokenizer(cfg, max_seq_len=max_len)
    tokenizer = ensure_pad_token(tokenizer)
    tokenizer.padding_side = "left"

    dataset = load_dataset(train_data)
    log.info("训练样本数：%d", len(dataset))

    dpo_config = DPOConfig(
        output_dir=output_dir,
        per_device_train_batch_size=int(stage.get("batch_size", 1)),
        gradient_accumulation_steps=int(stage.get("grad_accum", 8)),
        num_train_epochs=float(stage.get("epochs", 1)),
        learning_rate=float(stage.get("lr", 5e-5)),
        warmup_ratio=float(stage.get("warmup_ratio", 0.05)),
        lr_scheduler_type="cosine",
        beta=float(stage.get("beta", 0.1)),
        max_length=int(stage.get("max_length", 2048)),
        max_prompt_length=int(stage.get("max_prompt_length", 1024)),
        logging_steps=int(stage.get("logging_steps", 5)),
        save_steps=int(stage.get("save_steps", 100)),
        save_total_limit=2,
        remove_unused_columns=False,
        seed=int(cfg.get("seed", 3407)),
        report_to="none",
        bf16=bool(cfg.get("bf16", True)),
        gradient_checkpointing=True,
    )

    trainer = DPOTrainer(
        model=model,
        ref_model=None,  # 内部自动创建参考模型
        args=dpo_config,
        train_dataset=dataset,
        tokenizer=tokenizer,
        peft_config=None,  # 模型已是 LoRA，无需再包一层
    )

    trainer.train()
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    log.info("DPO 训练完成，LoRA 权重已保存至 %s", output_dir)


if __name__ == "__main__":
    main()