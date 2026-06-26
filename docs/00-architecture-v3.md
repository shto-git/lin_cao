# 系统架构设计 v3

> 作者：Architect Agent  
> 日期：2026-06-26  
> 状态：待 Tech Lead 评审

---

## 一、系统架构总览

```
┌──────────────────────────────────────────────────────────────┐
│                     前端 (Vue 3 via CDN)                       │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ 项目管理     │  │ 资料管理      │  │ 大纲/草稿/质检/导出   │ │
│  └──────┬──────┘  └──────┬───────┘  └──────────┬───────────┘ │
│         │               │                      │             │
│         └───────────────┴──────────────────────┘             │
│                          │ HTTP/REST + WebSocket             │
└──────────────────────────┼───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│              FastAPI 后端 (lin_cao_planner/)                   │
│  ┌──────┐ ┌───────┐ ┌────────┐ ┌──────────┐ ┌────────────┐   │
│  │server│ │outline│ │evidence│ │generator │ │ validators │   │
│  │ .py  │ │ .py   │ │ .py    │ │ .py      │ │ .py        │   │
│  └──┬───┘ └───┬───┘ └───┬────┘ └────┬─────┘ └─────┬──────┘   │
│     │         │         │           │             │          │
│  ┌──▼─────────▼─────────▼───────────▼─────────────▼──────┐  │
│  │              pipeline.py (编排器)                        │  │
│  └────────────────────────┬───────────────────────────────┘  │
│                           │                                   │
│  ┌────────────────────────▼───────────────────────────────┐  │
│  │              database.py (SQLite 持久化)                  │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
                           │
              ┌────────────▼────────────┐
              │  RAGFlow (独立部署)       │
              │  知识底座: 解析/检索/chunk │
              └─────────────────────────┘
```

---

## 二、技术选型

| 层次 | 技术 | 选型理由 |
|------|------|---------|
| **前端框架** | Vue 3 (CDN: unpkg/jsDelivr) | 渐进式框架、响应式数据绑定、组件化，不需要构建工具 |
| **UI 组件库** | Element Plus (CDN) | 专业管理台 UI，表格/表单/弹窗齐全 |
| **图表库** | ECharts 5 (CDN) | 统计图/柱状图/饼图，中文文档好 |
| **后端** | Python + FastAPI | 便于维护，已有初版经验 |
| **数据库** | SQLite (MVP) → PostgreSQL (生产) | 零部署，项目级文件数据库 |
| **知识底座** | RAGFlow (Docker) | 文档解析+向量检索+引用追溯 |
| **LLM** | GPT API (sub.zs.uy) | 不限流，用于子代理文本生成 |
| **代码执行** | Codex CLI ACP | 仅有沙箱，用于 Developer 代码编写 |

---

## 三、模块划分

### 目录结构

```
D:\lincao├── lin_cao_planner/          # 后端
│   ├── __init__.py
│   ├── server.py             # FastAPI 路由 + WebSocket
│   ├── database.py           # SQLite CRUD
│   ├── domain.py             # 数据模型定义
│   ├── outline.py            # 规划模板（9种类型）
│   ├── evidence.py           # 检索计划生成
│   ├── generator.py          # 章节草稿（LLM调用）
│   ├── validators.py         # 质检引擎
│   ├── renderer.py           # Markdown 渲染
│   ├── word_export.py        # Word 导出
│   ├── chart_engine.py       # 统计图表生成
│   ├── review.py             # 审查意见管理
│   ├── pipeline.py           # 完整流程编排
│   └── ragflow_client.py     # RAGFlow REST 适配器
├── static/                    # 前端
│   ├── index.html            # 主页面（Vue 3 挂载）
│   ├── app.js                # Vue 应用 + 路由 + API 调用
│   ├── style.css             # 全局样式
│   └── components/           # Vue 组件目录（如需要）
├── tests/                     # 测试
│   ├── test_api.py
│   ├── test_database.py
│   ├── test_outline.py
│   ├── test_generator.py
│   └── test_validators.py
├── docs/                      # 文档
├── data/                      # SQLite 数据库 + 上传文件
└── dist/                      # 导出结果
```

### 模块职责

