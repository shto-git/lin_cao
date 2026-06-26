"""SQLite persistence layer for lin_cao planning system.

Provides a Database class with CRUD operations for all domain objects.
Uses Python standard library sqlite3 only — no external dependencies.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime
from typing import Any


DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "lin_cao.db")

SQL_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    region TEXT NOT NULL,
    period TEXT NOT NULL,
    level TEXT,
    planning_type TEXT NOT NULL,
    target_words INTEGER DEFAULT 50000,
    owner_department TEXT,
    drafting_unit TEXT,
    status TEXT DEFAULT 'active',
    ragflow_dataset_id TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    file_name TEXT NOT NULL,
    file_path TEXT,
    file_type TEXT,
    file_size INTEGER,
    source_unit TEXT,
    publish_year INTEGER,
    applicable_region TEXT,
    applicable_planning_types TEXT,
    is_formal_reference INTEGER DEFAULT 1,
    category TEXT,
    ragflow_document_id TEXT,
    parse_status TEXT DEFAULT 'pending',
    chunk_count INTEGER,
    description TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS outline_nodes (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    parent_id TEXT REFERENCES outline_nodes(id),
    title TEXT NOT NULL,
    level INTEGER NOT NULL,
    target_words INTEGER,
    sort_order INTEGER,
    requirements TEXT,
    required_evidence_types TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS section_tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    outline_id TEXT NOT NULL REFERENCES outline_nodes(id),
    title_path TEXT,
    target_words INTEGER,
    retrieval_queries TEXT,
    required_evidence_types TEXT,
    writing_constraints TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS evidences (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    section_task_id TEXT REFERENCES section_tasks(id),
    title TEXT,
    source_type TEXT,
    source_name TEXT,
    quote TEXT,
    similarity REAL,
    chunk_id TEXT,
    metadata TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chapter_drafts (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    outline_id TEXT NOT NULL REFERENCES outline_nodes(id),
    title TEXT,
    content TEXT,
    word_count INTEGER,
    evidence_ids TEXT,
    status TEXT DEFAULT 'draft',
    version INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS quality_reports (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    status TEXT DEFAULT 'completed',
    total_findings INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    warning_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS quality_findings (
    id TEXT PRIMARY KEY,
    report_id TEXT NOT NULL REFERENCES quality_reports(id),
    severity TEXT NOT NULL,
    code TEXT NOT NULL,
    message TEXT NOT NULL,
    location TEXT,
    suggestion TEXT,
    status TEXT DEFAULT 'open',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS export_tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    format TEXT NOT NULL,
    file_path TEXT,
    status TEXT DEFAULT 'pending',
    error_message TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_documents_project ON documents(project_id);
CREATE INDEX IF NOT EXISTS idx_outline_nodes_project ON outline_nodes(project_id);
CREATE INDEX IF NOT EXISTS idx_section_tasks_project ON section_tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_section_tasks_outline ON section_tasks(outline_id);
CREATE INDEX IF NOT EXISTS idx_evidences_task ON evidences(section_task_id);
CREATE INDEX IF NOT EXISTS idx_chapter_drafts_project ON chapter_drafts(project_id);
CREATE INDEX IF NOT EXISTS idx_quality_findings_report ON quality_findings(report_id);
CREATE INDEX IF NOT EXISTS idx_export_tasks_project ON export_tasks(project_id);
"""


def _gen_id() -> str:
    return str(uuid.uuid4())


def _now() -> str:
    return datetime.utcnow().isoformat()


