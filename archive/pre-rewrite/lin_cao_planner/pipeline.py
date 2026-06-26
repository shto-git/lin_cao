"""Complete pipeline: outline → retrieval → draft → quality check → export."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .domain import ChapterDraft, OutlineNode, ProjectInfo, SectionBrief, QualityFinding
from .evidence import build_retrieval_plan
from .generator import (
    EvidenceChunk,
    GenerationResult,
    LLMClient,
    LLMConfig,
    generate_chapter_draft,
)
from .outline import build_default_outline
from .ragflow_client import RagflowClient
from .renderer import (
    render_full_document,
    render_outline,
    render_quality_report,
    render_retrieval_plan,
)
from .validators import validate_document


@dataclass
class PipelineConfig:
    """Configuration for the planning pipeline."""

    # RAGFlow
    ragflow_url: str = ""
    ragflow_api_key: str = ""
    dataset_id: str = ""

    # LLM
    llm_config: LLMConfig | None = None

    # Output
    output_dir: str = "dist/output"

    @classmethod
    def from_env(cls) -> "PipelineConfig":
        return cls(
            ragflow_url=os.environ.get("RAGFLOW_BASE_URL", "http://localhost:9380"),
            ragflow_api_key=os.environ.get("RAGFLOW_API_KEY", ""),
            dataset_id=os.environ.get("RAGFLOW_DATASET_ID", ""),
            llm_config=LLMConfig.from_env(),
        )


@dataclass
class PipelineResult:
    """Complete result of a pipeline run."""

    project: ProjectInfo
    outline: OutlineNode
    briefs: list[SectionBrief]
    drafts: list[ChapterDraft] = field(default_factory=list)
    findings: list[QualityFinding] = field(default_factory=list)
    generated: list[GenerationResult] = field(default_factory=list)
    output_files: dict[str, str] = field(default_factory=dict)


def run_pipeline(project: ProjectInfo, config: PipelineConfig | None = None) -> PipelineResult:
    """Run the complete planning pipeline.

    Steps:
        1. Generate outline from project info
        2. Build retrieval plan for each section
        3. (Optional) Retrieve evidence from RAGFlow
        4. (Optional) Generate chapter drafts with LLM
        5. Run quality checks
        6. Export all outputs
    """
    if config is None:
        config = PipelineConfig.from_env()

    out_dir = Path(config.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    result = PipelineResult(
        project=project,
        outline=build_default_outline(project),
        briefs=build_retrieval_plan(project, build_default_outline(project)),
    )

    # Re-generate outline (already done above, but keep reference clean)
    result.outline = build_default_outline(project)
    result.briefs = build_retrieval_plan(project, result.outline)

    # Step 3: Try RAGFlow retrieval if configured
    evidence_map: dict[str, list[EvidenceChunk]] = {}
    client = None
    if config.ragflow_url and config.ragflow_api_key:
        client = RagflowClient(config.ragflow_url, config.ragflow_api_key)
        evidence_map = _retrieve_evidence(client, result)

    # Step 4: Generate drafts
    llm_client = LLMClient(config.llm_config)
    for brief in result.briefs:
        gen_result = generate_chapter_draft(
            outline_id=brief.outline_id,
            title_path=" / ".join(brief.title_path),
            target_words=brief.target_words,
            requirements=brief.writing_constraints,
            evidence_types=brief.required_evidence_types,
            constraints=brief.writing_constraints,
            evidence_chunks=evidence_map.get(brief.outline_id, []),
            llm_client=llm_client,
        )
        result.generated.append(gen_result)
        result.drafts.append(
            ChapterDraft(
                outline_id=gen_result.outline_id,
                title=gen_result.title,
                content=gen_result.content,
                evidence_ids=gen_result.evidence_ids,
                status=gen_result.status,
            )
        )

    # Step 5: Quality check
    result.findings = validate_document(result.outline, result.drafts)

    # Step 6: Export
    result.output_files = _export_all(result, out_dir)

    return result


def _retrieve_evidence(
    client: RagflowClient,
    result: PipelineResult,
) -> dict[str, list[EvidenceChunk]]:
    """Retrieve evidence chunks from RAGFlow for each section."""
    evidence_map: dict[str, list[EvidenceChunk]] = {}
    for brief in result.briefs:
        try:
            response = client.retrieve_chunks(
                question=brief.retrieval_queries[0] if brief.retrieval_queries else "",
                dataset_ids=[result.project.__dict__.get("_dataset_id", "")],
                page_size=5,
                similarity_threshold=0.15,
            )
            chunks = []
            for item in response.get("data", {}).get("chunks", []):
                chunks.append(
                    EvidenceChunk(
                        content=item.get("content", ""),
                        document_name=item.get("document_name", ""),
                        similarity=item.get("similarity", 0.0),
                    )
                )
            evidence_map[brief.outline_id] = chunks
        except Exception:
            evidence_map[brief.outline_id] = []
    return evidence_map


def _export_all(result: PipelineResult, out_dir: Path) -> dict[str, str]:
    """Export all pipeline outputs to files."""
    files: dict[str, str] = {}

    # Outline
    outline_path = out_dir / "outline.md"
    outline_path.write_text(render_outline(result.outline), encoding="utf-8")
    files["outline"] = str(outline_path)

    # Retrieval plan
    retrieval_path = out_dir / "retrieval_plan.md"
    retrieval_path.write_text(render_retrieval_plan(result.briefs), encoding="utf-8")
    files["retrieval_plan"] = str(retrieval_path)

    # Full document
    doc_path = out_dir / "document.md"
    doc_path.write_text(
        render_full_document(result.outline, result.drafts, result.findings),
        encoding="utf-8",
    )
    files["document"] = str(doc_path)

    # Quality report
    report_path = out_dir / "quality_report.md"
    report_path.write_text(render_quality_report(result.findings), encoding="utf-8")
    files["quality_report"] = str(report_path)

    return files