| 模块 | 职责 | 关键函数 |
|------|------|---------|
| `server.py` | HTTP/WebSocket 路由 | `create_project`, `generate_draft`, `export_markdown` |
| `database.py` | 数据持久化 | CRUD for projects/documents/drafts/reviews |
| `outline.py` | 规划模板 | `build_outline()`, `_select_template()` |
| `evidence.py` | 检索计划 | `build_retrieval_plan()`, `EvidenceChunk` |
| `generator.py` | LLM 草稿生成 | `generate_chapter_draft()`, `expand_draft()`, `compress_draft()` |
| `validators.py` | 质检 | `validate_document()`, `check_metric_consistency()` |
| `renderer.py` | Markdown 渲染 | `render_full_document()` |
| `word_export.py` | Word 导出 | `export_full_document()` |
| `chart_engine.py` | 图表生成 | `svg_bar_chart()`, `svg_pie_chart()`, `generate_charts_svg()` |
| `review.py` | 审查意见 | `submit_review()`, `check_review_resolution()` |
| `pipeline.py` | 流程编排 | `run_pipeline()` |
| `ragflow_client.py` | RAGFlow 适配 | `create_dataset()`, `retrieve_chunks()` |

---

## 四、API 接口规划

### 项目管理
```
POST   /api/v1/projects                    创建项目
GET    /api/v1/projects                    项目列表
GET    /api/v1/projects/{id}               项目详情
DELETE /api/v1/projects/{id}               删除项目
```

### 资料管理
```
POST   /api/v1/projects/{id}/documents     上传资料
GET    /api/v1/projects/{id}/documents     资料列表
DELETE /api/v1/projects/{id}/documents/{id} 删除资料
```

### 大纲与任务
```
POST   /api/v1/projects/{id}/outline/generate  生成大纲
GET    /api/v1/projects/{id}/outline           获取大纲
POST   /api/v1/projects/{id}/tasks/generate    生成检索任务
GET    /api/v1/projects/{id}/tasks              任务列表
```

### 草稿与质检
```
POST   /api/v1/projects/{id}/tasks/{id}/generate-draft  生成草稿
POST   /api/v1/projects/{id}/tasks/{id}/expand          扩写
POST   /api/v1/projects/{id}/tasks/{id}/compress        压缩
POST   /api/v1/projects/{id}/tasks/{id}/rewrite         重写
PUT    /api/v1/projects/{id}/drafts/{id}                保存编辑
POST   /api/v1/projects/{id}/quality-check              质检
GET    /api/v1/projects/{id}/metrics                     指标一致性
```

### 审查
```
POST   /api/v1/projects/{id}/reviews          提交审查意见
GET    /api/v1/projects/{id}/reviews          审查列表
PUT    /api/v1/projects/{id}/reviews/{id}     更新状态
GET    /api/v1/projects/{id}/reviews/status   整体审查状态
```

### 导出与图表
```
POST   /api/v1/projects/{id}/export/markdown  导出 Markdown
POST   /api/v1/projects/{id}/export/word       导出 Word
GET    /api/v1/projects/{id}/charts             统计图表
```

### WebSocket
```
WS     /ws/progress/{project_id}               实时进度推送
```

---

## 五、数据库 Schema

```sql
-- 项目表
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    region TEXT NOT NULL,
    period TEXT NOT NULL,
    planning_type TEXT NOT NULL,
    level TEXT DEFAULT '',
    target_words INTEGER DEFAULT 50000,
    owner_department TEXT DEFAULT '',
    drafting_unit TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    ragflow_dataset_id TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- 资料表
CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    file_name TEXT NOT NULL,
    file_path TEXT,
    file_type TEXT,
    file_size INTEGER,
    source_unit TEXT,
    publish_year INTEGER,
    applicable_region TEXT,
    applicable_planning_types TEXT,
    is_formal_reference INTEGER DEFAULT 1,
    category TEXT,
    ragflow_document_id TEXT,
    parse_status TEXT DEFAULT 'pending',
    chunk_count INTEGER,
    description TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- 大纲节点表
CREATE TABLE outline_nodes (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    parent_id TEXT REFERENCES outline_nodes(id),
    title TEXT NOT NULL,
    level INTEGER NOT NULL,
    target_words INTEGER,
    sort_order INTEGER,
    requirements TEXT,
    required_evidence_types TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- 章节任务表
CREATE TABLE section_tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    outline_id TEXT NOT NULL REFERENCES outline_nodes(id),
    title_path TEXT,
    target_words INTEGER,
    retrieval_queries TEXT,
    required_evidence_types TEXT,
    writing_constraints TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT (datetime('now'))
);

-- 章节草稿表
CREATE TABLE chapter_drafts (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    outline_id TEXT NOT NULL REFERENCES outline_nodes(id),
    title TEXT,
    content TEXT,
    word_count INTEGER,
    evidence_ids TEXT,
    status TEXT DEFAULT 'draft',
    version INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- 质检报告表
CREATE TABLE quality_reports (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    status TEXT DEFAULT 'completed',
    total_findings INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    warning_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

-- 质检发现表
CREATE TABLE quality_findings (
    id TEXT PRIMARY KEY,
    report_id TEXT NOT NULL REFERENCES quality_reports(id),
    severity TEXT NOT NULL,
    code TEXT NOT NULL,
    message TEXT NOT NULL,
    location TEXT,
    suggestion TEXT,
    status TEXT DEFAULT 'open',
    created_at TEXT DEFAULT (datetime('now'))
);

-- 审查意见表
CREATE TABLE reviews (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    chapter_id TEXT,
    severity TEXT DEFAULT 'info',
    content TEXT,
    suggestion TEXT,
    status TEXT DEFAULT 'open',
    reviewer TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    resolved_at TEXT
);

-- 导出任务表
CREATE TABLE export_tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    format TEXT NOT NULL,
    file_path TEXT,
    status TEXT DEFAULT 'pending',
    error_message TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT
);
```

