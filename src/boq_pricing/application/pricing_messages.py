from __future__ import annotations


def build_no_active_rule_message(
    rule_version: str | None,
    region_code: str | None,
    specialty: str | None,
    cost_category: str | None,
) -> str:
    filters = [
        f"价库规则版本={rule_version or '全部可用版本'}",
        f"计价地区={region_code or '未限定'}",
        f"专业工程={specialty or '未限定'}",
        f"费用/标段类别={cost_category or '未限定'}",
    ]
    return (
        "当前筛选条件下没有 active 状态的价格规则。"
        "请先在“价格规则库”新增或批量导入规则并审核通过，"
        "或在“价格库复核”通过市场询价记录生成规则；"
        "如果已存在规则，请将价库规则版本留空或放宽地区/专业/费用类别后重试。"
        f"筛选条件：{'，'.join(filters)}。"
    )
