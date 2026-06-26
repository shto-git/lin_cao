"""Tests for FastAPI backend API endpoints."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Skip if fastapi not installed
try:
    from fastapi.testclient import TestClient
    from lin_cao_planner.server import app
    from lin_cao_planner.database import Database
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


@unittest.skipUnless(HAS_FASTAPI, "fastapi not installed")
class APITest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use temp DB
        cls._tmpdir = os.path.join(os.path.dirname(__file__), "_test_data")
        os.makedirs(cls._tmpdir, exist_ok=True)
        cls._db_path = os.path.join(cls._tmpdir, "test.db")
        # Patch DB path
        import lin_cao_planner.server as srv
        srv.DB_PATH = cls._db_path
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        import shutil
        if os.path.exists(cls._tmpdir):
            shutil.rmtree(cls._tmpdir)

    def test_health(self):
        resp = self.client.get("/api/v1/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "ok")

    def test_create_project(self):
        resp = self.client.post("/api/v1/projects", json={
            "name": "测试项目",
            "region": "某县",
            "period": "2026-2030",
            "planning_type": "林业发展规划",
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("id", data)
        self.__class__.project_id = data["id"]

    def test_list_projects(self):
        resp = self.client.get("/api/v1/projects")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_get_project(self):
        # Create one first
        resp = self.client.post("/api/v1/projects", json={
            "name": "查询测试",
            "region": "某县",
            "period": "2026-2030",
            "planning_type": "林业",
        })
        pid = resp.json()["id"]
        resp = self.client.get(f"/api/v1/projects/{pid}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["name"], "查询测试")

    def test_get_project_not_found(self):
        resp = self.client.get("/api/v1/projects/nonexistent-id")
        self.assertEqual(resp.status_code, 404)

    def test_generate_outline(self):
        resp = self.client.post("/api/v1/projects", json={
            "name": "大纲测试",
            "region": "某县",
            "period": "2026-2030",
            "planning_type": "林业发展规划",
        })
        pid = resp.json()["id"]
        resp = self.client.post(f"/api/v1/projects/{pid}/outline/generate")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreater(data["chapters"], 0)
        self.assertGreater(data["sections"], 0)

    def test_get_outline(self):
        resp = self.client.post("/api/v1/projects", json={
            "name": "大纲查询测试",
            "region": "某县",
            "period": "2026-2030",
            "planning_type": "林业",
        })
        pid = resp.json()["id"]
        self.client.post(f"/api/v1/projects/{pid}/outline/generate")
        resp = self.client.get(f"/api/v1/projects/{pid}/outline")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)
        self.assertGreater(len(resp.json()), 0)

    def test_get_tasks(self):
        resp = self.client.post("/api/v1/projects", json={
            "name": "任务测试",
            "region": "某县",
            "period": "2026-2030",
            "planning_type": "林业",
        })
        pid = resp.json()["id"]
        self.client.post(f"/api/v1/projects/{pid}/outline/generate")
        resp = self.client.get(f"/api/v1/projects/{pid}/tasks")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_generate_drafts(self):
        resp = self.client.post("/api/v1/projects", json={
            "name": "草稿测试",
            "region": "某县",
            "period": "2026-2030",
            "planning_type": "林业",
        })
        pid = resp.json()["id"]
        self.client.post(f"/api/v1/projects/{pid}/outline/generate")
        resp = self.client.post(f"/api/v1/projects/{pid}/generate?skip_llm=true")
        self.assertEqual(resp.status_code, 200)

    def test_quality_check(self):
        resp = self.client.post("/api/v1/projects", json={
            "name": "质检测试",
            "region": "某县",
            "period": "2026-2030",
            "planning_type": "林业",
        })
        pid = resp.json()["id"]
        self.client.post(f"/api/v1/projects/{pid}/outline/generate")
        self.client.post(f"/api/v1/projects/{pid}/generate?skip_llm=true")
        resp = self.client.post(f"/api/v1/projects/{pid}/quality-check")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("total", data)
        self.assertIn("errors", data)
        self.assertIn("warnings", data)

    def test_delete_project(self):
        resp = self.client.post("/api/v1/projects", json={
            "name": "删除测试",
            "region": "某县",
            "period": "2026-2030",
            "planning_type": "林业",
        })
        pid = resp.json()["id"]
        resp = self.client.delete(f"/api/v1/projects/{pid}")
        self.assertEqual(resp.status_code, 200)
        # Verify deleted
        resp = self.client.get(f"/api/v1/projects/{pid}")
        self.assertEqual(resp.status_code, 404)


class NoFastAPITest(unittest.TestCase):
    """Tests that work without FastAPI - verify module structure."""

    def test_server_module_exists(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "lin_cao_planner", "server.py"
        )
        self.assertTrue(os.path.exists(path))

    def test_server_has_routes(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "lin_cao_planner", "server.py"
        )
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("FastAPI", content)
        self.assertIn("/api/v1/projects", content)
        self.assertIn("/api/v1/health", content)


if __name__ == "__main__":
    unittest.main()
