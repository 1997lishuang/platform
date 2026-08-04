"""Add MySQL table and column comments.

Revision ID: 20260722_0006
Revises: 20260721_0005
Create Date: 2026-07-22
"""

from __future__ import annotations

from typing import Final

from alembic import op
from sqlalchemy import text


revision = "20260722_0006"
down_revision = "20260721_0005"
branch_labels = None
depends_on = None


TABLE_COMMENTS: Final[dict[str, str]] = {
    "price_rule": "综合单价规则主表，存储按项目名称、项目特征、地区、专业等维度匹配的计价规则。",
    "price_rule_condition": "综合单价规则条件明细，存储项目特征字段与匹配运算条件。",
    "price_rule_component": "综合单价组成明细，存储人工、材料、机械、定额、市场询价等价格组成。",
    "feature_dictionary": "项目特征字段字典，维护特征别名、标准字段、数据类型和单位。",
    "material_price": "材料市场价库，存储按地区、月份、规格维护的材料单价。",
    "quota_item": "定额子目库，存储定额编码、名称、专业、单位和工作内容。",
    "quota_consumption": "定额消耗量明细，存储定额子目下人工、材料、机械等资源消耗。",
    "pricing_run": "计价运行批次表，记录一次工程量清单计价任务的总体结果。",
    "pricing_result": "计价结果明细表，记录每条清单项的工程量、综合单价、合价和匹配依据。",
    "pricing_task": "异步计价任务表，记录上传文件、执行进度、结果文件和任务状态。",
    "user_role": "用户角色表，存储租户内用户的审批与规则维护权限。",
    "market_price_quote": "第三方模型市场询价表，存储豆包、CloseAI、本地模型等返回的候选综合单价。",
}


