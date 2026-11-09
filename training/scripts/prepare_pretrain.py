# -*- coding: utf-8 -*-
"""PT 语料清洗管线：原始法条/裁判文书/合同 txt、md -> 去重/脱敏/切块 -> JSONL。

处理步骤：
    1. 递归读取 raw_dir 下的 .txt/.md 文件
    2. 统一换行与空白、去除噪声符号
    3. 正则脱敏（身份证/手机/邮箱/银行卡/车牌）
    4. 按句切块（chunk_size 字符，带 overlap）
    5. 过滤过短/非中文占比过高片段
    6. 精确去重（md5）+ 邻近去重（MinHash Jaccard）
    7. 输出 JSONL：{"id", "text", "source"}

用法：
    python scripts/prepare_pretrain.py --input_dir data/raw --output data/processed/pretrain.jsonl
    python scripts/prepare_pretrain.py --input_dir data/raw --output data/processed/pretrain.jsonl \\
        --chunk_size 512 --chunk_overlap 64 --min_chunk_len 50 --use_jieba
"""
import argparse
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import load_config, resolve_path, setup_logging

# jieba 为可选依赖：用于中文占比/分词过滤，缺失时降级为字符统计
try:
    import jieba

    jieba.setLogLevel(20)  # 静默日志
except Exception:  # pragma: no cover
    jieba = None

LOG = None  # 占位，main 中赋值

# 常见 PII 正则（法律语料中的当事人信息敏感项）
PII_PATTERNS = [
    (re.compile(r"\d{17}[\dXx]"), "[身份证号]"),
    (re.compile(r"(?<!\d)\d{15}(?!\d)"), "[身份证号]"),
    (re.compile(r"1[3-9]\d{9}"), "[手机号]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}"), "[邮箱]"),
    (re.compile(r"\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}"), "[银行卡号]"),
    (re.compile(r"(?<!\d)\d{16,19}(?!\d)"), "[银行卡号]"),
    (
        re.compile(r"[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼]"
                   r"[A-Z][A-Z0-9]{5}"),
        "[车牌号]",
    ),
]

# 分句分隔符（中文句末 + 换行）
_SENT_RE = re.compile(r"(?<=[。！？!?；;\n])")

