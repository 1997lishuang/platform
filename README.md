# 工程量清单智能计价引擎

本项目用于读取“工程量清单与计价表”，从项目特征中提取影响综合单价的指标，匹配企业价格规则库，计算 `合价 = 综合单价 * 工程量`，并输出可审计的计价结果。

## 当前能力

- 自动识别 Excel 中的清单表头
- 支持分部分项清单与措施项目清单
- 解析 `项目特征` 中的键值指标
- 使用 JSON 价格规则库匹配综合单价
- 计算综合单价、合价、单价来源
- 输出结果 Excel 与 JSON 审计文件
- 生成缺价、单位不一致、工程量异常等校验问题

## 快速运行

```powershell
python -m boq_pricing.cli `
  --input "工程招标工程量清单.xlsx" `
  --rule-source json `
  --rules "config/price_rules.sample.json" `
  --output-dir "outputs"
```

如不设置 `PYTHONPATH`，可使用：

```powershell
$env:PYTHONPATH="src"
python -m boq_pricing.cli --input "工程招标工程量清单.xlsx" --rules "config/price_rules.sample.json" --output-dir "outputs"
```

## MySQL 模式

先初始化数据库并导入规则：

```powershell
mysql -uroot -p < db/mysql/schema.sql
$env:BOQ_MYSQL_PASSWORD="your-password"
$env:PYTHONPATH="src"
python -m boq_pricing.admin.import_price_rules --json config/price_rules.sample.json
```

再从 MySQL 取价并写入审计：

```powershell
python -m boq_pricing.cli `
  --input "工程招标工程量清单.xlsx" `
  --rule-source mysql `
  --write-mysql-audit `
  --output-dir outputs
```

每次运行会生成：

- `*.priced.xlsx`：业务计价结果
- `*.audit.json`：系统审计文件
- `*.missing_rules.xlsx`：待补价格规则模板

业务填完 `*.missing_rules.xlsx` 的 `unit_price` 和 `source` 后，可导入 MySQL：

```powershell
python -m boq_pricing.admin.import_price_rules_xlsx --xlsx outputs/工程招标工程量清单.missing_rules.xlsx
```

## 架构文档

见 [docs/architecture.md](docs/architecture.md)。

SQLAlchemy 与 Alembic 说明见 [docs/sqlalchemy_alembic.md](docs/sqlalchemy_alembic.md)。

异步任务说明见 [docs/async_tasks.md](docs/async_tasks.md)。

权限与规则审批流说明见 [docs/rule_approval.md](docs/rule_approval.md)。

材料价、定额库与综合单价组成说明见 [docs/component_pricing.md](docs/component_pricing.md)。

外部模型/网络询价说明见 [docs/market_quote_sources.md](docs/market_quote_sources.md)。

## Web 控制台

前端和后端脚手架说明见 [docs/frontend_backend.md](docs/frontend_backend.md)。

## 投标报价策略

原 `smartModel` 项目已合并为平台内的“投标策略”模块，用于解析评标规则、模拟推荐报价区间、开标后回测和市场参数校准。

详见 [docs/bid_strategy.md](docs/bid_strategy.md)。

平台同时提供“动态博弈”和“单项反推”两个投标报价生成页面，用于从成本批次推导利润优先总价，并从目标总价反算清单单项报价。

后端 API：

```powershell
pip install -e ".[api,db,dev]"
$env:BOQ_MYSQL_PASSWORD="your-password"
$env:PYTHONPATH="src"
python -m boq_pricing.api.main
```

前端：

```powershell
cd frontend
pnpm install
pnpm dev
```
