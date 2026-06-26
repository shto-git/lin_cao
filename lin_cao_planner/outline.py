from __future__ import annotations

from .domain import OutlineNode, ProjectInfo


BASE_TEMPLATE: list[tuple[str, float, list[str]]] = [
    ("总则", 0.07, ["规划背景", "编制依据", "规划范围与期限"]),
    ("区域概况与资源现状", 0.18, ["自然地理与社会经济概况", "林草湿资源现状", "保护利用现状"]),
    ("形势研判与主要问题", 0.12, ["发展基础", "主要问题", "机遇与挑战"]),
    ("指导思想与目标指标", 0.12, ["指导思想", "基本原则", "规划目标与指标体系"]),
    ("空间布局", 0.13, ["总体布局", "分区管控", "重点区域安排"]),
    ("重点任务", 0.16, ["资源保护", "生态修复", "质量提升", "产业与服务能力"]),
    ("重点工程与项目安排", 0.10, ["重点工程", "项目库", "年度实施计划"]),
    ("投资估算与效益分析", 0.07, ["投资估算", "资金来源", "效益分析"]),
    ("保障措施", 0.05, ["组织保障", "政策保障", "实施监督"]),
]


TYPE_OVERRIDES: dict[str, list[tuple[str, float, list[str]]]] = {
    "湿地": [
        ("湿地保护修复格局", 0.14, ["湿地保护空间", "退化湿地修复", "湿地生态补水"]),
        ("湿地监测与合理利用", 0.10, ["监测评价", "科普宣教", "合理利用"]),
    ],
    "自然保护地": [
        ("保护地体系与边界管控", 0.15, ["保护对象", "功能分区", "边界与管控要求"]),
        ("建设管理任务", 0.13, ["基础设施", "科研监测", "社区共管"]),
    ],
    "产业": [
        ("产业基础与市场分析", 0.14, ["产业现状", "市场需求", "短板分析"]),
        ("产业布局与重点业态", 0.15, ["空间布局", "重点业态", "品牌与加工流通"]),
    ],
    "草原": [
        ("草原保护修复格局", 0.14, ["草原生态保护空间", "退化草原修复", "草原生态补水"]),
        ("草原监测与合理利用", 0.10, ["监测评价", "草畜平衡", "合理利用"]),
    ],
    "国土绿化": [
        ("国土绿化潜力评估", 0.15, ["绿化现状分析", "绿化潜力评价", "绿化空间布局"]),
        ("国土绿化重点任务", 0.13, ["森林质量提升", "退化林修复", "乡村绿化美化"]),
    ],
    "生物多样性": [
        ("生物多样性保护体系", 0.14, ["保护优先区", "保护空缺分析", "保护网络构建"]),
        ("重点物种与生态系统保护", 0.13, ["珍稀濒危物种", "典型生态系统", "外来物种防控"]),
    ],
}


def build_default_outline(project: ProjectInfo) -> OutlineNode:
    template = _select_template(project.planning_type)
    chapter_targets = _distribute_words(project.target_words, [item[1] for item in template])
    root = OutlineNode(
        id="root",
        title=project.name,
        level=0,
        target_words=project.target_words,
        requirements=[
            f"规划区域：{project.region}",
            f"规划期限：{project.period}",
            f"规划类型：{project.planning_type}",
        ],
    )

    for index, ((title, _, sections), chapter_words) in enumerate(zip(template, chapter_targets), start=1):
        child_targets = _distribute_words(chapter_words, [1.0] * len(sections))
        chapter = OutlineNode(
            id=str(index),
            title=f"第{index}章 {title}",
            level=1,
            target_words=chapter_words,
            requirements=_chapter_requirements(title),
            required_evidence_types=_required_evidence_types(title),
        )
        for sub_index, (section_title, section_words) in enumerate(zip(sections, child_targets), start=1):
            chapter.children.append(
                OutlineNode(
                    id=f"{index}.{sub_index}",
                    title=f"{index}.{sub_index} {section_title}",
                    level=2,
                    target_words=section_words,
                    requirements=_section_requirements(section_title),
                    required_evidence_types=_required_evidence_types(section_title),
                )
            )
        root.children.append(chapter)
    return root


def _select_template(planning_type: str) -> list[tuple[str, float, list[str]]]:
    for keyword, additions in TYPE_OVERRIDES.items():
        if keyword in planning_type:
            merged = BASE_TEMPLATE[:5] + additions + BASE_TEMPLATE[5:]
            return _normalize_weights(merged)
    return BASE_TEMPLATE


def _normalize_weights(template: list[tuple[str, float, list[str]]]) -> list[tuple[str, float, list[str]]]:
    total = sum(item[1] for item in template)
    return [(title, weight / total, sections) for title, weight, sections in template]


def _distribute_words(total_words: int, weights: list[float]) -> list[int]:
    raw = [int(total_words * weight / sum(weights)) for weight in weights]
    diff = total_words - sum(raw)
    if raw:
        raw[-1] += diff
    return raw


def _required_evidence_types(title: str) -> list[str]:
    evidence: list[str] = []
    if any(key in title for key in ["依据", "政策", "保障", "管控", "法规"]):
        evidence.extend(["policy", "standard"])
    if any(key in title for key in ["现状", "指标", "估算", "资源", "效益", "盖度"]):
        evidence.extend(["project_data", "statistic"])
    if any(key in title for key in ["工程", "项目", "年度", "任务"]):
        evidence.extend(["project_data", "case"])
    if any(key in title for key in ["空间", "布局", "分区", "区域", "保护地"]):
        evidence.extend(["spatial_data", "policy"])
    if any(key in title for key in ["物种", "生态", "生物多样性", "植被"]):
        evidence.extend(["case", "statistic"])
    if any(key in title for key in ["市场", "产业", "品牌", "加工"]):
        evidence.extend(["project_data", "case"])
    if any(key in title for key in ["监测", "科普", "宣教", "社区"]):
        evidence.extend(["standard", "case"])
    if not evidence:
        evidence.append("case")
    return sorted(set(evidence))


def _chapter_requirements(title: str) -> list[str]:
    return [
        "先写事实和依据，再写判断和安排",
        "关键数据必须保留来源",
        f"章节主题聚焦：{title}",
    ]


def _section_requirements(title: str) -> list[str]:
    requirements = ["避免空泛表述，优先使用项目资料"]
    if any(key in title for key in ["指标", "估算", "现状"]):
        requirements.append("涉及数字时注明年份、范围和单位")
    if any(key in title for key in ["依据", "保障", "管控"]):
        requirements.append("政策或规范名称必须完整")
    return requirements
