# SQLAlchemy 与 Alembic

## 当前状态

后端数据库访问已经支持 SQLAlchemy：

- `DatabaseConfig`：数据库连接配置
- `create_session_factory`：连接池与 Session 工厂
- `orm_models.py`：关系模型映射
- `SqlAlchemyPriceRuleRepository`：规则库仓储
- `SqlAlchemyPricingAuditWriter`：计价审计写入
- `db/alembic`：Alembic 迁移目录

旧的 `mysql.exe` CLI 仓储仍保留，可作为本机驱动不可用时的 fallback。

## 运行迁移

首次全新建库后：

```powershell
$env:BOQ_MYSQL_PASSWORD="your-password"
.venv\Scripts\alembic.exe upgrade head
```

如果数据库已经通过旧 SQL 脚本建好，不要重复建表，执行：

```powershell
$env:BOQ_MYSQL_PASSWORD="your-password"
.venv\Scripts\alembic.exe stamp head
```

查看当前版本：

```powershell
$env:BOQ_MYSQL_PASSWORD="your-password"
.venv\Scripts\alembic.exe current
```

## 使用 SQLAlchemy 仓储

CLI 默认已经使用 SQLAlchemy：

```powershell
$env:BOQ_MYSQL_PASSWORD="your-password"
.venv\Scripts\python.exe -m boq_pricing.cli `
  --input "工程招标工程量清单.xlsx" `
  --rule-source mysql `
  --db-backend sqlalchemy `
  --write-mysql-audit
```

需要回退到旧 CLI 仓储时：

```powershell
.venv\Scripts\python.exe -m boq_pricing.cli `
  --input "工程招标工程量清单.xlsx" `
  --rule-source mysql `
  --db-backend cli
```

## 后续建议

1. 新增迁移只通过 Alembic 创建，不再手写并直接执行生产 SQL。
2. API 层只依赖 Repository，不直接写 SQL。
3. 大批量导入规则可加批处理写入，当前规则量不大时通用 upsert 更容易测试和维护。
4. 后续引入 Redis 后，可以把 `SqlAlchemyPriceRuleRepository.load()` 的结果按租户、地区、专业、版本缓存。

