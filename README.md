# 途律 · TruLex

基于「领域法律知识库（Milvus 混合检索 + Neo4j 法条关系图）+ LangGraph 多 Agent + 企业级检索/记忆/观测底座」的**途律 · TruLex**系统。前后端分离，全栈 Docker 化。

## 产品能力

- **运单/运输合同审查**：识别保价/未保价、赔偿限额、免责、危险货物、超限超载、运费、时效、管辖等物流特有法律风险。
- **货损货差责任认定**：综合检索法条与判例，研判承运人责任归属、免责事由与赔偿计算（援引民法典第 832/833 条等）。
- **物流法规检索**：覆盖民法典运输合同章、道路运输条例、快递暂行条例、邮政法、海商法、铁路法、民用航空法、危险货物道路运输安全管理办法。
- **物流判例检索**：类案联想，结合 Neo4j 法条—案由—运输方式关系图。
- **物流法律文书生成**：货物运输合同、货损索赔函、律师函、起诉状等。

## 目录结构

```
trullex/
├── docker-compose.yml     # 全栈编排（MySQL/PG/Redis/Milvus/Neo4j/Jaeger/前后端/训练）
├── .env.example           # 环境变量契约（单一事实来源）
├── backend/               # FastAPI + LangGraph 多 Agent
├── frontend/              # Vue3 + TypeScript + Element Plus
├── training/              # Unsloth 训练三阶段（PT/SFT/DPO）+ 评估 + vLLM 部署
└── docs/                  # PRD / 架构 / 开发 / API / 数据语料 文档
```

## 文档导航

- [产品需求文档](docs/产品需求文档.md)
- [系统架构文档](docs/系统架构文档.md)
- [项目开发文档](docs/项目开发文档.md)
- [API 接口文档](docs/API接口文档.md)
- [数据语料说明](docs/数据语料说明.md)

## 快速启动

```bash
cp .env.example .env        # 填入 API_KEY 等
docker compose up -d        # 起中间件 + 前后端
```

首次启动会自动创建默认管理员 `admin` / `admin123456`，也可在登录页注册普通用户。

## 知识库入库

```bash
# 1. 生成物流法律结构化语料
docker compose exec -T backend python scripts/generate_rag_data.py
# 2. 入库向量库 + 图库
docker compose exec -T backend python scripts/ingest_milvus.py
docker compose exec -T backend python scripts/ingest_neo4j.py
```

语料覆盖公路货运、快递寄递、铁路、航空、水运海商、仓储、多式联运、危险货物运输等全领域。

> 提示：修改 `.env`（如更换 `API_KEY`）后，需用 `docker compose up -d backend` 重新创建容器才能生效——`docker compose restart` 不会重读 `env_file`（环境变量是容器创建时的快照）。

## 环境变量契约

核心键（详见 `.env.example`）：

| 键 | 用途 |
|---|---|
| `API_KEY` / `BASE_URL` / `MODEL_NAME` | LLM（DashScope，兼容 OpenAI 协议） |
| `EMBEDDING_MODEL` / `EMBEDDING_DIM` | `qwen3.7-text-embedding`，1024 维 |
| `MYSQL_URL` | 业务库（SQLAlchemy async，`mysql+aiomysql`） |
| `DB_URI` | 记忆库（LangGraph `PostgresSaver/Store`，`postgresql+psycopg2`） |
| `REDIS_URL` / `MILVUS_URI` / `NEO4J_URI` | 缓存 / 向量（稠密+BM25 稀疏）/ 图 |
| `JWT_SECRET` 等 | 认证 |

## API 概览（前缀 `/api/v1`）

`POST /auth/login` · `POST /auth/register` · `GET /auth/me` · `POST /chat`（SSE 流式）· `GET /chat/history` · `POST /contract/review`（运单审查）· `POST /knowledge/search` · `POST /documents/upload` · `GET /admin/audit` · `GET /healthz` · `GET /metrics`

## 训练三阶段

见 `training/`：`prepare_*`（数据）→ `train_pt` → `train_sft` → `train_dpo` → `evaluate` → `merge_export` → `deploy_vllm`。

## 本机运行与验证

已安装 Docker Desktop 时，在项目根目录执行：

```powershell
docker compose up -d --build
```

前端：http://localhost:8080 ，后端文档：http://localhost:8000/docs 。
默认管理员为 `admin` / `admin123456`。

前端开发（后端仍由 Docker 提供）：

```powershell
cd frontend
npm install
npm run dev
```

验证：`cd frontend; npm run build`；后端执行 `docker compose exec -T backend pytest -q`。

## 测试

后端单元测试位于 `backend/tests/`，分两层：

- **纯逻辑测试**（无外部依赖，可直接在宿主机运行）：`test_extraction.py`（实体/关系抽取）、`test_nodes.py`（意图路由/脱敏）、`test_agents.py`（节点行为，FakeLLM 桩）。
  ```bash
  cd backend && pytest tests/test_extraction.py tests/test_nodes.py tests/test_agents.py -q
  ```
- **集成测试**（需完整后端依赖，在容器内运行）：`test_health.py`、`test_chat.py`。
  ```bash
  docker compose exec -T backend pytest -q
  ```

聊天使用异步 PostgreSQL 检查点。SSE 在合规处理完成后回传最终答案，避免将内部路由词及未脱敏内容发送到页面。

> 免责声明：本系统输出由 AI 生成，仅供法律研究参考，不构成正式法律意见；正式法律判断须以现行法律法规及司法实践为准。
