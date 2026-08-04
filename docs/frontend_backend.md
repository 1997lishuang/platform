# 前后端脚手架方案

## 前端

当前前端使用：

- Vue 3
- Vite
- TypeScript
- Pinia
- Vue Router
- Axios
- @lucide/vue

目录：

```text
frontend/
  src/
    api/       API 客户端
    views/     业务页面
    App.vue    应用框架
```

启动：

```powershell
cd frontend
pnpm install
pnpm dev
```

或使用脚本：

```powershell
scripts/start_frontend.cmd
```

默认代理 `/api` 到 `http://127.0.0.1:8000`。

## 后端

当前后端核心引擎不依赖 Web 框架，便于 CLI、API、任务队列复用。

Web API 采用 FastAPI 脚手架风格：

```text
src/boq_pricing/api/
  main.py          FastAPI 应用入口
  dependencies.py 依赖注入
  schemas.py      Pydantic 入参/出参
  routes/         路由模块
```

安装：

```powershell
pip install -e ".[api,db,dev]"
```

启动：

```powershell
$env:BOQ_MYSQL_PASSWORD="your-password"
$env:PYTHONPATH="src"
python -m boq_pricing.api.main
```

或使用脚本：

```powershell
$env:BOQ_MYSQL_PASSWORD="your-password"
scripts/start_api.cmd
```

接口文档：

```text
http://127.0.0.1:8000/api/docs
```

## 后端是否能用成熟脚手架

可以，而且建议这样做。当前项目已经采用成熟脚手架的分层方式：

- FastAPI：HTTP API、OpenAPI 文档、依赖注入
- Pydantic：接口模型校验
- SQLAlchemy/Alembic：当前已经接入，用于 ORM 仓储和迁移管理
- Celery/RQ：后续处理大文件、OCR、批量计价等异步任务
- Redis：规则缓存、任务状态、幂等锁

当前默认使用 SQLAlchemy 仓储，MySQL CLI 仓储仍作为 fallback 保留。领域层、应用层、CLI 和 API 共用同一套计价链路。

## 推荐下一阶段

1. 接入正式 JWT/企业 SSO 登录。
2. 增加材料价、定额库、综合单价组成计算。
3. 引入 Redis 做规则缓存和任务状态缓存。
4. 将 FastAPI BackgroundTasks 替换为 Celery/RQ。
5. 增加 API 自动化测试和前端端到端测试。
