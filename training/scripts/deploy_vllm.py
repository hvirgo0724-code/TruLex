# -*- coding: utf-8 -*-
"""vLLM 推理部署：生成 `vllm serve` 启动命令，也可直接以子进程/AsyncLLMEngine 运行。

用法：
    # 打印完整启动命令（默认）
    python scripts/deploy_vllm.py --model /models/merged/v1.0.0

    # 直接启动服务
    python scripts/deploy_vllm.py --model /models/merged/v1.0.0 --run

    # GPTQ/AWQ 量化模型
    python scripts/deploy_vllm.py --model /models/merged/v1.0.0-qptq \\
        --quantization gptq
    python scripts/deploy_vllm.py --model /models/merged/v1.0.0-awq \\
        --quantization awq

生成命令示例：
    vllm serve /models/merged/v1.0.0 --host 0.0.0.0 --port 8000 \\
        --served-model-name trullex --gpu-memory-utilization 0.90 \\
        --tensor-parallel-size 1 --max-model-len 8192
"""
import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import load_config, setup_logging


def build_command(model, deploy):
    port = int(deploy.get("port", 8000))
    served_name = deploy.get("served_model_name", "trullex")
    gmu = float(deploy.get("gpu_memory_utilization", 0.9))
    tp = int(deploy.get("tensor_parallel_size", 1))
    max_len = int(deploy.get("max_model_len", 8192))
    quant = deploy.get("quantization")

    cmd = [
        "vllm", "serve", model,
        "--host", "0.0.0.0",
        "--port", str(port),
        "--served-model-name", str(served_name),
        "--gpu-memory-utilization", "%.2f" % gmu,
        "--tensor-parallel-size", str(tp),
        "--max-model-len", str(max_len),
    ]
    if quant and str(quant).lower() not in ("none", "null", ""):
        cmd += ["--quantization", str(quant)]
    return cmd


def run_async_engine_example(model, log):
    """AsyncLLMEngine 最小示例（选中演示）。"""
    try:
        from vllm import LLM, SamplingParams
    except Exception as exc:
        log.warning("无法导入 vLLM（未安装或环境不支持）：%s", exc)
        return
    log.info("vLLM 加载模型 %s ...", model)
    llm = LLM(model=model, tensor_parallel_size=1)
    params = SamplingParams(temperature=0.1, max_tokens=256)
    outputs = llm.generate(["买卖合同纠纷，标的物风险何时转移？"], params)
    for o in outputs:
        log.info("输出：%s", o.outputs[0].text)


def main():
    parser = argparse.ArgumentParser(description="vLLM 推理部署")
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--model", type=str, default=None,
                        help="合并后的模型目录（默认 /models/merged/{version} 需自行指定）")
    parser.add_argument("--version", type=str, default=None,
                        help="配合 --model 缺省时定位 /models/merged/{version}")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--quantization", type=str, default=None,
                        choices=["gptq", "awq", "fp8", "bitsandbytes", None])
    parser.add_argument("--gpu_memory_utilization", type=float, default=None)
    parser.add_argument("--tensor_parallel_size", type=int, default=None)
    parser.add_argument("--max_model_len", type=int, default=None)
    parser.add_argument("--served_model_name", type=str, default=None)
    parser.add_argument("--run", action="store_true", help="直接子进程启动服务")
    parser.add_argument("--demo", action="store_true", help="运行 AsyncLLMEngine 演示推理")
    args = parser.parse_args()

    log = setup_logging("deploy-vllm")
    cfg = load_config(args.config)
    deploy = dict(cfg.get("deploy", {}))

    model = args.model
    if not model:
        version = args.version or "latest"
        model = os.path.join(cfg.get("output", {}).get("root", "/models"),
                             "merged", version)

    # 命令行覆盖
    overrides = {
        "port": args.port,
        "quantization": args.quantization,
        "gpu_memory_utilization": args.gpu_memory_utilization,
        "tensor_parallel_size": args.tensor_parallel_size,
        "max_model_len": args.max_model_len,
        "served_model_name": args.served_model_name,
    }
    for k, v in overrides.items():
        if v is not None:
            deploy[k] = v

    cmd = build_command(model, deploy)
    print("\n" + " \\\n  ".join(cmd) + "\n")

    if args.demo:
        run_async_engine_example(model, log)
    elif args.run:
        log.info("启动 vLLM 服务 ...")
        subprocess.run(cmd)


if __name__ == "__main__":
    main()