COLUMN_COMMENTS: Final[dict[str, dict[str, str]]] = {
    "price_rule": {
        "id": "主键ID。",
        "tenant_code": "租户编码，用于多企业、多项目数据隔离。",
        "rule_code": "规则编码，同一租户内用于唯一识别一条综合单价规则。",
        "version": "规则版本号，用于规则发布、回滚和历史追溯。",
        "status": "规则状态，如草稿、待审批、已生效、已拒绝、已停用。",
        "project_type": "项目类型，如市政、房建、桩基等。",
        "region_code": "适用地区编码或名称。",
        "specialty": "适用专业，如土建、安装、桩基等。",
        "cost_category": "费用类别或清单分类。",
        "item_name_contains": "清单项目名称包含关键字，用于规则初筛。",
        "unit": "清单计量单位。",
        "feature_conditions_json": "项目特征匹配条件JSON，保存规格、材质、强度、施工方式等结构化条件。",
        "unit_price": "综合单价，计价时与工程量相乘得到合价。",
        "pricing_method": "计价方法，如固定综合单价、组成法、市场询价等。",
        "match_priority": "匹配优先级，数值越小优先级越高。",
        "source": "规则来源，如企业价库、历史项目、政府定额、模型询价等。",
        "active": "是否启用。",
        "created_by": "创建人账号。",
        "submitted_by": "提交审批人账号。",
        "reviewed_by": "审批人账号。",
        "reviewed_at": "审批时间。",
        "review_comment": "审批意见或驳回原因。",
        "effective_from": "规则生效开始日期。",
        "effective_to": "规则生效结束日期。",
        "created_at": "创建时间。",
        "updated_at": "最后更新时间。",
    },
    "price_rule_condition": {
        "id": "主键ID。",
        "price_rule_id": "关联的综合单价规则ID。",
        "feature_key": "项目特征标准字段名。",
        "operator": "匹配运算符，如包含、等于、范围、大于、小于。",
        "expected_value": "期望匹配值。",
        "weight": "条件权重，用于计算规则匹配置信度。",
        "created_at": "创建时间。",
    },
    "price_rule_component": {
        "id": "主键ID。",
        "price_rule_id": "关联的综合单价规则ID。",
        "component_type": "组成类型，如人工、材料、机械、管理费、利润、定额、市场询价。",
        "component_name": "组成项名称。",
        "material_code": "关联材料编码。",
        "quota_code": "关联定额编码。",
        "unit": "组成项计量单位。",
        "quantity": "组成项消耗量或系数。",
        "unit_price": "组成项单价。",
        "amount": "组成项金额，由消耗量乘以单价计算。",
        "price_source_type": "组成项价格来源类型，如手工、材料价库、定额、模型询价。",
        "source": "组成项价格来源说明。",
        "created_at": "创建时间。",
    },
    "feature_dictionary": {
        "id": "主键ID。",
        "canonical_key": "标准项目特征字段名。",
        "alias_key": "项目特征别名或原始表述。",
        "data_type": "字段数据类型，如文本、数值、范围、枚举。",
        "unit": "字段单位。",
        "active": "是否启用。",
        "created_at": "创建时间。",
    },
    "material_price": {
        "id": "主键ID。",
        "tenant_code": "租户编码。",
        "material_code": "材料编码。",
        "material_name": "材料名称。",
        "specification": "材料规格型号。",
        "region_code": "价格适用地区。",
        "unit": "材料计量单位。",
        "unit_price": "材料单价。",
        "price_month": "价格月份，格式YYYY-MM。",
        "source": "价格来源。",
        "created_at": "创建时间。",
    },
    "quota_item": {
        "id": "主键ID。",
        "tenant_code": "租户编码。",
        "quota_code": "定额编码。",
        "version": "定额版本。",
        "quota_name": "定额子目名称。",
        "specialty": "适用专业。",
        "unit": "定额计量单位。",
        "work_content": "工作内容说明。",
        "active": "是否启用。",
        "created_at": "创建时间。",
    },
    "quota_consumption": {
        "id": "主键ID。",
        "quota_item_id": "关联的定额子目ID。",
        "resource_type": "资源类型，如人工、材料、机械。",
        "resource_code": "资源编码。",
        "resource_name": "资源名称。",
        "material_code": "关联材料编码。",
        "unit": "资源计量单位。",
        "consumption": "单位定额消耗量。",
        "created_at": "创建时间。",
    },
    "pricing_run": {
        "id": "主键ID。",
        "tenant_code": "租户编码。",
        "run_code": "计价批次编码。",
        "workbook_name": "原始工程量清单文件名。",
        "project_name": "项目名称。",
        "region_code": "项目地区。",
        "rule_source": "本次计价使用的规则来源。",
        "rule_version": "本次计价使用的规则版本。",
        "item_count": "清单项总数。",
        "priced_count": "成功计价项数量。",
        "unpriced_count": "未匹配到综合单价的项数量。",
        "created_at": "创建时间。",
    },
    "pricing_result": {
        "id": "主键ID。",
        "run_id": "关联的计价批次ID。",
        "source_sheet": "来源工作表名称。",
        "source_row_number": "来源Excel行号。",
        "sequence_no": "清单序号。",
        "item_code": "清单项目编码。",
        "item_name": "清单项目名称。",
        "unit": "清单计量单位。",
        "quantity": "工程量。",
        "unit_price": "综合单价。",
        "total_price": "合价，等于综合单价乘以工程量。",
        "rule_code": "匹配到的规则编码。",
        "rule_version": "匹配到的规则版本。",
        "price_source": "综合单价来源说明。",
        "confidence": "规则匹配或模型询价置信度。",
        "features_json": "解析后的项目特征JSON。",
        "issues_json": "计价问题、缺失规则或校验提示JSON。",
        "created_at": "创建时间。",
    },
    "pricing_task": {
        "id": "主键ID。",
        "tenant_code": "租户编码。",
        "task_code": "异步任务编码。",
        "status": "任务状态，如待处理、运行中、成功、失败。",
        "progress": "任务进度百分比。",
        "message": "任务当前消息或失败原因。",
        "workbook_name": "上传的工程量清单文件名。",
        "upload_path": "上传文件存储路径。",
        "project_name": "项目名称。",
        "region_code": "项目地区。",
        "specialty": "项目专业。",
        "cost_category": "费用类别或清单分类。",
        "rule_version": "指定使用的规则版本。",
        "mysql_run_code": "生成的计价批次编码。",
        "item_count": "清单项总数。",
        "priced_count": "成功计价项数量。",
        "unpriced_count": "未计价项数量。",
        "excel_path": "计价结果Excel文件路径。",
        "missing_rules_path": "缺失规则导出文件路径。",
        "audit_path": "审计文件路径。",
        "created_at": "创建时间。",
        "started_at": "任务开始时间。",
        "finished_at": "任务结束时间。",
    },
    "user_role": {
        "id": "主键ID。",
        "tenant_code": "租户编码。",
        "username": "用户账号。",
        "display_name": "用户显示名称。",
        "role": "用户角色，如管理员、规则维护人、审批人、查看人。",
        "active": "是否启用。",
        "created_at": "创建时间。",
    },
    "market_price_quote": {
        "id": "主键ID。",
        "tenant_code": "租户编码。",
        "quote_code": "市场询价记录编码。",
        "provider": "第三方模型或服务提供方，如doubao、closeai、local。",
        "model": "调用的模型名称。",
        "item_name": "询价的清单项目名称。",
        "feature_json": "询价输入的项目特征JSON。",
        "region_code": "询价适用地区。",
        "unit": "综合单价计量单位。",
        "price_min": "模型返回的建议最低单价。",
        "price_max": "模型返回的建议最高单价。",
        "recommended_price": "模型返回的推荐综合单价。",
        "tax_included": "价格是否含税。",
        "confidence": "模型返回或系统计算的置信度。",
        "source_urls_json": "模型引用或检索到的来源链接JSON。",
        "assumptions_json": "模型价格假设条件JSON。",
        "raw_response": "模型原始响应内容。",
        "status": "询价记录状态，如待审批、已采纳、已拒绝。",
        "created_by": "创建人账号。",
        "reviewed_by": "审批人账号。",
        "review_comment": "审批意见。",
        "created_at": "创建时间。",
        "reviewed_at": "审批时间。",
    },
}


