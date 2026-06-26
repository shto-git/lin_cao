from __future__ import annotations

from .domain import OutlineNode, ProjectInfo, SectionBrief


DEFAULT_CONSTRAINTS = [
    "不得编造政策、数据、年份和项目名称",
    "无法从资料确认的内容写为风险提示或待补充",
    "同一指标必须保持单位、年份和统计范围一致",
]


def build_retrieval_plan(project: ProjectInfo, outline: OutlineNode) -> list[SectionBrief]:
    briefs: list[SectionBrief] = []
    for chapter in outline.children:
        for section in chapter.children:
            briefs.append(
                SectionBrief(
                    outline_id=section.id,
                    title_path=[chapter.title, section.title],
                    target_words=section.target_words,
                    retrieval_queries=_queries_for_section(project, chapter, section),
                    required_evidence_types=section.required_evidence_types,
                    writing_constraints=DEFAULT_CONSTRAINTS + section.requirements,
                )
            )
    return briefs


def _queries_for_section(project: ProjectInfo, chapter: OutlineNode, section: OutlineNode) -> list[str]:
    plain_chapter = _strip_number(chapter.title)
    plain_section = _strip_number(section.title)
    base = f"{project.region} {project.planning_type} {plain_section}"
    queries = [
        f"{base} 基础资料 数据 指标",
        f"{base} 政策 规范 上位规划",
        f"{project.region} {plain_chapter} {plain_section} 历史规划 案例",
    ]
    if "spatial_data" in section.required_evidence_types:
        queries.append(f"{project.region} {plain_section} 空间布局 图件 边界 管控")
    if "project_data" in section.required_evidence_types:
        queries.append(f"{project.region} {plain_section} 项目库 工程 投资 年度计划")
    return _deduplicate(queries)


def _strip_number(title: str) -> str:
    parts = title.split(" ", 1)
    if len(parts) == 2 and (parts[0].startswith("第") or "." in parts[0]):
        return parts[1]
    return title


def _deduplicate(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            out.append(value)
            seen.add(value)
    return out
