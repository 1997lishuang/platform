# 材料价、定额库与综合单价组成

## 目标

综合单价不再只能是一个固定数字，也可以由组成明细计算：

```text
综合单价 = Σ(组成消耗量 × 组成单价)
```

组成类型可以是：

- `labor`：人工
- `material`：材料
- `machine`：机械
- `management`：管理费
- `profit`：利润
- `tax`：税金

## 数据表

- `material_price`：材料信息价，支持地区、月份、规格、来源。
- `quota_item`：定额子目主表。
- `quota_consumption`：定额消耗量。
- `price_rule_component`：综合单价组成明细。

## 价格规则模式

`price_rule.pricing_method` 支持：

- `fixed_unit_price`：固定综合单价。
- `component_sum`：按组成明细求和。

只有审批通过后的规则，即 `status = active` 且 `active = 1`，才参与取价。

## API

导入材料价：

```http
POST /api/rules/materials
```

替换规则组成明细：

```http
PUT /api/rules/{rule_id}/{version}/components
```

组件可以手工指定单价：

```json
{
  "component_type": "labor",
  "component_name": "安装人工",
  "unit": "工日",
  "quantity": "0.2",
  "unit_price": "220",
  "price_source_type": "manual",
  "source": "企业人工单价"
}
```

也可以引用最新材料价：

```json
{
  "component_type": "material",
  "component_name": "测试钢材",
  "unit": "kg",
  "quantity": "10",
  "material_code": "MAT-COMP-001",
  "price_source_type": "material_latest"
}
```

## 后续增强

1. 定额子目自动展开为组成明细。
2. 材料价按地区、月份、供应商优先级取价。
3. 管理费、利润、税金支持费率公式。
4. 前端增加组成价编辑器和组成明细审计视图。
5. 输出 Excel 增加综合单价组成分析表。