class Database:
    """SQLite database manager for lin_cao planning system.

    Usage:
        with Database() as db:
            project_id = db.save_project(project_info)
            outline = db.list_outline_nodes(project_id)
    """

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or DB_PATH
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> "Database":
        self.connect()
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def connect(self) -> None:
        dir_name = os.path.dirname(self.db_path)
        if dir_name and self.db_path != ":memory:":
            os.makedirs(dir_name, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = OFF")
        self._create_tables()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def _create_tables(self) -> None:
        assert self._conn is not None
        self._conn.executescript(SQL_CREATE_TABLES)
        self._conn.commit()

    def _execute(self, sql: str, params: tuple | dict = ()) -> sqlite3.Cursor:
        assert self._conn is not None
        return self._conn.execute(sql, params)

    def _executemany(self, sql: str, seq: list) -> None:
        assert self._conn is not None
        self._conn.executemany(sql, seq)
        self._conn.commit()

    @staticmethod
    def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return dict(row)

    @staticmethod
    def _rows_to_list(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
        return [dict(r) for r in rows]

    # ── Projects ──────────────────────────────────────────

    def save_project(
        self,
        name: str,
        region: str,
        period: str,
        planning_type: str,
        level: str = "",
        target_words: int = 50000,
        owner_department: str = "",
        drafting_unit: str = "",
        project_id: str | None = None,
    ) -> str:
        pid = project_id or _gen_id()
        self._execute(
            """INSERT OR REPLACE INTO projects
               (id, name, region, period, level, planning_type, target_words,
                owner_department, drafting_unit, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (pid, name, region, period, level, planning_type, target_words,
             owner_department, drafting_unit, _now()),
        )
        self._conn.commit()
        return pid

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        cur = self._execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        return self._row_to_dict(cur.fetchone())

    def list_projects(self, status: str | None = None) -> list[dict[str, Any]]:
        if status:
            cur = self._execute(
                "SELECT * FROM projects WHERE status = ? ORDER BY created_at DESC",
                (status,),
            )
        else:
            cur = self._execute("SELECT * FROM projects ORDER BY created_at DESC")
        return self._rows_to_list(cur.fetchall())

    def delete_project(self, project_id: str) -> bool:
        cur = self._execute("DELETE FROM projects WHERE id = ?", (project_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def update_document_ragflow_id(self, doc_id: str, ragflow_id: str) -> None:
        self._execute(
            "UPDATE documents SET ragflow_document_id = ? WHERE id = ?",
            (ragflow_id, doc_id),
        )
        self._conn.commit()

    def update_document_chunk_count(self, doc_id: str, chunk_count: int) -> None:
        self._execute(
            "UPDATE documents SET chunk_count = ?, parse_status = 'completed' WHERE id = ?",
            (chunk_count, doc_id),
        )
        self._conn.commit()

    def clear_section_tasks(self, project_id: str) -> None:
        cur = self._execute("DELETE FROM section_tasks WHERE project_id = ?", (project_id,))
        self._conn.commit()


    # ── Documents ─────────────────────────────────────────

    def save_document(
        self,
        project_id: str,
        file_name: str,
        file_path: str = "",
        file_type: str = "",
        file_size: int = 0,
        source_unit: str = "",
        publish_year: int | None = None,
        category: str = "",
        doc_id: str | None = None,
    ) -> str:
        did = doc_id or _gen_id()
        self._execute(
            """INSERT OR REPLACE INTO documents
               (id, project_id, file_name, file_path, file_type, file_size,
                source_unit, publish_year, category)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (did, project_id, file_name, file_path, file_type, file_size,
             source_unit, publish_year, category),
        )
        self._conn.commit()
        return did

    def get_document(self, doc_id: str) -> dict[str, Any] | None:
        cur = self._execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        return self._row_to_dict(cur.fetchone())

    def list_documents(self, project_id: str) -> list[dict[str, Any]]:
        cur = self._execute(
            "SELECT * FROM documents WHERE project_id = ? ORDER BY created_at",
            (project_id,),
        )
        return self._rows_to_list(cur.fetchall())

    def delete_document(self, doc_id: str) -> bool:
        cur = self._execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        self._conn.commit()
        return cur.rowcount > 0

    # ── Outline Nodes ─────────────────────────────────────

    def save_outline_node(
        self,
        project_id: str,
        title: str,
        level: int,
        node_id: str | None = None,
        parent_id: str | None = None,
        target_words: int | None = None,
        sort_order: int | None = None,
        requirements: list[str] | None = None,
        required_evidence_types: list[str] | None = None,
    ) -> str:
        nid = node_id or _gen_id()
        self._execute(
            """INSERT OR REPLACE INTO outline_nodes
               (id, project_id, parent_id, title, level, target_words,
                sort_order, requirements, required_evidence_types)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (nid, project_id, parent_id, title, level, target_words,
             sort_order,
             json.dumps(requirements or [], ensure_ascii=False),
             json.dumps(required_evidence_types or [], ensure_ascii=False)),
        )
        self._conn.commit()
        return nid

    def get_outline_node(self, node_id: str) -> dict[str, Any] | None:
        cur = self._execute("SELECT * FROM outline_nodes WHERE id = ?", (node_id,))
        return self._row_to_dict(cur.fetchone())

    def list_outline_nodes(self, project_id: str) -> list[dict[str, Any]]:
        cur = self._execute(
            "SELECT * FROM outline_nodes WHERE project_id = ? ORDER BY sort_order, id",
            (project_id,),
        )
        return self._rows_to_list(cur.fetchall())

    def delete_outline_node(self, node_id: str) -> bool:
        cur = self._execute("DELETE FROM outline_nodes WHERE id = ?", (node_id,))
        self._conn.commit()
        return cur.rowcount > 0

    # ── Section Tasks ─────────────────────────────────────

    def save_section_task(
        self,
        project_id: str,
        outline_id: str,
        title_path: list[str],
        target_words: int,
        retrieval_queries: list[str],
        required_evidence_types: list[str],
        writing_constraints: list[str] | None = None,
        status: str = "pending",
        task_id: str | None = None,
    ) -> str:
        tid = task_id or _gen_id()
        self._execute(
            """INSERT OR REPLACE INTO section_tasks
               (id, project_id, outline_id, title_path, target_words,
                retrieval_queries, required_evidence_types, writing_constraints, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (tid, project_id, outline_id, json.dumps(title_path, ensure_ascii=False),
             target_words, json.dumps(retrieval_queries, ensure_ascii=False),
             json.dumps(required_evidence_types, ensure_ascii=False),
             json.dumps(writing_constraints or [], ensure_ascii=False),
             status),
        )
        self._conn.commit()
        return tid

    def get_section_task(self, task_id: str) -> dict[str, Any] | None:
        cur = self._execute("SELECT * FROM section_tasks WHERE id = ?", (task_id,))
        return self._row_to_dict(cur.fetchone())

    def list_section_tasks(self, project_id: str) -> list[dict[str, Any]]:
        cur = self._execute(
            "SELECT * FROM section_tasks WHERE project_id = ? ORDER BY outline_id",
            (project_id,),
        )
        return self._rows_to_list(cur.fetchall())

    def delete_section_task(self, task_id: str) -> bool:
        cur = self._execute("DELETE FROM section_tasks WHERE id = ?", (task_id,))
        self._conn.commit()
        return cur.rowcount > 0

    # ── Evidences ─────────────────────────────────────────

    def save_evidence(
        self,
        project_id: str,
        section_task_id: str,
        title: str = "",
        source_type: str = "",
        source_name: str = "",
        quote: str = "",
        similarity: float = 0.0,
        chunk_id: str = "",
        metadata: dict | None = None,
        evidence_id: str | None = None,
    ) -> str:
        eid = evidence_id or _gen_id()
        self._execute(
            """INSERT OR REPLACE INTO evidences
               (id, project_id, section_task_id, title, source_type,
                source_name, quote, similarity, chunk_id, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (eid, project_id, section_task_id, title, source_type,
             source_name, quote, similarity, chunk_id,
             json.dumps(metadata or {}, ensure_ascii=False)),
        )
        self._conn.commit()
        return eid

    def get_evidence(self, evidence_id: str) -> dict[str, Any] | None:
        cur = self._execute("SELECT * FROM evidences WHERE id = ?", (evidence_id,))
        return self._row_to_dict(cur.fetchone())

    def list_evidences(self, section_task_id: str) -> list[dict[str, Any]]:
        cur = self._execute(
            "SELECT * FROM evidences WHERE section_task_id = ? ORDER BY similarity DESC",
            (section_task_id,),
        )
        return self._rows_to_list(cur.fetchall())

    def delete_evidence(self, evidence_id: str) -> bool:
        cur = self._execute("DELETE FROM evidences WHERE id = ?", (evidence_id,))
        self._conn.commit()
        return cur.rowcount > 0

    # ── Chapter Drafts ────────────────────────────────────

    def save_chapter_draft(
        self,
        project_id: str,
        outline_id: str,
        title: str,
        content: str,
        evidence_ids: list[str] | None = None,
        status: str = "draft",
        version: int = 1,
        draft_id: str | None = None,
    ) -> str:
        did = draft_id or _gen_id()
        word_count = len(content)
        self._execute(
            """INSERT OR REPLACE INTO chapter_drafts
               (id, project_id, outline_id, title, content, word_count,
                evidence_ids, status, version, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (did, project_id, outline_id, title, content, word_count,
             json.dumps(evidence_ids or [], ensure_ascii=False),
             status, version, _now()),
        )
        self._conn.commit()
        return did

    def get_chapter_draft(self, draft_id: str) -> dict[str, Any] | None:
        cur = self._execute("SELECT * FROM chapter_drafts WHERE id = ?", (draft_id,))
        return self._row_to_dict(cur.fetchone())

    def list_chapter_drafts(self, project_id: str) -> list[dict[str, Any]]:
        cur = self._execute(
            "SELECT * FROM chapter_drafts WHERE project_id = ? ORDER BY outline_id",
            (project_id,),
        )
        return self._rows_to_list(cur.fetchall())

    def delete_chapter_draft(self, draft_id: str) -> bool:
        cur = self._execute("DELETE FROM chapter_drafts WHERE id = ?", (draft_id,))
        self._conn.commit()
        return cur.rowcount > 0

    # ── Quality Reports ───────────────────────────────────

    def save_quality_report(
        self,
        project_id: str,
        total_findings: int = 0,
        error_count: int = 0,
        warning_count: int = 0,
        status: str = "completed",
        report_id: str | None = None,
    ) -> str:
        rid = report_id or _gen_id()
        self._execute(
            """INSERT OR REPLACE INTO quality_reports
               (id, project_id, status, total_findings, error_count, warning_count)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (rid, project_id, status, total_findings, error_count, warning_count),
        )
        self._conn.commit()
        return rid

    def get_quality_report(self, report_id: str) -> dict[str, Any] | None:
        cur = self._execute("SELECT * FROM quality_reports WHERE id = ?", (report_id,))
        return self._row_to_dict(cur.fetchone())

    def list_quality_reports(self, project_id: str) -> list[dict[str, Any]]:
        cur = self._execute(
            "SELECT * FROM quality_reports WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,),
        )
        return self._rows_to_list(cur.fetchall())

    def delete_quality_report(self, report_id: str) -> bool:
        cur = self._execute("DELETE FROM quality_reports WHERE id = ?", (report_id,))
        self._conn.commit()
        return cur.rowcount > 0

    # ── Quality Findings ──────────────────────────────────

    def save_quality_finding(
        self,
        report_id: str,
        severity: str,
        code: str,
        message: str,
        location: str = "",
        suggestion: str = "",
        status: str = "open",
        finding_id: str | None = None,
    ) -> str:
        fid = finding_id or _gen_id()
        self._execute(
            """INSERT OR REPLACE INTO quality_findings
               (id, report_id, severity, code, message, location, suggestion, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (fid, report_id, severity, code, message, location, suggestion, status),
        )
        self._conn.commit()
        return fid

    def get_quality_finding(self, finding_id: str) -> dict[str, Any] | None:
        cur = self._execute("SELECT * FROM quality_findings WHERE id = ?", (finding_id,))
        return self._row_to_dict(cur.fetchone())

    def list_quality_findings(self, report_id: str) -> list[dict[str, Any]]:
        cur = self._execute(
            "SELECT * FROM quality_findings WHERE report_id = ? ORDER BY severity, code",
            (report_id,),
        )
        return self._rows_to_list(cur.fetchall())

    def delete_quality_finding(self, finding_id: str) -> bool:
        cur = self._execute("DELETE FROM quality_findings WHERE id = ?", (finding_id,))
        self._conn.commit()
        return cur.rowcount > 0

    # ── Export Tasks ──────────────────────────────────────

    def save_export_task(
        self,
        project_id: str,
        format: str,
        file_path: str = "",
        status: str = "pending",
        error_message: str = "",
        task_id: str | None = None,
    ) -> str:
        tid = task_id or _gen_id()
        self._execute(
            """INSERT OR REPLACE INTO export_tasks
               (id, project_id, format, file_path, status, error_message)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (tid, project_id, format, file_path, status, error_message),
        )
        self._conn.commit()
        return tid

    def get_export_task(self, task_id: str) -> dict[str, Any] | None:
        cur = self._execute("SELECT * FROM export_tasks WHERE id = ?", (task_id,))
        return self._row_to_dict(cur.fetchone())

    def list_export_tasks(self, project_id: str) -> list[dict[str, Any]]:
        cur = self._execute(
            "SELECT * FROM export_tasks WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,),
        )
        return self._rows_to_list(cur.fetchall())

    def delete_export_task(self, task_id: str) -> bool:
        cur = self._execute("DELETE FROM export_tasks WHERE id = ?", (task_id,))
        self._conn.commit()
        return cur.rowcount > 0
