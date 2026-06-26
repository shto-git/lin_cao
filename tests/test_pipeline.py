"""Tests for the complete pipeline, generator, and ragflow client."""

import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lin_cao_planner import (
    ChapterDraft,
    EvidenceChunk,
    GenerationResult,
    LLMClient,
    LLMConfig,
    ProjectInfo,
    build_default_outline,
    build_retrieval_plan,
    generate_chapter_draft,
    validate_document,
    render_full_document,
    render_quality_report,
    RagflowClient,
    RagflowError,
    PipelineConfig,
    run_pipeline,
)


class PipelineTest(unittest.TestCase):
    """Tests from the original codebase (preserved)."""

    def test_outline_word_count_is_preserved(self):
        project = ProjectInfo(
            name="某县林业发展规划",
            region="某县",
            period="2026-2030年",
            level="县域级",
            planning_type="林业发展规划",
            target_words=50000,
        )
        outline = build_default_outline(project)
        self.assertEqual(sum(chapter.target_words for chapter in outline.children), 50000)
        self.assertGreater(len(outline.leaves()), 10)

    def test_retrieval_plan_has_queries_for_each_leaf(self):
        project = ProjectInfo(
            name="某县湿地保护修复规划",
            region="某县",
            period="2026-2030年",
            level="县域级",
            planning_type="湿地保护修复规划",
            target_words=60000,
        )
        outline = build_default_outline(project)
        briefs = build_retrieval_plan(project, outline)
        self.assertEqual(len(briefs), len(outline.leaves()))
        self.assertTrue(all(brief.retrieval_queries for brief in briefs))
        self.assertTrue(any("空间布局" in " ".join(brief.retrieval_queries) for brief in briefs))

    def test_validator_flags_missing_evidence_and_metric_conflict(self):
        project = ProjectInfo(
            name="某县林业发展规划",
            region="某县",
            period="2026-2030年",
            level="县域级",
            planning_type="林业发展规划",
            target_words=50000,
        )
        outline = build_default_outline(project)
        drafts = [
            ChapterDraft("1.1", "规划背景", "根据统计，森林覆盖率达到42.1%，有关部门应加强统筹。"),
            ChapterDraft("1.2", "编制依据", "森林覆盖率为43.0%。", evidence_ids=["ev-1"]),
        ]
        findings = validate_document(outline, drafts)
        codes = {finding.code for finding in findings}
        self.assertIn("missing_evidence", codes)
        self.assertIn("forbidden_phrase", codes)
        self.assertIn("metric_conflict", codes)


class WetlandTemplateTest(unittest.TestCase):
    """Test wetland planning template has extra chapters."""

    def test_wetland_has_extended_chapters(self):
        project = ProjectInfo(
            name="某县湿地保护修复规划",
            region="某县",
            period="2026-2030年",
            level="县域级",
            planning_type="湿地保护修复规划",
            target_words=60000,
        )
        outline = build_default_outline(project)
        # Wetland adds 2 extra chapter groups compared to base (9)
        self.assertGreaterEqual(len(outline.children), 10)
        titles = [ch.title for ch in outline.children]
        self.assertTrue(any("湿地保护修复格局" in t for t in titles))
        self.assertTrue(any("湿地监测与合理利用" in t for t in titles))

    def test_nature_reserve_has_extended_chapters(self):
        project = ProjectInfo(
            name="某自然保护地规划",
            region="某市",
            period="2026-2035年",
            level="市级",
            planning_type="自然保护地建设管理规划",
            target_words=80000,
        )
        outline = build_default_outline(project)
        titles = [ch.title for ch in outline.children]
        self.assertTrue(any("保护地体系" in t for t in titles))
        self.assertTrue(any("建设管理任务" in t for t in titles))


