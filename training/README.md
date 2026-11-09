# training/ —— 物流交通运输法律大模型训练三阶段（Unsloth）

面向物流交通运输法律领域的自训练大模型：**PT 继续预训练 → SFT 监督微调 → DPO 偏好对齐**，配套
数据准备、三层评估、权重合并导出与 vLLM 部署。基座默认 `unsloth/Qwen2.5-7B-Instruct`
（可用 `BASE_MODEL` 环境变量或 `--base_model` 覆盖，如 `Qwen/Qwen2.5-7B-Instruct`、
`unsloth/Qwen3-8B`），使用 LoRA 省显存，单片 A100/H100 80G 即可跑。

## 目录结构

```
training/
├── Dockerfile
├── requirements.txt
├── README.md
├── config/
│   └── train.yaml          # 统一配置（模型/超参/数据路径/产出目录）
├── scripts/
│   ├── common.py           # 公共工具：配置/日志/模型加载/LoRA/输出路径
│   ├── prepare_pretrain.py # PT 语料清洗
│   ├── prepare_sft.py      # SFT 指令数据生成
│   ├── prepare_dpo.py      # DPO 偏好对生成
│   ├── train_pt.py         # 阶段一：继续预训练
│   ├── train_sft.py        # 阶段二：监督微调
│   ├── train_dpo.py        # 阶段三：偏好对齐
│   ├── evaluate.py         # 三层评估
│   ├── merge_export.py     # LoRA 合并导出
│   └── deploy_vllm.py      # vLLM 部署
└── data/
    └── README.md           # 数据格式与示例
```

## 环境准备

```bash
# 本机（建议 CUDA 12.1）
pip install -r requirements.txt

# 或 Docker（GPU）
docker build -t trullex-training ./training
docker compose --profile training run --rm training bash
```

## 完整流程

```bash
cd training

# 0) 数据准备（内置示例可先跑通；真实生产请替换为正式语料）
mkdir -p data/raw
python scripts/prepare_pretrain.py          # raw txt -> data/processed/pretrain.jsonl
python scripts/prepare_sft.py               # -> data/processed/sft.jsonl
python scripts/prepare_dpo.py               # -> data/processed/dpo.jsonl

# 1) 阶段一：继续预训练（物流交通法律语料，语言建模目标）
python scripts/train_pt.py

# 2) 阶段二：监督微调（运单审查/责任认定/法规检索/判例检索/文书生成 + 工具调用）
python scripts/train_sft.py

# 3) 阶段三：偏好对齐（三元组 chosen/rejected）
python scripts/train_dpo.py

# 4) 评估（自动指标 + 可选 LLM Judge + 红队）
python scripts/evaluate.py                  # 内置演示集直接可跑
python scripts/evaluate.py --eval_data data/eval/eval.jsonl --judge

# 5) 合并 LoRA 并导出
python scripts/merge_export.py --adapter /models/sft/YYYYMMDD_hhmm --version v1.0.0

# 6) 部署
python scripts/deploy_vllm.py --model /models/merged/v1.0.0
python scripts/deploy_vllm.py --model /models/merged/v1.0.0 --run
```

## 关键超参（`config/train.yaml`）

| 阶段 | 学习率 | epochs | batch | grad_accum | 关键点 |
|---|---|---|---|---|---|
| PT | 2e-5 | 1 | 2 | 4 | 自回归 LM，DataCollatorForLanguageModeling(mlm=False) |
| SFT | 2e-4 | 3 | 2 | 4 | trl.SFTTrainer + Qwen chat template |
| DPO | 5e-5 | 1 | 1 | 8 | trl.DPOTrainer，beta=0.1，max_prompt_length=1024 |

LoRA：r=16、alpha=16、dropout=0，目标模块 `q/k/v/o_proj + gate/up/down_proj`，
`bias=none`，`use_gradient_checkpointing=unsloth`，`use_rslora=false`。

> 所有训练脚本均支持命令行覆盖：`--base_model`、`--epochs`、`--batch_size`、
> `--lr`、`--max_seq_len`、`--output_dir`、`--train_data`。

## 产物目录约定

```
/models/{stage}/{yyyyMMdd_hhmm}     # PT/SFT/DPO 的 LoRA 产物
/models/merged/{version}            # 合并后的完整权重（供 vLLM 加载）
reports/eval_{timestamp}.json/.txt  # 评估报告（相对 training/ 下 reports/）
```

`/models` 由容器卷 `model_repo` 挂载；可用 `OUTPUT_ROOT` 环境变量覆盖。

## 硬件与显存建议

- **推荐**：单卡 A100/H100 80G。7B 模型 4bit 加载 + LoRA 峰值约 20–30 GB 显存，留有充足余量。
- **最低**：24 GB（如 3090/4090/A10），`max_seq_len=2048`、`batch_size=1`、
  `grad_accum` 相应调大；DPO 需额外参考模型显存，可设 `max_length/max_prompt_length` 更小。
- 关闭 `bf16`（`config/train.yaml` 的 `bf16: false`）可兼容不支持 bf16 的旧卡。
- 量化部署：合并时 `--save_method merged_4bit` 或另用 GPTQ/AWQ 量化，vLLM 配合
  `--quantization gptq/awq` 降低推理显存。