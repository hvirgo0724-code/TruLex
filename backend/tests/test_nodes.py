"""意图路由与敏感信息脱敏单元测试。"""
from app.agents import nodes


def test_normalize_route_waybill():
    assert nodes._normalize_route("waybill") == "waybill"
    assert nodes._normalize_route("", "帮我审查这份运输合同") == "waybill"


def test_normalize_route_statute():
    assert nodes._normalize_route("statute") == "statute"
    assert nodes._normalize_route("", "道路运输条例有哪些规定") == "statute"


def test_normalize_route_case():
    assert nodes._normalize_route("case") == "case"
    assert nodes._normalize_route("", "有没有类似判例") == "case"


def test_normalize_route_liability():
    assert nodes._normalize_route("liability") == "liability"
    assert nodes._normalize_route("", "货物毁损承运人要赔偿吗") == "liability"


def test_normalize_route_document():
    assert nodes._normalize_route("document") == "document"
    assert nodes._normalize_route("", "帮我起草一份货损索赔函") == "document"


def test_normalize_route_chat_default():
    assert nodes._normalize_route("chat") == "chat"
    assert nodes._normalize_route("", "你好") == "chat"


def test_desensitize_phone():
    text = "请联系 13812345678 处理赔偿事宜。"
    out = nodes._desensitize(text)
    assert "13812345678" not in out
    assert "手机号" in out


def test_desensitize_id_card():
    text = "身份证号 110101199001011234 已登记。"
    out = nodes._desensitize(text)
    assert "110101199001011234" not in out


def test_desensitize_email():
    text = "联系邮箱 user@example.com 处理。"
    out = nodes._desensitize(text)
    assert "user@example.com" not in out


def test_desensitize_no_pii():
    text = "承运人应承担赔偿责任。"
    assert nodes._desensitize(text) == text
