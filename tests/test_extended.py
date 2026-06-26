"""Extended tests for generator, ragflow client, and rendering."""

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lin_cao_planner import (
    EvidenceChunk,
    LLMConfig,
    ProjectInfo,
    ChapterDraft,
    generate_chapter_draft,
    build_default_outline,
    build_retrieval_plan,
    validate_document,
    render_quality_report,
    render_full_document,
)


class EvidenceChunkTest(unittest.TestCase):
    def test_format_with_all_fields(self):
        chunk = EvidenceChunk("内容", "文件A", 0.92, 5)
        text = chunk.format_for_prompt()
        self.assertIn("文件A", text)
        self.assertIn("内容", text)

    def test_format_empty_document(self):
        chunk = EvidenceChunk("内容", "", 0.0)
        text = chunk.format_for_prompt()
        self.assertIn("来源", text)


class FullDocumentRenderTest(unittest.TestCase):
    def setUp(self):
        self.project = ProjectInfo(
            name="某县规划", region="某县", period="2026-2030",
            level="县级", planning_type="林业发展规划", target_words=5000,
        )
        self.outline = build_default_outline(self.project)

    def test_full_document_has_toc(self):
        md = render_full_document(self.outline, [])
        self.assertIn("目录", md)

    def test_full_document_with_drafts(self):
        drafts = [ChapterDraft("1.1", "标题", "正文内容", ["ev-1"])]
        md = render_full_document(self.outline, drafts)
        self.assertIn("正文内容", md)

    def test_full_document_with_quality(self):
        drafts = [ChapterDraft("1.1", "标题", "据报道森林覆盖率为42%")]
        findings = validate_document(self.outline, drafts)
        md = render_full_document(self.outline, drafts, findings)
        self.assertIn("质检报告", md)


class IndustryTemplateTest(unittest.TestCase):
    def test_industry_template(self):
        project = ProjectInfo(
            name="某县林业产业规划", region="某县", period="2026-2030",
            level="县级", planning_type="林草产业发展规划", target_words=40000,
        )
        outline = build_default_outline(project)
        titles = [ch.title for ch in outline.children]
        self.assertTrue(any("产业基础" in t for t in titles))
        self.assertTrue(any("产业布局" in t for t in titles))
        # Verify word count
        total = sum(ch.target_words for ch in outline.children)
        self.assertEqual(total, 40000)


class GrasslandTemplateTest(unittest.TestCase):
    def test_grassland_uses_base(self):
        project = ProjectInfo(
            name="某县草原保护修复规划", region="某县", period="2026-2030",
            level="县级", planning_type="草原保护修复规划", target_words=50000,
        )
        outline = build_default_outline(project)
        # Grassland doesn't have overrides, uses base template (9 chapters)
        self.assertEqual(len(outline.children), 9)
        total = sum(ch.target_words for ch in outline.children)
        self.assertEqual(total, 50000)


class QualityCheckTest(unittest.TestCase):
    def test_no_false_positive_for_evidence(self):
        """A simple chapter without facts should not trigger missing_evidence."""
        project = ProjectInfo(
            name="测试", region="某县", period="2026-2030",
            level="县级", planning_type="林业发展规划", target_words=5000,
        )
        outline = build_default_outline(project)
        drafts = [ChapterDraft("1.1", "标题", "本节主要阐述规划背景与意义。", ["ev-1"])]
        findings = validate_document(outline, drafts)
        # No data or fact markers in the content, should not have missing_evidence for "1.1"
        for f in findings:
            if f.location == "1.1":
                self.assertNotEqual(f.code, "missing_evidence")

    def test_forbidden_phrase_in_multiple_drafts(self):
        project = ProjectInfo(
            name="测试", region="某县", period="2026-2030",
            level="县级", planning_type="林业发展规划", target_words=5000,
        )
        outline = build_default_outline(project)
        drafts = [
            ChapterDraft("1.1", "a", "据说该县发展很快"),
            ChapterDraft("1.2", "b", "大概有1000公顷"),
        ]
        findings = validate_document(outline, drafts)
        phrase_findings = [f for f in findings if f.code == "forbidden_phrase"]
        self.assertEqual(len(phrase_findings), 2)


if __name__ == "__main__":
    unittest.main()
