# -*- coding: utf-8 -*-
"""阶段二：监督微调 SFT（trl.SFTTrainer + Qwen 对话模板）。

读取 SFT 指令数据 JSONL（{"messages": [...]}），用 chat template 格式化后
在 LoRA 上做指令跟随微调，覆盖合同审查/法条检索/判例分析/文书生成/法律问答/工具调用。

用法：
    python scripts/train_sft.py
    python scripts/train_sft.py --train_data data/processed/sft.jsonl --epochs 3 \\
        --batch_size 2 --lr 2e-4
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datasets import Dataset
from trl import SFTConfig, SFTTrainer

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
            "SFT 数据不存在：%s，请先运行 scripts/prepare_sft.py 生成" % path
        )
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append({"messages": json.loads(line)["messages"]})
    return Dataset.from_list(rows)


def main():
    parser = build_arg_parser("阶段二：监督微调 SFT")
    parser.add_argument("--train_data", type=str, default=None, help="SFT JSONL 路径")
    args = parser.parse_args()

    cfg = load_config(args.config)
    apply_overrides(cfg, args, stage="sft")
    log = setup_logging("train-sft")

    stage = cfg.get("sft", {})
    train_data = (args.train_data or stage.get("train_data")
                  or cfg.get("data", {}).get("sft_file"))
    train_data = resolve_path(train_data)

    output_dir = args.output_dir or make_output_dir(cfg, "sft")
    max_len = int(stage.get("max_seq_len", cfg.get("max_seq_len", 2048)))

    log.info("基座模型：%s", cfg.get("base_model"))
    log.info("输出目录：%s", output_dir)

    model, tokenizer = load_model_and_tokenizer(cfg, max_seq_len=max_len)
    tokenizer = ensure_pad_token(tokenizer)
    tokenizer.padding_side = "right"

    dataset = load_dataset(train_data)
    log.info("训练样本数：%d", len(dataset))

    def formatting_func(example):
        return tokenizer.apply_chat_template(
            example["messages"],
            tokenize=False,
            add_generation_prompt=False,
        )

    sft_config = SFTConfig(
        output_dir=output_dir,
        per_device_train_batch_size=int(stage.get("batch_size", 2)),
        gradient_accumulation_steps=int(stage.get("grad_accum", 4)),
        num_train_epochs=float(stage.get("epochs", 3)),
        learning_rate=float(stage.get("lr", 2e-4)),
        weight_decay=float(stage.get("weight_decay", 0.01)),
        warmup_ratio=float(stage.get("warmup_ratio", 0.03)),
        lr_scheduler_type="cosine",
        optim="adamw_8bit",
        max_seq_length=max_len,
        logging_steps=int(stage.get("logging_steps", 5)),
        save_steps=int(stage.get("save_steps", 100)),
        save_total_limit=2,
        packing=False,
        seed=int(cfg.get("seed", 3407)),
        report_to="none",
        bf16=bool(cfg.get("bf16", True)),
        gradient_checkpointing=True,
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        args=sft_config,
        formatting_func=formatting_func,
    )

    trainer.train()
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    log.info("SFT 训练完成，LoRA 权重已保存至 %s", output_dir)


if __name__ == "__main__":
    main()