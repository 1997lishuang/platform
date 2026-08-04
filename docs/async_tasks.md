# 异步计价任务

## 目标

上传工程量清单后，API 立即返回任务号，计价过程在后台执行，前端通过轮询查询任务状态。这样大文件、复杂规则匹配、OCR 或后续 AI 解析不会阻塞 HTTP 请求。

## 状态流转

```text
pending -> running -> succeeded
                  \-> failed
```

状态保存在 `pricing_task` 表：

- `task_code`：任务号
- `status`：任务状态
- `progress`：进度百分比
- `message`：当前提示或失败原因
- `mysql_run_code`：成功后关联的审计批次
- `excel_path`、`missing_rules_path`、`audit_path`：输出文件路径

## API

创建异步任务：

```http
POST /api/pricing/tasks
Content-Type: multipart/form-data
```

查询任务状态：

```http
GET /api/pricing/tasks/{task_code}?tenant_code=default
```

查看最近任务：

```http
GET /api/pricing/tasks?tenant_code=default&limit=20
```

## 当前实现

当前使用 FastAPI `BackgroundTasks` 执行后台任务，适合单机部署和 MVP 阶段。任务状态已经落 MySQL，前端刷新后仍可查询。

## 后续扩展

当并发量或文件体积上来后，可替换为：

- Redis + RQ
- Celery + Redis/RabbitMQ
- Dramatiq
- 企业已有任务调度平台

替换时保留 `PricingTaskRepository` 和 `PricingTaskRunner` 的接口，API 和前端不用大改。

