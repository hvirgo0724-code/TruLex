# -*- coding: utf-8 -*-
"""对「基座模型」跑基线评测：读取评测黄金集，调用线上 LLM 生成预测，回填后供 evaluate.py 计算指标。

产出 data/eval/eval_pred.jsonl（每条带 prediction），再运行：
    python scripts/evaluate.py --eval_data data/eval/eval_pred.jsonl --judge

说明：这里预测来自线上基座模型（.env 中 MODEL_NAME），是真实测量值，
      用于得到「微调前基线」，而非凭空编造。
"""
import json
import os
import sys
import time
from urllib import request, error

HERE = os.path.dirname(os.path.abspath(__file__))
TRAINING = os.path.dirname(HERE)
EVAL_SRC = os.path.join(TRAINING, "data", "eval", "eval.jsonl")
EVAL_DST = os.path.join(TRAINING, "data", "eval", "eval_pred.jsonl")

SYSTEM = (
    "你是一名专业、审慎的物流交通运输法律智能助手。"
    "基于现行法律法规作答，援引法条须准确，无法确定时如实说明，不虚构法条。"
)


def load_env():
    keys = {}
    for line in open(os.path.join(TRAINING, "..", ".env"), encoding="utf-8"):
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            keys[k.strip()] = v.strip().strip('"').strip("'")
    return keys


def chat(env, messages):
    base = env["BASE_URL"].rstrip("/")
    url = base + "/chat/completions"
    payload = {"model": env["MODEL_NAME"], "messages": messages,
               "temperature": 0, "max_tokens": 768}
    req = request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + env["API_KEY"]})
    try:
        with request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        msg = data["choices"][0]["message"]
        return (msg.get("content") or msg.get("reasoning_content") or "")
    except error.HTTPError as e:
        sys.stderr.write("HTTP %s: %s\n" % (e.code, e.read().decode()[:200]))
        return ""
    except Exception as e:
        sys.stderr.write("ERR %r\n" % e)
        return ""


def main():
    env = load_env()
    rows = [json.loads(l) for l in open(EVAL_SRC, encoding="utf-8") if l.strip()]
    out = []
    for i, r in enumerate(rows):
        pred = chat(env, [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": r["input"]},
        ])
        r = dict(r)
        r["prediction"] = pred.strip()
        out.append(r)
        print("[%02d/%02d] %s => %s" % (i + 1, len(rows), r["task"], pred[:36].replace("\n", " ")))
        time.sleep(0.2)
    with open(EVAL_DST, "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("已写出 %d 条预测 -> %s" % (len(out), EVAL_DST))


if __name__ == "__main__":
    main()