# 林草专业规划智能编制项目

本仓库当前用于推进“林草专业规划长文本智能编制”项目的前期落地工作。

当前已完成三件事：

1. 读取并拆解需求文档：`林草专业规划长文本智能编制合作需求.md`。
2. 核对开源底座：已把 RAGFlow 作为资料解析、知识库、检索与引用追溯的优先参考项目，源码位于 `reference_repos/ragflow`。
3. 搭建首版业务编排层：`lin_cao_planner`，用于规划大纲、章节任务、检索计划、基础质检与 RAGFlow API 适配。

## 目录

```text
docs/
  00-项目推进记录.md
  01-需求痛点与MVP.md
  02-开源项目选型验证.md
  03-技术方案.md
  04-实施任务清单.md
lin_cao_planner/
  domain.py
  outline.py
  evidence.py
  validators.py
  ragflow_client.py
  renderer.py
  cli.py
samples/
  demo_project.json
tests/
  test_pipeline.py
```

## 快速验证

生成一个示例项目的大纲和章节检索任务：

```powershell
python -m lin_cao_planner.cli samples\demo_project.json --out dist\demo
```

运行测试：

```powershell
python -m unittest discover -s tests -v
```

## 当前定位

本项目不直接替代 RAGFlow，也不在 RAGFlow 上硬改业务逻辑。RAGFlow 更适合做资料解析、知识库、chunk、检索、引用追溯；本项目补齐林草规划编制需要的业务层：

- 规划项目上下文
- 规划类型模板
- 章节级长文本编排
- 章节检索计划
- 证据引用要求
- 专业术语、口径和数字一致性校验
- 图表与成果导出任务清单

后续如果进入工程开发阶段，建议先用“RAGFlow + 独立业务服务”的方式试点，确认业务流程跑通后再决定是否做深度二开。
