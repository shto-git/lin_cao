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
- [x] RAGFlow REST API 适配
- [x] Markdown 导出
- [x] 完整项目文档
- [ ] FastAPI 后端服务
- [ ] 数据库持久化
- [ ] 前端管理台
- [ ] 章节草稿生成（对接 LLM）
- [ ] Word/PDF 导出
- [ ] 图表自动生成
- [ ] 审查意见闭环

## 快速开始

### 生成大纲和检索计划

```powershell
cd D:\lincao
python -m lin_cao_planner.cli samples\demo_project.json --out dist\demo
```

### 运行测试

```powershell
python -m unittest discover -s tests -v
```

### Python API 调用

```python
from lin_cao_planner.domain import ProjectInfo
from lin_cao_planner.outline import build_default_outline
from lin_cao_planner.evidence import build_retrieval_plan
from lin_cao_planner.renderer import render_outline, render_retrieval_plan

project = ProjectInfo(
    name="某县林业发展规划（2026-2030年）",
    region="某县",
    period="2026-2030年",
    level="县域级",
    planning_type="林业发展规划",
    target_words=50000,
)
outline = build_default_outline(project)
briefs = build_retrieval_plan(project, outline)
print(render_outline(outline))
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
| [docs/10-部署指南.md](docs/10-部署指南.md) | 本地部署 + 生产化部署方案 |
| [林草专业规划长文本智能编制合作需求.md](林草专业规划长文本智能编制合作需求.md) | 原始需求文档 |

## 支持的规划类型

- 林业发展规划
- 湿地保护修复规划
- 自然保护地建设管理规划
- 林草产业发展规划
- 草原保护修复规划
- 国土绿化专项规划
- 生物多样性保护规划

## 技术栈

**MVP 阶段**：
- Python 3.10+
- RAGFlow（知识底座）
- Markdown（中间格式）

**生产化阶段**：
- FastAPI + PostgreSQL + Redis
- python-docx / Pandoc（Word 导出）
- Docker Compose 部署

## 架构

```text
林草规划应用（前端管理台）
        │
        ▼
业务编排服务 lin_cao_planner
  ├── Outline Planner      — 大纲生成
  ├── Evidence Planner     — 检索计划
  ├── Generation Task      — 章节任务构建
  ├── Validation Engine    — 质检引擎
  └── RAGFlow Adapter      — 知识底座适配
        │
        ▼
RAGFlow 知识底座
  ├── 文件解析（PDF/Word/Excel）
  ├── Chunk + 向量化
  ├── 混合检索（向量 + 关键词）
  └── 引用来源追溯
```