# 中文字符判定
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _stable_hash(text, seed=0):
    digest = hashlib.md5(("%d|%s" % (seed, text)).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def minhash_signature(text, num_hashes=64):
    """对 3-gram 集合作稳定 MinHash 签名（用于邻近去重）。"""
    shingles = [text[i:i + 3] for i in range(len(text) - 2)]
    if not shingles:
        return [0] * num_hashes
    return [min(_stable_hash(s, seed=seed + 1) for s in shingles)
            for seed in range(num_hashes)]


def _jaccard_approx(sig1, sig2):
    shared = sum(a == b for a, b in zip(sig1, sig2))
    return shared / max(len(sig1), 1)


def sanitize(text):
    """脱敏 + 基础清洗。"""
    for pattern, repl in PII_PATTERNS:
        text = pattern.sub(repl, text)
    # 统一空白
    text = re.sub(r"[ \t\u3000]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    return text


def split_sentences(text):
    parts = [p.strip() for p in _SENT_RE.split(text)]
    return [p for p in parts if p]


def chunk_text(text, chunk_size, overlap):
    """按句贪心拼接到 chunk_size，块间保留 overlap 字符重叠。"""
    sentences = split_sentences(text)
    chunks = []
    cur = ""
    for s in sentences:
        if len(cur) + len(s) > chunk_size and cur:
            chunks.append(cur)
            keep = cur[-overlap:] if overlap > 0 else ""
            cur = (keep + s) if s else keep
        else:
            cur += s
        if len(cur) >= chunk_size:
            chunks.append(cur[:chunk_size])
            keep = cur[-overlap:] if overlap > 0 else ""
            cur = keep
    if cur.strip():
        chunks.append(cur)
    return chunks


def chinese_ratio(text):
    cjk = len(_CJK_RE.findall(text))
    return cjk / max(len(text), 1)


def is_quality_chunk(text, min_len, max_cjk_drop):
    """过滤过短片段与中文占比过低（噪声/乱码）片段。"""
    if len(text) < min_len:
        return False
    ratio = chinese_ratio(text)
    return ratio >= (1.0 - max_cjk_drop)


def read_raw_texts(input_dir, log):
    """递归读取 txt/md 文件，返回 [(source, text), ...]。"""
    items = []
    exts = {".txt", ".md"}
    for root, _dirs, files in os.walk(input_dir):
        for fn in sorted(files):
            if os.path.splitext(fn)[1].lower() not in exts:
                continue
            path = os.path.join(root, fn)
            for enc in ("utf-8", "gb18030", "latin-1"):
                try:
                    with open(path, "r", encoding=enc, errors="ignore") as f:
                        text = f.read()
                    break
                except Exception:
                    continue
            if text.strip():
                items.append((path, text))
    log.info("读取原始文件 %d 个", len(items))
    return items


def process(input_dir, output, chunk_size, overlap, min_len,
            use_jieba, near_dedupe_thresh, log):
    if not os.path.isdir(input_dir):
        log.error("输入目录不存在：%s（请先放入原始法条/裁判文书/合同 txt）", input_dir)
        sys.exit(1)

    raw = read_raw_texts(input_dir, log)
    chunks = []
    for source, text in raw:
        text = sanitize(text)
        for c in chunk_text(text, chunk_size, overlap):
            if is_quality_chunk(c, min_len, 0.3):
                chunks.append({"id": None, "text": c, "source": source})

    log.info("切块后共 %d 条", len(chunks))

    # 精确去重
    seen_md5 = set()
    uniq = []
    for c in chunks:
        h = hashlib.md5(c["text"].encode("utf-8")).hexdigest()
        if h not in seen_md5:
            seen_md5.add(h)
            uniq.append(c)
    log.info("精确去重后 %d 条", len(uniq))

    # 邻近去重（MinHash）
    if near_dedupe_thresh is not None and near_dedupe_thresh < 1.0:
        kept = []
        seen_sigs = []
        for c in uniq:
            sig = minhash_signature(c["text"])
            dup = any(_jaccard_approx(sig, s) >= near_dedupe_thresh
                      for s in seen_sigs)
            if not dup:
                kept.append(c)
                seen_sigs.append(sig)
        uniq = kept
        log.info("邻近去重后 %d 条", len(uniq))

    # 可选：jieba 分词过滤（过滤分词后无有效词的片段）
    if use_jieba and jieba is not None:
        uniq = [c for c in uniq if len(jieba.lcut(c["text"])) >= 5]
        log.info("jieba 过滤后 %d 条", len(uniq))

    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        for i, c in enumerate(uniq):
            c["id"] = "pt_%08d" % i
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    log.info("已写出 %d 条到 %s", len(uniq), output)


def main():
    global LOG
    parser = argparse.ArgumentParser(description="PT 语料清洗")
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--input_dir", type=str, default=None,
                        help="原始语料目录（默认取 config data.raw_dir）")
    parser.add_argument("--output", type=str, default=None,
                        help="输出 JSONL 路径（默认 config data.pretrain_file）")
    parser.add_argument("--chunk_size", type=int, default=512)
    parser.add_argument("--chunk_overlap", type=int, default=64)
    parser.add_argument("--min_chunk_len", type=int, default=50)
    parser.add_argument("--near_dedupe_thresh", type=float, default=0.9,
                        help="邻近去重 Jaccard 阈值，1.0 表示关闭")
    parser.add_argument("--use_jieba", action="store_true", help="启用 jieba 分词过滤")
    args = parser.parse_args()

    LOG = setup_logging("prepare-pretrain")
    cfg = load_config(args.config)
    data_cfg = cfg.get("data", {})
    input_dir = args.input_dir or resolve_path(data_cfg.get("raw_dir", "data/raw"))
    output = args.output or resolve_path(data_cfg.get("pretrain_file",
                                                      "data/processed/pretrain.jsonl"))

    process(input_dir, output, args.chunk_size, args.chunk_overlap,
            args.min_chunk_len, args.use_jieba, args.near_dedupe_thresh, LOG)


if __name__ == "__main__":
    main()