def _quote(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


def _column_definition(row: object) -> str:
    column_type = row["column_type"]
    nullable = "NULL" if row["is_nullable"] == "YES" else "NOT NULL"
    default = row["column_default"]
    extra = row["extra"] or ""
    extra = " ".join(part for part in extra.split() if part.upper() != "DEFAULT_GENERATED")
    generation_expression = row["generation_expression"]

    if generation_expression:
        stored_or_virtual = "STORED" if "STORED" in extra.upper() else "VIRTUAL"
        return f"{column_type} GENERATED ALWAYS AS ({generation_expression}) {stored_or_virtual}"

    clauses = [column_type, nullable]
    if default is not None:
        default_upper = str(default).upper()
        if default_upper.startswith("CURRENT_TIMESTAMP"):
            clauses.append(f"DEFAULT {default}")
        else:
            clauses.append(f"DEFAULT {_quote(str(default))}")
    if extra:
        clauses.append(extra)
    return " ".join(clauses)


def _apply_column_comments(comments: dict[str, dict[str, str]], *, clear: bool = False) -> None:
    bind = op.get_bind()
    for table_name, column_comments in comments.items():
        for column_name, comment in column_comments.items():
            row = bind.execute(
                text(
                    """
                    SELECT
                        COLUMN_TYPE AS column_type,
                        IS_NULLABLE AS is_nullable,
                        COLUMN_DEFAULT AS column_default,
                        EXTRA AS extra,
                        GENERATION_EXPRESSION AS generation_expression
                    FROM information_schema.columns
                    WHERE table_schema = DATABASE()
                      AND table_name = :table_name
                      AND column_name = :column_name
                    """
                ),
                {"table_name": table_name, "column_name": column_name},
            ).mappings().first()
            if row is None:
                continue
            definition = _column_definition(row)
            target_comment = "" if clear else comment
            op.execute(
                f"ALTER TABLE `{table_name}` MODIFY COLUMN `{column_name}` "
                f"{definition} COMMENT {_quote(target_comment)}"
            )


def upgrade() -> None:
    for table_name, comment in TABLE_COMMENTS.items():
        op.execute(f"ALTER TABLE `{table_name}` COMMENT = {_quote(comment)}")
    _apply_column_comments(COLUMN_COMMENTS)


def downgrade() -> None:
    _apply_column_comments(COLUMN_COMMENTS, clear=True)
    for table_name in TABLE_COMMENTS:
        op.execute(f"ALTER TABLE `{table_name}` COMMENT = ''")
