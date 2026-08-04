# MySQL 部署与使用

## 数据库职责

MySQL 作为企业价格中台与计价审计库，负责保存：

- 企业综合单价规则
- 项目特征匹配条件
- 综合单价组成明细
- 材料/设备信息价
- 计价批次与逐条清单审计结果

当前实现仍保留 `feature_conditions_json` 兼容字段，同时把项目特征条件双写到 `price_rule_condition`，后续可以逐步从 JSON 匹配演进到关系索引匹配。

## 初始化与迁移

全新环境：

```powershell
mysql -uroot -p < db/mysql/schema.sql
```

已初始化过的环境：

```powershell
mysql -uroot -p < db/mysql/migrations/001_enterprise_pricing_model.sql
```

## 导入样例规则

```powershell
$env:BOQ_MYSQL_PASSWORD="your-password"
$env:PYTHONPATH="src"
python -m boq_pricing.admin.import_price_rules `
  --json config/price_rules.sample.json `
  --mysql-user root `
  --mysql-database boq_pricing `
  --tenant-code default
```

## 从 MySQL 取价

```powershell
$env:BOQ_MYSQL_PASSWORD="your-password"
$env:PYTHONPATH="src"
python -m boq_pricing.cli `
  --input "工程招标工程量清单.xlsx" `
  --rule-source mysql `
  --mysql-user root `
  --mysql-database boq_pricing `
  --tenant-code default `
  --project-name "中广核叶集区集安200MW光伏项目" `
  --region-code "AH-LA" `
  --write-mysql-audit `
  --output-dir outputs
```

## 补充规则闭环

每次运行会生成：

- `*.priced.xlsx`：业务计价结果
- `*.audit.json`：系统审计文件
- `*.missing_rules.xlsx`：待补价格规则模板

业务人员填完 `*.missing_rules.xlsx` 的 `unit_price` 和 `source` 后，导入 MySQL：

```powershell
python -m boq_pricing.admin.import_price_rules_xlsx `
  --xlsx outputs/工程招标工程量清单.missing_rules.xlsx `
  --tenant-code default
```

## 扩展原则

- 多公司/多组织：使用 `tenant_code` 隔离规则和计价批次。
- 多地区：使用 `region_code` 区分地区信息价和规则适用范围。
- 多专业：使用 `specialty` 区分建筑、安装、电气、道路等专业规则。
- 多费用类别：使用 `cost_category` 区分人工、材料、机械、措施费、其他费。
- 多版本：使用 `version + status + effective_from/effective_to` 管理规则生命周期。
- 高性能：批量取价时一次性加载候选规则到内存，避免每条清单逐行查库。

