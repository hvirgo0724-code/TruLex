# -*- coding: utf-8 -*-
"""权重合并导出：把 LoRA adapter 合并回基座并 save_pretrained 到 /models/merged/{version}。

默认加载基座 -> 挂载 PeftModel -> 合并卸载 -> 以 bf16 保存完整权重（含分词器/配置），
供 vLLM 直接加载推理。

用法：
    python scripts/merge_export.py --adapter /models/sft/20250101_1200 \\
        --version v1.0.0
    python scripts/merge_export.py --adapter /models/dpo/20250102_1000 \\
        --version v1.1.0 --save_method merged_4bit
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import (
    get_timestamp,
    load_base_model_tokenizer,
    load_config,
    output_root,
    setup_logging,
)


def main():
    parser = argparse.ArgumentParser(description="合并 LoRA 并导出权重")
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--adapter", type=str, required=True, help="LoRA adapter 目录")
    parser.add_argument("--version", type=str, default=None,
                        help="版本号（默认时间戳），输出 /models/merged/{version}")
    parser.add_argument("--save_method", type=str, default="merged_16bit",
                        choices=["merged_16bit", "merged_4bit", "lora"],
                        help="merged_16bit=bf16 全量合并；merged_4bit=4bit 量化；lora=仅导出 LoRA")
    parser.add_argument("--push_to_hub", type=str, default=None,
                        help="可选：合并后 push_to_hub 的仓库名（repo_id）")
    args = parser.parse_args()

    log = setup_logging("merge-export")
    cfg = load_config(args.config)

    if not os.path.isdir(args.adapter):
        log.error("adapter 目录不存在：%s", args.adapter)
        sys.exit(1)

    version = args.version or get_timestamp()
    out_dir = os.path.join(output_root(cfg), "merged", version)
    os.makedirs(out_dir, exist_ok=True)

    max_len = cfg.get("max_seq_len", 2048)
    model, tokenizer = load_base_model_tokenizer(cfg, max_seq_len=max_len)

    from peft import PeftModel

    model = PeftModel.from_pretrained(model, args.adapter)

    if args.save_method == "lora":
        log.info("仅导出 LoRA 到 %s", out_dir)
        model.save_pretrained(out_dir)
        tokenizer.save_pretrained(out_dir)
    else:
        # Unsloth 提供 save_pretrained_merged；退化方案：merge_and_unload + save
        if hasattr(model, "save_pretrained_merged"):
            log.info("合并 LoRA（%s）并保存到 %s", args.save_method, out_dir)
            model.save_pretrained_merged(out_dir, tokenizer, save_method=args.save_method)
        else:
            log.info("merge_and_unload 后 save_pretrained 到 %s", out_dir)
            model = model.merge_and_unload()
            model.save_pretrained(out_dir, safe_serialization=True)
            tokenizer.save_pretrained(out_dir)

    if args.push_to_hub:
        model.push_to_hub(args.push_to_hub, safe_serialization=True)
        tokenizer.push_to_hub(args.push_to_hub)

    log.info("导出完成：%s", out_dir)


if __name__ == "__main__":
    main()