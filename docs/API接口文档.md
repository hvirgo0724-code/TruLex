# API 接口文档

途律 · TruLex后端 API 文档。基础路径前缀 `/api/v1`，在线交互式文档见 `http://localhost:8000/docs`（Swagger UI）。

## 约定

- **认证**：除 `/auth/login`、`/auth/register`、`/healthz`、`/metrics` 外，均需 `Authorization: Bearer <JWT>` 请求头（聊天接口 `POST /chat` 与历史 `GET /chat/history` 为可选认证，未登录也可匿名使用）。
- **响应格式**：成功返回 JSON；错误返回 `{"detail": "..."}`。
- **流式接口**：`POST /chat` 使用 SSE（`text/event-stream`），事件格式见下文。

---

## 一、认证 `POST /auth/*`

### `POST /auth/login` — 登录

请求体：

```json
{ "username": "admin", "password": "admin123456" }
```

响应：

```json
{ "access_token": "<JWT>", "token_type": "bearer" }
```

### `POST /auth/register` — 注册

请求体：`{ "username": "...", "email": "...", "password": "..." }`。成功返回用户信息或直接可登录。

### `GET /auth/me` — 当前用户（需认证）

返回当前登录用户的 `id` / `username` / `email` / `is_active` 等。

---

## 二、智能对话 `POST /chat`（核心）

### `POST /chat` — 多 Agent 智能问答（SSE 流式）

请求体：

```json
{ "conversation_id": "可选，会话 thread_id，缺省新建", "message": "货物运输途中毁损，承运人要赔偿吗？" }
```

SSE 事件序列（依次返回）：

| 事件 | 数据 | 说明 |
|---|---|---|
| `token` | `{"content": "..."}` | 逐 token 输出最终答案 |
| `citations` | `{"items": [{"source","title","snippet"}]}` | 引用法条/判例列表 |
| `done` | `{"conversation_id","compliance_ok","route"}` | 结束；`route` 为命中意图（waybill/statute/case/liability/document/chat） |
| `error` | `{"message": "..."}` | 处理失败 |

**意图路由说明**（supervisor 自动识别，无需显式指定）：

| route | 触发场景 | 节点 |
|---|---|---|
| `waybill` | 审查运输合同/运单/面单 | waybill_reviewer |
| `statute` | 检索法律法规条文 | statute_retrieval |
| `case` | 检索判例/裁判文书 | case_retrieval |
| `liability` | 货损货差责任认定、赔偿计算 | liability_assessor |
| `document` | 起草法律文书 | document_writer |
| `chat` | 一般性咨询/闲聊 | compliance_guard |

所有回答最终经 `compliance_guard` 做敏感信息脱敏 + 免责声明。

### `GET /chat/history?conversation_id=...` — 历史消息

返回指定会话的消息列表：

```json
{ "conversation_id": "...", "messages": [{"id":1,"role":"user","content":"...","citations":null,"created_at":"..."}] }
```

---

## 三、运单/运输合同审查 `POST /contract/review`

### `POST /contract/review` — 运单/合同审查

请求体（二选一）：

```json
{ "text": "运输合同条款原文...", "file_path": "可选，上传文件的路径" }
```

响应：

```json
{
  "items": [
    {
      "risk_level": "high|medium|low",
      "clause": "条款定位/摘要",
      "highlight": "需高亮的原文片段",
      "suggestion": "修改建议"
    }
  ]
}
```

风险规则覆盖：保价/未保价、赔偿限额、免责条款、危险货物、超限超载、运费与留置、时效、管辖等物流特有风险。

---

## 四、知识库检索 `POST /knowledge/search`

### `POST /knowledge/search` — 向量检索

请求体：

```json
{ "query": "货损货差", "top_k": 5 }
```

响应：

```json
{ "hits": [{"score": 0.83, "source": "milvus", "text": "...", "metadata": {...}}] }
```

---

## 五、文档上传 `POST /documents/upload`

### `POST /documents/upload` — 上传文档（multipart）

`multipart/form-data` 上传 `.docx` / `.pdf` / `.txt`，返回文档元数据（id、文件名、存储路径）。

---

## 六、管理 `GET /admin/audit`

### `GET /admin/audit` — 审计日志（需管理员）

返回操作审计记录列表（操作人、动作、资源、时间、IP 等）。

---

## 七、健康与可观测性

| 端点 | 说明 |
|---|---|
| `GET /healthz` | 健康检查，返回 `{"status":"ok","service":"trullex-backend"}` |
| `GET /metrics` | Prometheus 指标 |

---

## 错误码约定

| HTTP 状态 | 含义 |
|---|---|
| 400 | 请求参数错误 |
| 401 | 未认证 / 凭证错误 |
| 403 | 无权限 / 账号禁用 |
| 404 | 资源不存在（如会话） |
| 429 | 触发限流 |
| 500 | 服务内部错误 |

---

## 调用示例（curl）

```bash
# 登录获取 token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123456"}'

# 流式对话
curl -N -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{"message":"快递丢件未保价怎么赔？"}'

# 知识库检索
curl -X POST http://localhost:8000/api/v1/knowledge/search \
  -H "Content-Type: application/json" \
  -d '{"query":"承运人责任","top_k":5}'
```
