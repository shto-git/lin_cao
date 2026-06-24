import unittest

from lin_cao_planner import ChapterDraft, ProjectInfo, build_default_outline, build_retrieval_plan, validate_document


class PipelineTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
