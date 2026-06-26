# Tech Lead 评审报告

> 评审人：Tech Lead Agent  
> 日期：2026-06-26  
> 输入：PRD v2 + 技术选型 v2  
> 状态：✅ 通过（附修改建议）

---

## 一、PRD v2 评审

### 1.1 评审结论：✅ 通过

**范围合理**。从 V1 的"大而全"裁剪为 7 个 MUST HAVE，聚焦"林业发展规划"单一类型，是正确的 MVP 决策。

### 1.2 验收标准检查

| 功能 | 验收标准可测试？ | 建议 |
|------|----------------|------|
| M1 项目管理 | ✅ 可测试 | — |
| M2 规划模板 | ✅ 可测试 | — |
| M3 资料入库 | ✅ 可测试 | — |
| M4 章节检索任务 | ✅ 可测试 | — |
| M5 章节草稿生成 | ⚠️ 需补充 | 建议增加："草稿字数在 3000-8000 范围内" |
| M6 基础质检 | ✅ 可测试 | — |
| M7 Markdown 导出 | ✅ 可测试 | — |

### 1.3 遗漏补充

1. **M5 章节草稿生成**缺少"缺资料时的行为"定义：
   - 建议：当 RAGFlow 检索返回 0 条结果时，草稿开头应插入 `[缺资料提示：本章节未检索到相关依据，请补充以下类型资料：xxx]`
   
2. **M3 资料入库**缺少"上传失败处理"：
   - 建议：上传非支持格式时返回明确错误信息

3. **缺少 WebSocket 进度推送**：
   - 章节草稿生成需要 10-30 秒，前端需要实时进度反馈
   - 建议增加 M8：WebSocket 进度推送（Must Have）

### 1.4 用户故事完整性

用户故事覆盖了核心流程，但缺少：
- **资料删除**：用户上传了错误资料时需要能删除
- **草稿手动编辑**：生成的草稿用户需要在界面上直接修改

---

## 二、技术选型评审

### 2.1 全部通过 ✅

7 个决策点全部正确，无需更改。补充说明：

| 决策 | 补充建议 |
|------|---------|
| RAGFlow | 确认可用 RAGFlow 的"轻量模式"（无需 ES），或评估 ChromaDB 作为备选 |
| LLM 路由 | 建议增加"模型不可用自动降级"：GPT-5.5 不可用时自动切换 DeepSeek |
| 前端 | Phase 1 静态 HTML 够用，不需要提前引入 Vue 3 |
| 数据库 | SQLite → PostgreSQL 迁移路径已确认 |

### 2.2 技术债务可接受

所有标注的技术债务都是合理的，不影响 MVP 交付。

---

## 三、可执行契约

### M1 项目管理

```yaml
文件归属:
  - lin_cao_planner/server.py (API 端点)
  - lin_cao_planner/database.py (CRUD 操作)
  - static/index.html (前端页面)

API 端点:
  POST /api/v1/projects
    输入: { name, region, period, planning_type, level, target_words, owner_department, drafting_unit }
    输出: { id, name, ... , created_at }
    
  GET /api/v1/projects
    输出: [ { id, name, region, status, created_at }, ... ]
    
  GET /api/v1/projects/{project_id}
    输出: { id, name, ... , ragflow_dataset_id }

依赖约束:
  - database.py (Database 类)
  - RAGFlow Client (创建数据集)

验收条件:
  - [ ] POST 创建项目返回 201
  - [ ] GET 列表返回所有项目
  - [ ] 创建时自动生成 ragflow_dataset_id
```

### M2 规划模板

```yaml
文件归属:
  - lin_cao_planner/outline.py (模板定义 + 生成逻辑)

接口:
  def build_outline(planning_type: str, target_words: int) -> list[OutlineNode]
    输入: planning_type="林业发展规划", target_words=50000
    输出: 9 个 OutlineNode，含子节点

  GET /api/v1/projects/{project_id}/outline/generate
    输出: [ { id, title, level, target_words, children: [...] }, ... ]

验收条件:
  - [ ] 林业发展规划生成 9 章
  - [ ] 总字数分配 = target_words（误差 ±5%）
  - [ ] 每章有 requirements 和 required_evidence_types
```

### M3 资料入库

