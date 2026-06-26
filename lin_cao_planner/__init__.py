"""Business orchestration layer for forestry and grassland planning drafts."""

from .domain import ChapterDraft, Evidence, OutlineNode, ProjectInfo, QualityFinding, SectionBrief
from .evidence import build_retrieval_plan
from .outline import build_default_outline
from .validators import validate_document
from .renderer import render_outline, render_retrieval_plan, render_quality_report, render_full_document
from .generator import (
    EvidenceChunk,
    GenerationResult,
    LLMClient,
    LLMConfig,
    generate_chapter_draft,
)
from .ragflow_client import RagflowClient, RagflowError
from .pipeline import PipelineConfig, PipelineResult, run_pipeline

__all__ = [
    # Domain
    "ChapterDraft",
    "Evidence",
    "OutlineNode",
    "ProjectInfo",
    "QualityFinding",
    "SectionBrief",
    # Outline & Evidence
    "build_default_outline",
    "build_retrieval_plan",
    # Validation
    "validate_document",
    # Rendering
    "render_outline",
    "render_retrieval_plan",
    "render_quality_report",
    "render_full_document",
    # Generation
    "EvidenceChunk",
    "GenerationResult",
    "LLMClient",
    "LLMConfig",
    "generate_chapter_draft",
    # Pipeline
    "PipelineConfig",
    "PipelineResult",
    "run_pipeline",
    # RAGFlow
    "RagflowClient",
    "RagflowError",
]
