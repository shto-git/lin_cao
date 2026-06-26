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
from .database import Database, DB_PATH
from .chart_engine import bar_chart, line_chart, pie_chart, stacked_bar_chart

__all__ = [
    "ChapterDraft", "Evidence", "OutlineNode", "ProjectInfo", "QualityFinding", "SectionBrief",
    "build_default_outline", "build_retrieval_plan",
    "validate_document",
    "render_outline", "render_retrieval_plan", "render_quality_report", "render_full_document",
    "EvidenceChunk", "GenerationResult", "LLMClient", "LLMConfig", "generate_chapter_draft",
    "PipelineConfig", "PipelineResult", "run_pipeline",
    "RagflowClient", "RagflowError",
    "Database", "DB_PATH",
    "bar_chart", "line_chart", "pie_chart", "stacked_bar_chart",
]