---

## 六、前端组件树

```
App (Vue 3)
├── NavBar (顶部导航: 项目名 + 菜单)
├── ProjectList (项目列表页)
│   ├── CreateProjectModal (新建项目弹窗)
│   └── ProjectCard (项目卡片)
├── ProjectDetail (项目详情页)
│   ├── DocumentPanel (资料管理)
│   │   ├── UploadZone (上传区)
│   │   └── DocumentList (资料列表)
│   ├── OutlinePanel (大纲视图)
│   │   ├── OutlineTree (树形大纲)
│   │   └── ChapterNode (章节节点)
│   ├── TaskPanel (任务视图)
│   │   ├── TaskList (任务列表)
│   │   └── TaskCard (任务卡片 + 生成按钮)
│   ├── DraftPanel (草稿视图)
│   │   ├── DraftList (草稿列表)
│   │   ├── DraftEditor (TinyMCE 编辑器)
│   │   └── DraftActions (保存/重写/扩写/压缩)
│   ├── QualityPanel (质检报告)
│   │   ├── QualitySummary (统计)
│   │   └── FindingList (问题列表)
│   ├── ReviewPanel (审查意见)
│   │   ├── ReviewForm (提交审查)
│   │   └── ReviewList (审查列表)
│   └── ExportPanel (导出)
│       ├── ExportMarkdownBtn
│       ├── ExportWordBtn
│       └── ChartViewer (图表)
└── ProgressBar (WebSocket 进度条)
```

---

## 七、关键设计决策

### 7.1 前端框架：Vue 3 via CDN

**选择理由**：
- 不需要 Node/npm/构建工具
- 响应式数据绑定，表单交互简单
- 组件化开发，便于维护
- Element Plus 提供专业管理台组件

**引入方式**：
```html
<script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>
<script src="https://unpkg.com/element-plus"></script>
```

### 7.2 后端保持 FastAPI

**选择理由**：
- 已有初版经验，团队熟悉
- 自动生成 API 文档
- 异步支持（WebSocket 进度推送）
- Pydantic 数据验证

### 7.3 数据库：SQLite → PostgreSQL

**MVP 用 SQLite**：零部署，文件数据库
**生产迁移 PostgreSQL**：并发写入支持

迁移路径：SQLAlchemy 抽象层 → 切换连接字符串即可

### 7.4 LLM 调用

| 用途 | 方式 | 备注 |
|------|------|------|
| 子代理文本生成 | GPT API (sub.zs.uy) | 不限流，并发 2 |
| Developer 代码编写 | Codex CLI ACP | 有沙箱，并发 1 |
| 章节草稿 | 通过后端 server.py 调用 GPT API | 不直接在前端调用 |

---

## 八、风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| Vue 3 CDN 加载慢 | 首屏延迟 | 国内 jsDelivr 镜像 |
| SQLite 并发写入 | 数据丢失 | 生产迁移 PostgreSQL |
| GPT API 不可用 | 子代理失败 | 主代理兜底执行 |
| RAGFlow 部署复杂 | 无法导入资料 | 提供 Docker Compose 一键启动 |
| 前端框架升级 | 后续维护成本 | Vue 3 LTS 版本，API 稳定 |
