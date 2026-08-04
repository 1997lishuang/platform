# 权限与规则审批流

## 角色

当前实现使用请求头模拟登录态：

- `x-user`：用户名，默认 `admin`
- `x-user-role`：角色，默认 `admin`
- `x-tenant-code`：租户，默认 `default`

角色权限：

- `admin`：创建、提交、审核、驳回、查看规则
- `estimator`：创建、提交、查看规则
- `reviewer`：审核、驳回、查看规则
- `viewer`：查看规则

后续接入 JWT、企业 SSO 或 RBAC 服务时，只需要替换 `api/auth.py` 中的 `get_current_user()`。

## 规则状态

```text
draft -> reviewing -> active
                  \-> rejected -> reviewing
```

只有满足以下条件的规则会参与自动取价：

- `status = active`
- `active = 1`

因此草稿、待审、驳回规则不会影响正式计价。

## API

创建草稿：

```http
POST /api/rules/drafts
```

提交审核：

```http
POST /api/rules/{rule_id}/{version}/submit
```

审核通过：

```http
POST /api/rules/{rule_id}/{version}/approve
```

驳回：

```http
POST /api/rules/{rule_id}/{version}/reject
```

按状态查看规则：

```http
GET /api/rules?status=reviewing
```

## 前端

新增 `规则审批` 页面：

- 查看待审核规则
- 通过规则
- 驳回规则

## 后续增强

1. 接入正式登录和 JWT。
2. 将角色权限从代码迁移到数据库 RBAC 表。
3. 增加审批意见必填、审批记录流水表。
4. 增加规则版本 diff。
5. 增加规则发布窗口和生效/失效日期校验。