class GeneratorTest(unittest.TestCase):
    """Test chapter draft generation."""

    def test_generate_placeholder_without_llm(self):
        result = generate_chapter_draft(
            outline_id="1.1",
            title_path="第1章 总则 / 1.1 规划背景",
            target_words=1500,
            requirements=["说明规划背景"],
            evidence_types=["case"],
            constraints=["不得编造"],
            evidence_chunks=[
                EvidenceChunk(
                    content="某县总面积1500平方公里。",
                    document_name="统计年鉴",
                    similarity=0.9,
                ),
            ],
            llm_client=None,
        )
        self.assertEqual(result.outline_id, "1.1")
        self.assertEqual(result.status, "draft")
        self.assertGreater(result.word_count, 0)
        self.assertTrue(len(result.warnings) > 0)  # Should warn about missing LLM key
        self.assertEqual(len(result.evidence_ids), 1)

    def test_generate_with_no_evidence(self):
        result = generate_chapter_draft(
            outline_id="2.1",
            title_path="第2章 / 2.1 现状",
            target_words=3000,
            requirements=[],
            evidence_types=["statistic"],
            constraints=[],
            evidence_chunks=[],
            llm_client=None,
        )
        self.assertEqual(result.outline_id, "2.1")
        self.assertTrue("待补充" in result.content or "占位草稿" in result.content)

    def test_llm_config_from_env(self):
        """LLMConfig should pick up env vars."""
        os.environ["LINCAO_LLM_API_KEY"] = "test-key-123"
        os.environ["LINCAO_LLM_MODEL"] = "test-model"
        config = LLMConfig.from_env()
        self.assertEqual(config.api_key, "test-key-123")
        self.assertEqual(config.model, "test-model")
        del os.environ["LINCAO_LLM_API_KEY"]
        del os.environ["LINCAO_LLM_MODEL"]

    def test_evidence_chunk_format(self):
        chunk = EvidenceChunk(
            content="测试内容",
            document_name="测试文件",
            similarity=0.85,
            page_number=10,
        )
        formatted = chunk.format_for_prompt()
        self.assertIn("测试文件", formatted)
        self.assertIn("测试内容", formatted)
        self.assertIn("10", formatted)


class RendererTest(unittest.TestCase):
    """Test rendering functions."""

    def test_render_full_document(self):
        project = ProjectInfo(
            name="测试规划",
            region="测试区",
            period="2026-2030年",
            level="县级",
            planning_type="林业发展规划",
            target_words=10000,
        )
        outline = build_default_outline(project)
        drafts = [
            ChapterDraft("1.1", "测试节", "这是测试内容。", evidence_ids=["ev-1"]),
        ]
        result = render_full_document(outline, drafts)
        self.assertIn("测试规划", result)
        self.assertIn("目录", result)
        self.assertIn("测试节", result)

    def test_render_quality_report_with_findings(self):
        project = ProjectInfo(
            name="测试规划",
            region="测试区",
            period="2026-2030年",
            level="县级",
            planning_type="林业发展规划",
            target_words=10000,
        )
        outline = build_default_outline(project)
        drafts = [
            ChapterDraft("1.1", "测试", "根据统计，森林覆盖率达到42.1%。"),
        ]
        findings = validate_document(outline, drafts)
        report = render_quality_report(findings)
        self.assertIn("质检报告", report)


class RagflowClientTest(unittest.TestCase):
    """Test RAGFlow client (without actual connection)."""

    def test_client_init(self):
        client = RagflowClient("http://localhost:9380", "test-key")
        self.assertEqual(client.base_url, "http://localhost:9380")
        self.assertEqual(client.api_key, "test-key")

    def test_ragflow_error(self):
        err = RagflowError("test error")
        self.assertIsInstance(err, RuntimeError)


class FullPipelineTest(unittest.TestCase):
    """Integration test for the complete pipeline."""

    def test_pipeline_end_to_end(self):
        project = ProjectInfo(
            name="某县林业发展规划（2026-2030年）",
            region="某县",
            period="2026-2030年",
            level="县域级",
            planning_type="林业发展规划",
            target_words=30000,
        )
        config = PipelineConfig()
        config.output_dir = "dist/test_pipeline"

        result = run_pipeline(project, config)

        self.assertIsNotNone(result.outline)
        self.assertGreater(len(result.briefs), 0)
        self.assertGreater(len(result.drafts), 0)
        self.assertTrue(len(result.output_files) >= 4)

        # Verify output files exist
        for name, path in result.output_files.items():
            self.assertTrue(
                os.path.exists(path),
                f"Output file missing: {name} at {path}",
            )


if __name__ == "__main__":
    unittest.main()
