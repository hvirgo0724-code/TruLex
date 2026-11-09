# -*- coding: utf-8 -*-
"""校验 PT / SFT / DPO 三个数据文件的格式与数量，完全对齐各 train_*.py 的加载逻辑。

本脚本仅依赖标准库，无需 unsloth/torch/trl，可在无 GPU 环境运行：
    python scripts/verify_data.py
    python scripts/verify_data.py --data_dir data/processed --expect 100

校验规则（与 train_pt.py / train_sft.py / train_dpo.py 的 build/load 逻辑一致）：
    PT  : 每行 JSON，obj.get("text") or obj.get("content") 非空
    SFT : 每行 JSON，obj["messages"] 为列表，每条含合法 role 与 content
    DPO : 每行 JSON，obj["prompt"]/obj["chosen"]/obj["rejected"] 为消息列表
"""
import argparse
import json
import os
import sys

ALLOWED_ROLES = {"system", "user", "assistant", "tool"}


def iter_lines(path):
    if not os.path.exists(path):
        raise FileNotFoundError("数据文件不存在：%s" % path)
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield i, json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError("第 %d 行 JSON 解析失败：%s" % (i, e))


def check_message_list(messages, where):
    if not isinstance(messages, list) or not messages:
        raise ValueError("%s 的 messages 必须是至少含一条的非空列表" % where)
    for j, m in enumerate(messages):
        if not isinstance(m, dict):
            raise ValueError("%s 第 %d 条消息不是对象" % (where, j))
        role = m.get("role")
        if role not in ALLOWED_ROLES:
            raise ValueError("%s 第 %d 条消息 role 非法：%r" % (where, j, role))
        if "content" in m and m["content"] is not None and not isinstance(m["content"], str):
            raise ValueError("%s 第 %d 条消息 content 类型非法" % (where, j))
        if role == "tool" and not m.get("tool_call_id"):
            raise ValueError("%s 第 %d 条 tool 消息缺少 tool_call_id" % (where, j))


def verify_pt(path, expect):
    n = 0
    for i, obj in iter_lines(path):
        text = obj.get("text") or obj.get("content")
        if not text or not isinstance(text, str) or not text.strip():
            raise ValueError("PT 第 %d 行缺少 text/content 字段" % i)
        n += 1
    return n


def verify_sft(path, expect):
    n = 0
    for i, obj in iter_lines(path):
        messages = obj.get("messages")
        check_message_list(messages, "SFT 第 %d 行" % i)
        if not any(m.get("role") == "user" for m in messages):
            raise ValueError("SFT 第 %d 行缺少 user 消息" % i)
        n += 1
    return n


def verify_dpo(path, expect):
    n = 0
    for i, obj in iter_lines(path):
        for key in ("prompt", "chosen", "rejected"):
            if key not in obj:
                raise ValueError("DPO 第 %d 行缺少字段 %s" % (i, key))
            check_message_list(obj[key], "DPO 第 %d 行 %s" % (i, key))
        if not any(m.get("role") == "assistant" for m in obj["chosen"]):
            raise ValueError("DPO 第 %d 行 chosen 缺少 assistant 消息" % i)
        if not any(m.get("role") == "assistant" for m in obj["rejected"]):
            raise ValueError("DPO 第 %d 行 rejected 缺少 assistant 消息" % i)
        n += 1
    return n


def main():
    parser = argparse.ArgumentParser(description="校验训练数据格式与数量")
    parser.add_argument("--data_dir", type=str, default="data/processed")
    parser.add_argument("--expect", type=int, default=100)
    args = parser.parse_args()

    files = {
        "PT (pretrain.jsonl)": (verify_pt, "pretrain.jsonl"),
        "SFT (sft.jsonl)": (verify_sft, "sft.jsonl"),
        "DPO (dpo.jsonl)": (verify_dpo, "dpo.jsonl"),
    }

    ok = True
    for label, (fn, name) in files.items():
        path = os.path.join(args.data_dir, name)
        try:
            n = fn(path, args.expect)
            status = "OK" if n == args.expect else "FAIL"
            if n != args.expect:
                ok = False
            print("[%s] %-22s %d 条（期望 %d）" % (status, label, n, args.expect))
        except Exception as e:
            ok = False
            print("[FAIL] %-22s %s" % (label, e))

    print("-" * 50)
    print("结果：%s" % ("全部通过" if ok else "存在失败项"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()