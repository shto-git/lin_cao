# API 接口设计

本文档描述林草规划系统的 API 接口设计，包括：
- RAGFlow 知识底座适配层接口（已实现）
- 林草规划业务服务接口（待实现）

---

## 一、RAGFlow 适配层接口

源码位置：`lin_cao_planner/ragflow_client.py`

### 1.1 创建知识库

```
POST /api/v1/datasets
```

业务层封装：`RagflowClient.create_dataset()`

| 参数 | 类型 | 说明 |
|------|------|------|
| name | string | 知识库名称，建议格式：`{区域}_{规划类型}_{年份}` |
| description | string | 知识库描述 |
| chunk_method | string | 分块方法：`naive`、`manual`、`qa`、`paper`、`book`、`laws`、`presentation`、`picture`、`one`、`knowledge_graph`、`table`、`resume`、`tag` |

### 1.2 上传资料

```
POST /api/v1/datasets/{dataset_id}/documents
```

业务层封装：待实现（当前 ragflow_client 未封装此接口，需补充）

| 参数 | 类型 | 说明 |
|------|------|------|
| dataset_id | string | 知识库 ID |
| file | multipart | 支持 Word、PDF、Excel、Markdown、TXT、HTML 等 |

### 1.3 触发解析

```
POST /api/v1/datasets/{dataset_id}/chunks
```

业务层封装：`RagflowClient.parse_documents()`

| 参数 | 类型 | 说明 |
|------|------|------|
| dataset_id | string | 知识库 ID |
| document_ids | list[string] | 待解析文档 ID 列表 |

### 1.4 检索 Chunk

```
POST /api/v1/retrieval
```

业务层封装：`RagflowClient.retrieve_chunks()`

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| question | string | 必填 | 检索问题 |
| dataset_ids | list[string] | 必填 | 知识库 ID 列表 |
| page | int | 1 | 页码 |
| page_size | int | 8 | 每页返回数量 |
| similarity_threshold | float | 0.2 | 相似度阈值 |
| vector_similarity_weight | float | 0.3 | 向量相似度权重（1为纯向量，0为纯关键词） |
| keyword | bool | True | 是否启用关键词检索 |
| highlight | bool | False | 是否高亮匹配片段 |
| metadata_condition | dict | None | 元数据过滤条件 |

返回字段说明：

```json
{
  "code": 0,
  "data": {
    "chunks": [
      {
        "content": "chunk 文本内容",
        "document_id": "文档ID",
        "document_name": "文件名",
        "similarity": 0.85,
        "vector_similarity": 0.80,
        "term_similarity": 0.90,
        "positions": [[页码, 行号], ...],
        "chunk_id": "chunk唯一标识"
      }
    ],
    "total": 总数量
  }
}
```

### 1.5 错误处理

`RagflowClient` 统一抛出 `RagflowError`，包含以下场景：

- HTTP 错误（非 2xx 响应）
- 网络不可达
- 返回非 JSON 数据
- RAGFlow 业务错误码（code != 0）

---

## 二、业务服务接口（待实现）

未来 FastAPI 业务服务接口规划。

### 2.1 项目管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/projects` | 创建规划项目 |
| GET | `/api/v1/projects` | 查询项目列表 |
| GET | `/api/v1/projects/{project_id}` | 获取项目详情 |
| PUT | `/api/v1/projects/{project_id}` | 更新项目信息 |
| DELETE | `/api/v1/projects/{project_id}` | 删除项目 |
| POST | `/api/v1/projects/{project_id}/clone` | 复制项目 |

### 2.2 资料管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/projects/{project_id}/documents` | 上传资料 |
| GET | `/api/v1/projects/{project_id}/documents` | 列出项目资料 |
| DELETE | `/api/v1/projects/{project_id}/documents/{doc_id}` | 删除资料 |
| POST | `/api/v1/projects/{project_id}/documents/{doc_id}/reparse` | 重新解析 |

### 2.3 大纲管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/projects/{project_id}/outline/generate` | 自动生成大纲 |
| GET | `/api/v1/projects/{project_id}/outline` | 获取当前大纲 |
| PUT | `/api/v1/projects/{project_id}/outline` | 更新大纲（人工调整） |
| POST | `/api/v1/projects/{project_id}/outline/validate` | 校验大纲完整性 |

### 2.4 章节任务

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/projects/{project_id}/tasks/generate` | 生成章节检索和写作任务 |
| GET | `/api/v1/projects/{project_id}/tasks` | 获取任务列表 |
| GET | `/api/v1/projects/{project_id}/tasks/{task_id}` | 获取任务详情（含证据包） |
| POST | `/api/v1/projects/{project_id}/tasks/{task_id}/generate-draft` | 生成章节草稿 |
| POST | `/api/v1/projects/{project_id}/tasks/{task_id}/rewrite` | 重写章节 |

### 2.5 质检

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/projects/{project_id}/quality-check` | 执行质检 |
| GET | `/api/v1/projects/{project_id}/quality-check/{report_id}` | 获取质检报告 |

### 2.6 导出

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/projects/{project_id}/export/markdown` | 导出 Markdown |
| POST | `/api/v1/projects/{project_id}/export/word` | 导出 Word |
| POST | `/api/v1/projects/{project_id}/export/pdf` | 导出 PDF |

---

## 三、配置项

RAGFlow 连接配置（建议通过环境变量或配置文件管理）：

```env
RAGFLOW_BASE_URL=http://localhost:9380
RAGFLOW_API_KEY=your-api-key-here
RAGFLOW_TIMEOUT_SECONDS=60
```

业务服务配置：

```env
DATABASE_URL=postgresql://user:pass@localhost:5432/lin_cao
REDIS_URL=redis://localhost:6379/0
STORAGE_PATH=./storage
LOG_LEVEL=INFO
```