```yaml
文件归属:
  - lin_cao_planner/server.py (上传 API)
  - lin_cao_planner/ragflow_client.py (RAGFlow 对接)

API 端点:
  POST /api/v1/projects/{project_id}/documents
    输入: multipart file upload
    输出: { id, file_name, file_type, parse_status, chunk_count }
    
  GET /api/v1/projects/{project_id}/documents
    输出: [ { id, file_name, file_type, parse_status, chunk_count, description }, ... ]
    
  DELETE /api/v1/projects/{project_id}/documents/{doc_id}
    输出: { success: true }

依赖约束:
  - RAGFlow Client
  - 支持格式: pdf, docx, xlsx, md, txt

验收条件:
  - [ ] 上传 PDF/Word 成功返回 parse_status=completed
  - [ ] 上传非支持格式返回 400 错误
  - [ ] DELETE 删除后 GET 列表不再包含
  - [ ] 上传后 RAGFlow 能检索到内容
```

### M4 章节检索任务

```yaml
文件归属:
  - lin_cao_planner/evidence.py (检索计划生成)
  - lin_cao_planner/ragflow_client.py (RAGFlow 检索)

接口:
  def build_retrieval_plan(outline: list[OutlineNode]) -> list[SectionBrief]
    
  POST /api/v1/projects/{project_id}/tasks/generate
    输出: [ { id, outline_id, title_path, target_words, retrieval_queries, required_evidence_types }, ... ]

依赖约束:
  - outline.py (需要大纲)
  - ragflow_client.py (需要检索)

验收条件:
  - [ ] 每章生成 3-5 条检索问题
  - [ ] 检索问题覆盖 policy/standard/data/case 类型
  - [ ] 调用 RAGFlow retrieval 返回结果
```

### M5 章节草稿生成

```yaml
文件归属:
  - lin_cao_planner/generator.py (LLM 调用 + 草稿组装)
  - lin_cao_planner/server.py (API)

API 端点:
  POST /api/v1/projects/{project_id}/tasks/{task_id}/generate-draft
    输入: { skip_llm: bool }
    输出: { id, content, word_count, evidence_ids, status }

依赖约束:
  - ragflow_client.py (获取证据)
  - LLM API (DeepSeek / GPT-5.5)
  - database.py (保存草稿)

验收条件:
  - [ ] 输出字数 3000-8000
  - [ ] 每段引用标注来源
  - [ ] 缺资料时插入 [缺资料提示] 标记
  - [ ] skip_llm=true 时返回模拟数据
  - [ ] 生成时间 < 30 秒
```

### M6 基础质检

```yaml
文件归属:
  - lin_cao_planner/validators.py (质检规则)

接口:
  def validate_draft(draft: ChapterDraft, evidence_map: dict) -> list[QualityFinding]
    
  POST /api/v1/projects/{project_id}/quality-check
    输出: { id, total_findings, error_count, warning_count, findings: [...] }

质检规则:
  - ERROR: 出现数字但无来源引用
  - ERROR: 禁用词检测（"大概"、"可能"、"估计"等不确定表述）
  - ERROR: 同一指标不同章节数值冲突
  - WARNING: 术语不规范
  - WARNING: 章节字数超出目标 ±30%

验收条件:
  - [ ] 无来源数字被标记为 ERROR
  - [ ] 禁用词被检测出来
  - [ ] 指标冲突被检测
  - [ ] 报告包含位置信息（章节+段落）
```

### M7 Markdown 导出

```yaml
文件归属:
  - lin_cao_planner/renderer.py (Markdown 渲染)

接口:
  def render_markdown(project_id: str) -> str
    
  POST /api/v1/projects/{project_id}/export/markdown
    输出: { file_path, content }

验收条件:
  - [ ] 输出包含完整大纲结构
  - [ ] 包含章节内容
  - [ ] 包含引用来源
  - [ ] 包含质检报告
```

### M8 WebSocket 进度推送（新增）

