from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ProjectInfo:
    name: str
    region: str
    period: str
    level: str
    planning_type: str
    target_words: int = 50000
    owner_department: str = ""
    drafting_unit: str = ""

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "ProjectInfo":
        return cls(
            name=str(data["name"]),
            region=str(data["region"]),
            period=str(data["period"]),
            level=str(data.get("level", "")),
            planning_type=str(data["planning_type"]),
            target_words=int(data.get("target_words", 50000)),
            owner_department=str(data.get("owner_department", "")),
            drafting_unit=str(data.get("drafting_unit", "")),
        )


@dataclass(slots=True)
class OutlineNode:
    id: str
    title: str
    level: int
    target_words: int
    requirements: list[str] = field(default_factory=list)
    required_evidence_types: list[str] = field(default_factory=list)
    children: list["OutlineNode"] = field(default_factory=list)

    def walk(self) -> list["OutlineNode"]:
        nodes = [self]
        for child in self.children:
            nodes.extend(child.walk())
        return nodes

    def leaves(self) -> list["OutlineNode"]:
        if not self.children:
            return [self]
        out: list[OutlineNode] = []
        for child in self.children:
            out.extend(child.leaves())
        return out


@dataclass(slots=True)
class Evidence:
    id: str
    title: str
    source_type: str
    source_name: str
    quote: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SectionBrief:
    outline_id: str
    title_path: list[str]
    target_words: int
    retrieval_queries: list[str]
    required_evidence_types: list[str]
    writing_constraints: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ChapterDraft:
    outline_id: str
    title: str
    content: str
    evidence_ids: list[str] = field(default_factory=list)
    status: str = "draft"


@dataclass(slots=True)
class QualityFinding:
    severity: str
    code: str
    message: str
    location: str
    suggestion: str
