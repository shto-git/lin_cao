"""Tests for SQLite database persistence layer."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lin_cao_planner.database import Database


class DatabaseCRUDTest(unittest.TestCase):
    """Test all CRUD operations on an in-memory SQLite database."""

    def setUp(self):
        self.db = Database(db_path=":memory:")
        self.db.connect()

    def tearDown(self):
        self.db.close()

    # ── Projects ──────────────────────────────────────────

    def test_save_and_get_project(self):
        pid = self.db.save_project(
            name="测试规划",
            region="某县",
            period="2026-2030",
            planning_type="林业发展规划",
            target_words=50000,
        )
        project = self.db.get_project(pid)
        self.assertIsNotNone(project)
        self.assertEqual(project["name"], "测试规划")
        self.assertEqual(project["region"], "某县")
        self.assertEqual(project["target_words"], 50000)

    def test_list_projects(self):
        self.db.save_project("项目A", "区域A", "2026-2030", "林业", project_id="p1")
        self.db.save_project("项目B", "区域B", "2026-2030", "湿地", project_id="p2")
        projects = self.db.list_projects()
        self.assertEqual(len(projects), 2)

    def test_delete_project(self):
        pid = self.db.save_project("测试", "某县", "2026-2030", "林业")
        self.assertTrue(self.db.delete_project(pid))
        self.assertIsNone(self.db.get_project(pid))

    def test_save_project_with_id(self):
        pid = self.db.save_project("测试", "某县", "2026-2030", "林业", project_id="custom-id")
        self.assertEqual(pid, "custom-id")
        project = self.db.get_project("custom-id")
        self.assertIsNotNone(project)

    # ── Documents ─────────────────────────────────────────

    def test_save_and_get_document(self):
        pid = self.db.save_project("测试", "某县", "2026-2030", "林业")
        did = self.db.save_document(
            project_id=pid,
            file_name="test.pdf",
            file_path="/tmp/test.pdf",
            file_type="pdf",
            file_size=1024,
            source_unit="林科院",
            publish_year=2025,
            category="policy",
        )
        doc = self.db.get_document(did)
        self.assertIsNotNone(doc)
        self.assertEqual(doc["file_name"], "test.pdf")
        self.assertEqual(doc["file_size"], 1024)
        self.assertEqual(doc["publish_year"], 2025)

    def test_list_documents(self):
        pid = self.db.save_project("测试", "某县", "2026-2030", "林业")
        self.db.save_document(pid, "a.pdf", doc_id="d1")
        self.db.save_document(pid, "b.pdf", doc_id="d2")
        docs = self.db.list_documents(pid)
        self.assertEqual(len(docs), 2)

    def test_delete_document(self):
        pid = self.db.save_project("测试", "某县", "2026-2030", "林业")
        did = self.db.save_document(pid, "test.pdf")
        self.assertTrue(self.db.delete_document(did))
        self.assertIsNone(self.db.get_document(did))

    # ── Outline Nodes ─────────────────────────────────────

    def test_save_and_get_outline_node(self):
        pid = self.db.save_project("测试", "某县", "2026-2030", "林业")
        nid = self.db.save_outline_node(
            project_id=pid,
            title="第1章 总则",
            level=1,
            node_id="1",
            target_words=3500,
            requirements=["要求1", "要求2"],
            required_evidence_types=["policy", "case"],
        )
        node = self.db.get_outline_node("1")
        self.assertIsNotNone(node)
        self.assertEqual(node["title"], "第1章 总则")
        self.assertEqual(node["level"], 1)
        self.assertEqual(node["target_words"], 3500)

    def test_list_outline_nodes(self):
        pid = self.db.save_project("测试", "某县", "2026-2030", "林业")
        self.db.save_outline_node(pid, "第1章", 1, node_id="1")
        self.db.save_outline_node(pid, "第2章", 1, node_id="2")
        nodes = self.db.list_outline_nodes(pid)
        self.assertEqual(len(nodes), 2)

    # ── Section Tasks ─────────────────────────────────────

    def test_save_and_get_section_task(self):
        pid = self.db.save_project("测试", "某县", "2026-2030", "林业")
        self.db.save_outline_node(pid, "第1章", 1, node_id="1")
        tid = self.db.save_section_task(
            project_id=pid,
            outline_id="1.1",
            title_path=["第1章", "1.1 背景"],
            target_words=1500,
            retrieval_queries=["查询1", "查询2"],
            required_evidence_types=["case"],
            writing_constraints=["约束1"],
        )
        task = self.db.get_section_task(tid)
        self.assertIsNotNone(task)
        self.assertEqual(task["outline_id"], "1.1")
        self.assertEqual(task["target_words"], 1500)

    def test_list_section_tasks(self):
        pid = self.db.save_project("测试", "某县", "2026-2030", "林业")
        self.db.save_outline_node(pid, "第1章", 1, node_id="1")
        self.db.save_section_task(pid, "1.1", ["路径"], 1000, ["q1"], ["case"])
        self.db.save_section_task(pid, "1.2", ["路径"], 1000, ["q2"], ["policy"])
        tasks = self.db.list_section_tasks(pid)
        self.assertEqual(len(tasks), 2)

    # ── Evidences ─────────────────────────────────────────

    def test_save_and_get_evidence(self):
        pid = self.db.save_project("测试", "某县", "2026-2030", "林业")
        self.db.save_outline_node(pid, "第1章", 1, node_id="1")
        tid = self.db.save_section_task(pid, "1.1", ["路径"], 1000, ["q1"], ["case"])
        eid = self.db.save_evidence(
            project_id=pid,
            section_task_id=tid,
            title="证据标题",
            source_type="policy",
            source_name="文件名",
            quote="引用内容",
            similarity=0.85,
            chunk_id="chunk-1",
        )
        ev = self.db.get_evidence(eid)
        self.assertIsNotNone(ev)
        self.assertEqual(ev["similarity"], 0.85)
        self.assertEqual(ev["source_type"], "policy")

    def test_list_evidences(self):
        pid = self.db.save_project("测试", "某县", "2026-2030", "林业")
        self.db.save_outline_node(pid, "第1章", 1, node_id="1")
        tid = self.db.save_section_task(pid, "1.1", ["路径"], 1000, ["q1"], ["case"])
        self.db.save_evidence(pid, tid, similarity=0.9, evidence_id="e1")
        self.db.save_evidence(pid, tid, similarity=0.7, evidence_id="e2")
        evs = self.db.list_evidences(tid)
        self.assertEqual(len(evs), 2)
        # Should be ordered by similarity DESC
        self.assertGreaterEqual(evs[0]["similarity"], evs[1]["similarity"])

    # ── Chapter Drafts ────────────────────────────────────

    def test_save_and_get_chapter_draft(self):
        pid = self.db.save_project("测试", "某县", "2026-2030", "林业")
        self.db.save_outline_node(pid, "第1章", 1, node_id="1")
        did = self.db.save_chapter_draft(
            project_id=pid,
            outline_id="1.1",
            title="1.1 规划背景",
            content="这是测试内容，约100字。" * 10,
            evidence_ids=["ev-1", "ev-2"],
            status="draft",
        )
        draft = self.db.get_chapter_draft(did)
        self.assertIsNotNone(draft)
        self.assertEqual(draft["title"], "1.1 规划背景")
        self.assertGreater(draft["word_count"], 0)
        self.assertEqual(draft["status"], "draft")

    def test_list_chapter_drafts(self):
        pid = self.db.save_project("测试", "某县", "2026-2030", "林业")
        self.db.save_outline_node(pid, "第1章", 1, node_id="1")
        self.db.save_chapter_draft(pid, "1.1", "标题1", "内容1")
        self.db.save_chapter_draft(pid, "1.2", "标题2", "内容2")
        drafts = self.db.list_chapter_drafts(pid)
        self.assertEqual(len(drafts), 2)

    # ── Quality Reports ───────────────────────────────────

    def test_save_and_get_quality_report(self):
        pid = self.db.save_project("测试", "某县", "2026-2030", "林业")
        rid = self.db.save_quality_report(
            project_id=pid,
            total_findings=5,
            error_count=2,
            warning_count=3,
        )
        report = self.db.get_quality_report(rid)
        self.assertIsNotNone(report)
        self.assertEqual(report["total_findings"], 5)
        self.assertEqual(report["error_count"], 2)

    def test_list_quality_reports(self):
        pid = self.db.save_project("测试", "某县", "2026-2030", "林业")
        self.db.save_quality_report(pid, report_id="r1")
        self.db.save_quality_report(pid, report_id="r2")
        reports = self.db.list_quality_reports(pid)
        self.assertEqual(len(reports), 2)

    # ── Quality Findings ──────────────────────────────────

    def test_save_and_get_quality_finding(self):
        pid = self.db.save_project("测试", "某县", "2026-2030", "林业")
        rid = self.db.save_quality_report(pid)
        fid = self.db.save_quality_finding(
            report_id=rid,
            severity="error",
            code="metric_conflict",
            message="指标冲突",
            location="1.1",
            suggestion="修复建议",
        )
        finding = self.db.get_quality_finding(fid)
        self.assertIsNotNone(finding)
        self.assertEqual(finding["severity"], "error")
        self.assertEqual(finding["code"], "metric_conflict")

    def test_list_quality_findings(self):
        pid = self.db.save_project("测试", "某县", "2026-2030", "林业")
        rid = self.db.save_quality_report(pid)
        self.db.save_quality_finding(rid, "error", "code1", "msg1")
        self.db.save_quality_finding(rid, "warning", "code2", "msg2")
        findings = self.db.list_quality_findings(rid)
        self.assertEqual(len(findings), 2)

    # ── Export Tasks ──────────────────────────────────────

    def test_save_and_get_export_task(self):
        pid = self.db.save_project("测试", "某县", "2026-2030", "林业")
        tid = self.db.save_export_task(
            project_id=pid,
            format="markdown",
            file_path="/tmp/output.md",
            status="completed",
        )
        task = self.db.get_export_task(tid)
        self.assertIsNotNone(task)
        self.assertEqual(task["format"], "markdown")
        self.assertEqual(task["status"], "completed")

    def test_list_export_tasks(self):
        pid = self.db.save_project("测试", "某县", "2026-2030", "林业")
        self.db.save_export_task(pid, "markdown")
        self.db.save_export_task(pid, "word")
        tasks = self.db.list_export_tasks(pid)
        self.assertEqual(len(tasks), 2)

    # ── Context Manager ───────────────────────────────────

    def test_context_manager(self):
        with Database(db_path=":memory:") as db:
            pid = db.save_project("测试", "某县", "2026-2030", "林业")
            project = db.get_project(pid)
            self.assertIsNotNone(project)


class DatabaseFileTest(unittest.TestCase):
    """Test file-based database."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self._tmpdir, "test.db")

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self._tmpdir)

    def test_file_db_persists(self):
        db = Database(db_path=self.db_path)
        db.connect()
        pid = db.save_project("持久化测试", "某县", "2026-2030", "林业")
        db.close()

        # Reopen and verify
        db2 = Database(db_path=self.db_path)
        db2.connect()
        project = db2.get_project(pid)
        self.assertIsNotNone(project)
        self.assertEqual(project["name"], "持久化测试")
        db2.close()


if __name__ == "__main__":
    unittest.main()
