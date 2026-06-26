# 林草专业规划智能编制项目

## 项目定位

本项目面向林草行业各类专业规划文本编制场景，建设"资料导入、知识增强、规划大纲管理、章节生成、图表生成、专业校核、协同修订、成果导出"的闭环能力。

核心定位：**RAGFlow 做知识底座，lin_cao_planner 做业务编排层**。

## 当前进度

- [x] 需求拆解与 MVP 定义
- [x] 开源底座选型（RAGFlow）
- [x] 业务编排层骨架代码
- [x] 规划模板系统（基础 + 湿地/自然保护地/产业）
- [x] 检索计划生成
- [x] 基础质检引擎（禁用词、来源追溯、指标冲突）
- [x] RAGFlow REST API 适配（完整 CRUD + 检索 + 对话）
- [x] 章节草稿生成模块（OpenAI-compatible LLM 调用）
- [x] 完整 Pipeline 编排（outline → retrieval → draft → quality → export）
- [x] Markdown 导出 + 全文档渲染
- [x] Word 导出模块（python-docx）
- [x] CLI 完整工作流
- [x] 完整项目文档（11 份）
- [x] 23 个单元测试全部通过
- [ ] FastAPI 后端服务
- [ ] 数据库持久化
- [ ] 前端管理台
- [ ] 图表自动生成
- [ ] 审查意见闭环

## 快速开始

### 安装

```powershell
cd D:\lincao
python -m venv venv
venv\Scripts\activate
pip install python-docx  # 可选，用于 Word 导出
```

### 生成大纲和检索计划

```powershell
python -m lin_cao_planner.cli samples\demo_project.json --out dist\demo --skip-llm
```

### 运行完整流程（含章节草稿生成）

```powershell
# 配置 LLM API Key（支持 DeepSeek、OpenAI、通义千问 等）
$env:LINCAO_LLM_API_KEY="your-api-key"
$env:LINCAO_LLM_MODEL="deepseek-chat"  # 可选，默认 deepseek-chat
$env:LINCAO_LLM_BASE_URL="https://api.deepseek.com/v1"  # 可选

python -m lin_cao_planner.cli samples\demo_project.json --out dist\output
```

### 运行测试

```powershell
python -m unittest discover -s tests -v
```

### Python API 调用

```python
from lin_cao_planner import ProjectInfo, PipelineConfig, run_pipeline

project = ProjectInfo(
    name="某县林业发展规划（2026-2030年）",
    region="某县",
    period="2026-2030年",
    level="县域级",
    planning_type="林业发展规划",
    target_words=50000,
)
config = PipelineConfig()
config.output_dir = "dist/output"

result = run_pipeline(project, config)
print(f"生成 {len(result.drafts)} 个章节草稿，{len(result.findings)} 个质检发现")
```

## 文档索引

| 文档 | 内容 |
|------|------|
| [docs/00-项目推进记录.md](docs/00-项目推进记录.md) | 项目推进日志 |
| [docs/01-需求痛点与MVP.md](docs/01-需求痛点与MVP.md) | 需求分析与 MVP 定义 |
| [docs/02-开源项目选型验证.md](docs/02-开源项目选型验证.md) | 开源底座选型对比 |
| [docs/03-技术方案.md](docs/03-技术方案.md) | 总体技术方案 |
| [docs/04-实施任务清单.md](docs/04-实施任务清单.md) | 分阶段任务清单 |
| [docs/05-API接口设计.md](docs/05-API接口设计.md) | RAGFlow 适配层 + 业务接口设计 |
| [docs/06-规划模板库.md](docs/06-规划模板库.md) | 各规划类型模板定义 |
| [docs/07-数据模型与数据库设计.md](docs/07-数据模型与数据库设计.md) | 数据库表结构 + SQLite 建表语句 |
| [docs/08-开发者指南.md](docs/08-开发者指南.md) | 环境搭建、常用命令、模块说明 |
| [docs/09-质检规则详细说明.md](docs/09-质检规则详细说明.md) | 所有质检规则的检测逻辑和扩展方式 |
| [docs/10-部署指南.md](docs/10-部署指南.md) | MVP 本地部署 + 生产化部署方案 |

## 模块说明

| 模块 | 文件 | 功能 |
|------|------|------|
| 编排入口 | `cli.py` | 命令行工具 |
| 完整流程 | `pipeline.py` | outline → retrieval → draft → quality → export |
| 大纲生成 | `outline.py` | 按规划类型生成章节树 + 字数分配 |
| 检索计划 | `evidence.py` | 为每个章节生成检索问题 |
| 章节生成 | `generator.py` | RAG-enhanced LLM 章节草稿生成 |
| 质检引擎 | `validators.py` | 禁用词、来源追溯、指标冲突检测 |
| RAGFlow 适配 | `ragflow_client.py` | RAGFlow REST API 完整封装 |
| 渲染输出 | `renderer.py` | Markdown 渲染（大纲/检索计划/质检报告/全文） |
| Word 导出 | `word_export.py` | Markdown → .docx 转换 |
| 数据对象 | `domain.py` | ProjectInfo / OutlineNode / ChapterDraft 等 |

## 支持的规划类型

- 林业发展规划（基础模板）
- 湿地保护修复规划（扩展模板）
- 自然保护地建设管理规划（扩展模板）
- 林草产业发展规划（扩展模板）
- 草原保护修复规划（基础模板）
- 国土绿化专项规划（扩展模板）
- 生物多样性保护规划（扩展模板）

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LINCAO_LLM_API_KEY` | LLM API Key | 空（返回占位草稿） |
| `LINCAO_LLM_BASE_URL` | LLM API 地址 | https://api.deepseek.com/v1 |
| `LINCAO_LLM_MODEL` | 模型名称 | deepseek-chat |
| `RAGFLOW_BASE_URL` | RAGFlow 地址 | http://localhost:9380 |
| `RAGFLOW_API_KEY` | RAGFlow API Key | 空 |
| `RAGFLOW_DATASET_ID` | 默认数据集 ID | 空 |

## 架构

```text
CLI / Python API
      │
      ▼
lin_cao_planner/pipeline.py
  ├── outline.py          — 大纲生成
  ├── evidence.py         — 检索计划
  ├── generator.py        — 章节草稿（LLM）
  ├── validators.py       — 质检引擎
  ├── ragflow_client.py   — RAGFlow 适配
  ├── renderer.py         — Markdown 渲染
  └── word_export.py      — Word 导出
        │
        ├──→ RAGFlow（知识底座）
        └──→ LLM API（OpenAI-compatible）
```