```yaml
文件归属:
  - lin_cao_planner/server.py (WebSocket endpoint)

API 端点:
  WS /ws/progress/{project_id}
    
    消息格式:
    { type: "task_start", task_id: "xxx", chapter: "第一章" }
    { type: "task_progress", task_id: "xxx", percent: 50, message: "正在检索资料..." }
    { type: "task_complete", task_id: "xxx", result: { word_count: 4500 } }
    { type: "task_error", task_id: "xxx", error: "LLM 调用失败" }

验收条件:
  - [ ] 生成草稿时前端收到实时进度
  - [ ] 完成后收到结果通知
  - [ ] 失败时收到错误通知
```

---

## 四、排期估算

### 4.1 任务拆解与估算

| 任务 | 乐观 | 基准 | 悲观 | 依赖 |
|------|------|------|------|------|
| M1 项目管理 API | 0.5d | 1d | 1.5d | — |
| M2 规划模板 | 0.5d | 0.5d | 1d | — |
| M3 资料入库 API | 0.5d | 1d | 2d | M1 |
| M4 章节检索任务 | 0.5d | 1d | 1.5d | M2 |
| M5 章节草稿生成 | 1d | 2d | 3d | M3, M4 |
| M6 基础质检 | 0.5d | 1d | 1.5d | M5 |
| M7 Markdown 导出 | 0.5d | 0.5d | 1d | M5 |
| M8 WebSocket 进度 | 0.5d | 1d | 1.5d | M5 |
| 前端管理台适配 | 1d | 2d | 3d | M1-M8 |
| 集成测试 + Bug修复 | 1d | 2d | 3d | 全部 |

### 4.2 汇总

| 指标 | 值 |
|------|------|
| 乐观总工期 | 5.5 天 |
| 基准总工期 | 10 天 |
| 悲观总工期 | 17 天 |
| 建议排期 | **2 周（10 工作日）** |

### 4.3 里程碑

**Week 1 验收（Day 5）**：
- ✅ 创建项目 + 生成大纲
- ✅ 上传资料 + 检索验证
- ✅ 生成单章草稿
- ✅ 基础质检

**Week 2 验收（Day 10）**：
- ✅ 完整流程端到端跑通
- ✅ Markdown 导出
- ✅ 前端管理台可用
- ✅ WebSocket 实时进度
- ✅ 集成测试通过

---

## 五、DAG 依赖图

```
M1 项目管理 ──┬──→ M3 资料入库 ──→ M5 章节草稿生成 ──┬──→ M6 基础质检
              │                                       │
M2 规划模板 ──┴──→ M4 章节检索任务 ────────────────────┴──→ M7 Markdown 导出
                                                        │
                                              M8 进度推送 ┘
```

**关键路径**：M1 → M3 → M5 → M6（最长路径）
**可并行**：M1 || M2, M3 || M4

---

## 六、Top 5 风险

| # | 风险 | 影响 | 概率 | 缓解 |
|---|------|------|------|------|
| 1 | **LLM 生成质量差** | 用户不信任系统，弃用 | 中 | 缺资料时强制降级为风险提示；提供"重新生成"按钮 |
| 2 | **RAGFlow 部署复杂** | 用户无法启动系统 | 中 | 提供 Docker Compose 一键启动；准备 ChromaDB 备选方案 |
| 3 | **WebSocket 在 Windows 上不稳定** | 进度推送不工作 | 低 | 降级为轮询（每 3 秒 GET 状态） |
| 4 | **前端页面交互粗糙** | 用户体验差 | 中 | Phase 1 以功能可用为主，UI 优化放 Phase 2 |
| 5 | **模型 API 限流/不可用** | 章节生成失败 | 中 | 实现自动降级（DeepSeek ↔ GPT），设置重试策略 |

---

## 七、最终决策

### ✅ 评审通过

PRD v2 和技术选型均通过，可进入开发阶段。

### 修改建议（非阻塞）
1. 增加 M8 WebSocket 进度推送（Must Have）
2. M5 补充"缺资料降级"行为定义
3. M3 补充"上传失败处理"
4. 增加资料删除功能

### 开发顺序建议
```
Day 1-2:   M1 + M2 (项目 + 模板)
Day 3-4:   M3 + M4 (资料 + 检索)
Day 5:     M5 (草稿生成) → Week 1 验收
Day 6-7:   M6 + M7 + M8 (质检 + 导出 + 进度)
Day 8-10:  前端适配 + 集成测试 → Week 2 验收
```
