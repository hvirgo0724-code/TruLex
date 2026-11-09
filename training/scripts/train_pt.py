# -*- coding: utf-8 -*-
"""阶段一：继续预训练 PT（Unsloth + LoRA，自回归语言建模目标）。

读取清洗后的法律语料 JSONL（{"text": ...}），在基座上做 causal LM 继续预训练，
使模型学习法律术语、法条表述与裁判文书文风。

用法：
    python scripts/train_pt.py
    python scripts/train_pt.py --train_data data/processed/pretrain.jsonl --epochs 1 \\
        --batch_size 2 --lr 2e-5 --base_model Qwen/Qwen2.5-7B-Instruct
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datasets import Dataset
from transformers import DataCollatorForLanguageModeling, Trainer, TrainingArguments

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


def build_dataset(path, tokenizer, max_len):
    if not path or not os.path.exists(path):
        raise FileNotFoundError(
            "PT 语料不存在：%s，请先运行 scripts/prepare_pretrain.py 生成" % path
        )
    texts = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            text = obj.get("text") or obj.get("content")
            if text:
                texts.append(text)

    dataset = Dataset.from_dict({"text": texts})

    def tokenize(examples):
        return tokenizer(
            examples["text"],
            truncation=True,
            max_length=max_len,
            padding=False,
            add_special_tokens=True,
        )

    dataset = dataset.map(tokenize, batched=True, remove_columns=["text"])
    return dataset


def main():
    parser = build_arg_parser("阶段一：继续预训练 PT")
    parser.add_argument("--train_data", type=str, default=None, help="PT JSONL 路径")
    args = parser.parse_args()

    cfg = load_config(args.config)
    apply_overrides(cfg, args, stage="pt")
    log = setup_logging("train-pt")

    stage = cfg.get("pt", {})
    train_data = (args.train_data or stage.get("train_data")
                  or cfg.get("data", {}).get("pretrain_file"))
    train_data = resolve_path(train_data)

    output_dir = args.output_dir or make_output_dir(cfg, "pt")
    max_len = int(stage.get("max_seq_len", cfg.get("max_seq_len", 2048)))

    log.info("基座模型：%s", cfg.get("base_model"))
    log.info("输出目录：%s", output_dir)

    model, tokenizer = load_model_and_tokenizer(cfg, max_seq_len=max_len)
    tokenizer = ensure_pad_token(tokenizer)

    dataset = build_dataset(train_data, tokenizer, max_len)
    log.info("训练样本数：%d", len(dataset))

    training_args = TrainingArguments(
        output_dir=output_dir,
        per_device_train_batch_size=int(stage.get("batch_size", 2)),
        gradient_accumulation_steps=int(stage.get("grad_accum", 4)),
        num_train_epochs=float(stage.get("epochs", 1)),
        learning_rate=float(stage.get("lr", 2e-5)),
        weight_decay=float(stage.get("weight_decay", 0.01)),
        warmup_ratio=float(stage.get("warmup_ratio", 0.03)),
        lr_scheduler_type="cosine",
        optim="adamw_8bit",
        logging_steps=int(stage.get("logging_steps", 10)),
        save_steps=int(stage.get("save_steps", 200)),
        save_total_limit=2,
        seed=int(cfg.get("seed", 3407)),
        report_to="none",
        bf16=bool(cfg.get("bf16", True)),
        gradient_checkpointing=True,
    )

    collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        data_collator=collator,
    )

    trainer.train()
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    log.info("PT 训练完成，LoRA 权重已保存至 %s", output_dir)


if __name__ == "__main__":
    main()