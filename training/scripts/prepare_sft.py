# -*- coding: utf-8 -*-
"""SFT 指令数据生成：6 类法律能力 + function calling 工具调用格式。

覆盖能力：
    contract_review   合同审查
    statute_retrieval 法条检索
    case_analysis     判例分析
    doc_drafting      文书生成
    legal_qa          法律问答
    tool_call         工具调用（function calling）

输出格式（每条一行 JSON）：
    {"messages": [{"role": "system", "content": "..."},
                  {"role": "user", "content": "..."},
                  {"role": "assistant", "content": "..."}]}

工具调用时 assistant 消息可携带 tool_calls，并追加 tool 角色返回结果：
    {"role": "assistant", "content": null,
     "tool_calls": [{"id": "call_1", "type": "function",
                     "function": {"name": "search_law", "arguments": "{\"keyword\": \"...\"}"}}]}
    {"role": "tool", "tool_call_id": "call_1", "content": "..."}

用法：
    python scripts/prepare_sft.py --output data/processed/sft.jsonl
    python scripts/prepare_sft.py --input extra_qa.jsonl --output data/processed/sft.jsonl
        # --input 为额外补充的 {"instruction":..,"input":..,"output":..} 或已有 messages 数据
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import load_config, resolve_path, setup_logging

# --------------------------------------------------------------------------- #
# 各能力 System Prompt
# --------------------------------------------------------------------------- #
SYSTEM_PROMPTS = {
    "contract_review": (
        "你是一名资深合同审查律师。请逐条审查合同条款，识别法律风险点，"
        "给出风险等级（高/中/低）、条款定位与修改建议。"
    ),
    "statute_retrieval": (
        "你是一名法律检索助手。请根据用户问题检索并引述相关法条，"
        "给出法条名称、具体条文内容及适用分析。"
    ),
    "case_analysis": (
        "你是一名判例分析师。请结合相关裁判要旨分析案情，"
        "归纳争议焦点、裁判规则与类案参考要点。"
    ),
    "doc_drafting": (
        "你是一名法律文书起草助手。请根据用户提供的要素，"
        "起草结构完整、用语规范的法律文书。"
    ),
    "legal_qa": (
        "你是一名专业、审慎的法律问答助手。请基于现行法律法规回答，"
        "无法确定时如实说明，不得虚构法条。"
    ),
    "tool_call": (
        "你是途律 · TruLex，一名可调用工具的物流交通运输法律智能体。请判断是否需要调用工具获取法律依据，"
        "如需则先输出 tool_calls，再基于工具返回结果作答。可调用工具："
        "search_law（法条检索）、search_case（判例检索）。"
    ),
}


def _tool_call_msg(call_id, name, arguments):
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": call_id,
            "type": "function",
            "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)},
        }],
    }


# --------------------------------------------------------------------------- #
# 内置示例（演示格式；生产环境请用真实语料扩充）
# --------------------------------------------------------------------------- #
BUILTIN_EXAMPLES = [
    # --- 合同审查 ---
    {
        "capability": "contract_review",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPTS["contract_review"]},
            {"role": "user", "content": (
                "请审查以下条款：\u300c乙方逾期交付的，每逾期一日按合同总价款的0.02%"
                "向甲方支付违约金，违约金总额不超过合同总价款的20%。\u300d"
            )},
            {"role": "assistant", "content": (
                "【风险等级】中\n"
                "【条款定位】违约责任条款\n"
                "【风险分析】1. 未约定甲方付款义务对应的违约责任，权利义务不对等；"
                "2. 违约金上限20%偏高，若明显超出实际损失，可能因依据《民法典》第585条"
                "被请求调整而部分无效；3. 建议明确\u201c逾期交付\u201d的起算点（是否含验收）。\n"
                "【修改建议】增加甲方迟延付款的对称违约责任；将违约金上限调整至已付价款的10%，"
                "并按实际损失与可得利益损失计算。"
            )},
        ],
    },
    # --- 法条检索 ---
    {
        "capability": "statute_retrieval",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPTS["statute_retrieval"]},
            {"role": "user", "content": "买卖合同中，标的物毁损灭失的风险自何时转移给买受人？"},
            {"role": "assistant", "content": (
                "根据《民法典》第六百零四条：标的物毁损、灭失的风险，在标的物交付之前由出卖人承担，"
                "交付之后由买受人承担，但是法律另有规定或者当事人另有约定的除外。\n"
                "适用分析：风险自\u201c交付\u201d时转移；涉及运输的，按第六百零七条，"
                "出卖人将标的物交付给第一承运人后，风险由买受人承担。"
            )},
        ],
    },
    # --- 判例分析 ---
    {
        "capability": "case_analysis",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPTS["case_analysis"]},
            {"role": "user", "content": (
                "案情：甲在电商平台购买商品，收货后发现为假冒伪劣产品，商家拒绝退一赔三。"
                "请分析甲能否主张惩罚性赔偿。"
            )},
            {"role": "assistant", "content": (
                "【争议焦点】经营者是否存在欺诈，甲能否依据消费者权益保护法主张退一赔三。\n"
                "【裁判规则】根据《消费者权益保护法》第五十五条，经营者提供商品有欺诈行为的，"
                "应当按照消费者的要求增加赔偿其受到的损失，增加赔偿的金额为消费者购买商品价款的"
                "三倍；增加赔偿的金额不足五百元的，为五百元。\n"
                "【类案参考】若经营者明知系假冒仍标注正品销售，可认定构成欺诈，"
                "消费者主张三倍赔偿通常获得支持。"
            )},
        ],
    },
    # --- 文书生成 ---
    {
        "capability": "doc_drafting",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPTS["doc_drafting"]},
            {"role": "user", "content": (
                "请起草一份民事起诉状：原告张某，被告某贸易公司，案由为买卖合同纠纷，"
                "请求判令被告支付货款10万元及逾期利息。"
            )},
            {"role": "assistant", "content": (
                "民事起诉状\n\n"
                "原告：张某，男，住……，联系电话：……\n"
                "被告：某贸易公司，住所地：……，法定代表人：……\n\n"
                "诉讼请求：\n"
                "一、判令被告支付货款人民币100000元；\n"
                "二、判令被告支付上述款项的逾期利息（以100000元为基数，自2024年1月1日起"
                "按全国银行间同业拆借中心公布的贷款市场报价利率计算至实际清偿之日止）；\n"
                "三、本案诉讼费用由被告承担。\n\n"
                "事实与理由：\n……（依法依约主张）……\n\n"
                "此致\n某人民法院\n\n具状人：张某\n日期：____年__月__日"
            )},
        ],
    },
    # --- 法律问答 ---
    {
        "capability": "legal_qa",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPTS["legal_qa"]},
            {"role": "user", "content": "试用期内用人单位可以随意解除劳动合同吗？"},
            {"role": "assistant", "content": (
                "不可以。根据《劳动合同法》第三十九条，劳动者在试用期间被证明不符合录用条件的，"
                "用人单位才可以解除劳动合同，并需向劳动者说明理由。若用人单位无法举证证明劳动者"
                "不符合录用条件，仅以\u201c试用期\u201d为由解除，属于违法解除，"
                "应按第八十七条规定支付赔偿金。"
            )},
        ],
    },
    # --- 工具调用：法条检索 ---
    {
        "capability": "tool_call",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPTS["tool_call"]},
            {"role": "user", "content": "请查一下关于\u201c网络侵权通知-删除规则\u201d的法条原文。"},
            _tool_call_msg("call_1", "search_law", {"keyword": "网络侵权 通知删除"}),
            {"role": "tool", "tool_call_id": "call_1", "content": (
                "《民法典》第一千一百九十五条：网络用户利用网络服务实施侵权行为的，"
                "权利人有权通知网络服务提供者采取删除、屏蔽、断开链接等必要措施。"
                "通知应当包括构成侵权的初步证据及权利人的真实身份信息。"
            )},
            {"role": "assistant", "content": (
                "已检索到《民法典》第一千一百九十五条，该条确立了\u201c通知—删除\u201d规则："
                "权利人有权通知网络服务提供者采取删除、屏蔽、断开链接等必要措施，"
                "并在通知中附初步侵权证据与真实身份信息。"
            )},
        ],
    },
    # --- 工具调用：判例检索 ---
    {
        "capability": "tool_call",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPTS["tool_call"]},
            {"role": "user", "content": "检索与\u201c职业打假人十倍赔偿\u201d相关的裁判案例。"},
            _tool_call_msg("call_2", "search_case", {"keyword": "职业打假 食品安全 十倍赔偿"}),
            {"role": "tool", "tool_call_id": "call_2", "content": (
                "检索到类案：某法院认为，知假买假者不属于为生活消费需要购买商品的消费者，"
                "其十倍赔偿请求不予支持；另有法院持相反观点。"
            )},
            {"role": "assistant", "content": (
                "类案检索显示司法实践存在分歧：多数法院认为职业打假人非\u201c为生活消费需要\u201d"
                "的消费者，故不适用《食品安全法》第一百四十八条的十倍赔偿；少数法院持肯定说。"
                "建议结合个案（是否已知、购买频率与数量）综合判断。"
            )},
        ],
    },
]


def _convert_entry(obj, capability):
    """把 {'instruction','input','output'} 或已有 {'messages'} 转为标准 messages。"""
    if "messages" in obj:
        return {"messages": obj["messages"]}
    sys_prompt = SYSTEM_PROMPTS.get(capability, SYSTEM_PROMPTS["legal_qa"])
    user = (obj.get("instruction") or "") + (
        ("\n" + obj["input"]) if obj.get("input") else ""
    )
    return {
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user.strip()},
            {"role": "assistant", "content": obj.get("output") or ""},
        ]
    }


def load_extras(path, capability, log):
    """读取补充数据（每行 JSON，可为 messages 或 instruction/input/output）。"""
    out = []
    if not path or not os.path.exists(path):
        return out
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            out.append(_convert_entry(obj, capability))
    log.info("补充数据 %d 条", len(out))
    return out


def main():
    parser = argparse.ArgumentParser(description="生成 SFT 指令数据")
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--output", type=str, default=None,
                        help="输出 JSONL（默认 config data.sft_file）")
    parser.add_argument("--input", type=str, default=None,
                        help="补充数据文件（可选，每条 instruction/input/output 或 messages）")
    parser.add_argument("--capability", type=str, default="legal_qa",
                        help="--input 补充数据所属能力（默认 legal_qa）")
    parser.add_argument("--no_builtin", action="store_true",
                        help="不写入内置示例")
    args = parser.parse_args()

    log = setup_logging("prepare-sft")
    cfg = load_config(args.config)
    output = args.output or resolve_path(cfg.get("data", {}).get("sft_file",
                                                                 "data/processed/sft.jsonl"))

    records = []
    if not args.no_builtin:
        records.extend({"messages": e["messages"]} for e in BUILTIN_EXAMPLES)
    records.extend(load_extras(args.input, args.capability, log))

    if not records:
        log.warning("没有可用样本，未写出文件。请提供 --input 或保留内置示例。")
        return

    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    log.info("已写出 %d 条 SFT 样本到 %s", len(records), output)


if __name__ == "__main__":
    main()