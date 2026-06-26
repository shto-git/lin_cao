"""FastAPI web service for lin_cao planning system."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

try:
    from fastapi import FastAPI, HTTPException, UploadFile, File
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    from pydantic import BaseModel, Field
except ImportError:
    raise ImportError(
        "FastAPI dependencies missing. Install with: pip install fastapi uvicorn pydantic"
    )

from lin_cao_planner import (
    Database,
    LLMConfig,
    PipelineConfig,
    ProjectInfo,
    build_default_outline,
    build_retrieval_plan,
    generate_chapter_draft,
    run_pipeline,
    validate_document,
    EvidenceChunk,
)

app = FastAPI(
    title="林草规划智能编制 API",
    description="林草专业规划长文本智能编制系统后端服务",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.environ.get("LINCAO_DB_PATH", str(Path(__file__).parent.parent / "data" / "lin_cao.db"))


def get_db() -> Database:
    db = Database(db_path=DB_PATH)
    db.connect()
    return db


# ── Request/Response Models ──────────────────────────────

class CreateProjectRequest(BaseModel):
    name: str
    region: str
    period: str
    planning_type: str
    level: str = ""
    target_words: int = 50000
    owner_department: str = ""
    drafting_unit: str = ""


class GenerateOutlineRequest(BaseModel):
    project_id: str
    planning_type: str = ""
    target_words: int = 0


class GenerateFullRequest(BaseModel):
    project_id: str
    skip_llm: bool = False


class LLMConfigRequest(BaseModel):
    api_key: str = ""
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-chat"


# ── API: Projects ───────────────────────────────────────

@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.2.0"}


@app.post("/api/v1/projects")
def create_project(req: CreateProjectRequest) -> dict[str, Any]:
    db = get_db()
    pid = db.save_project(
        name=req.name,
        region=req.region,
        period=req.period,
        planning_type=req.planning_type,
        level=req.level,
        target_words=req.target_words,
        owner_department=req.owner_department,
        drafting_unit=req.drafting_unit,
    )
    db.close()
    return {"id": pid, "message": "项目创建成功"}


@app.get("/api/v1/projects")
def list_projects() -> list[dict[str, Any]]:
    db = get_db()
    projects = db.list_projects()
    db.close()
    return projects


@app.get("/api/v1/projects/{project_id}")
def get_project(project_id: str) -> dict[str, Any]:
    db = get_db()
    project = db.get_project(project_id)
    db.close()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


@app.delete("/api/v1/projects/{project_id}")
def delete_project(project_id: str) -> dict[str, str]:
    db = get_db()
    ok = db.delete_project(project_id)
    db.close()
    if not ok:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"message": "项目已删除"}


# ── API: Outline ────────────────────────────────────────

@app.post("/api/v1/projects/{project_id}/outline/generate")
def generate_outline(project_id: str) -> dict[str, Any]:
    db = get_db()
    project_data = db.get_project(project_id)
    if not project_data:
        db.close()
        raise HTTPException(status_code=404, detail="项目不存在")

    project = ProjectInfo(
        name=project_data["name"],
        region=project_data["region"],
        period=project_data["period"],
        level=project_data.get("level", ""),
        planning_type=project_data["planning_type"],
        target_words=project_data.get("target_words", 50000),
    )
    outline = build_default_outline(project)

    # Save outline nodes to DB
    _save_outline_tree(db, project_id, outline)

    briefs = build_retrieval_plan(project, outline)
    # Save section tasks to DB
    for brief in briefs:
        db.save_section_task(
            project_id=project_id,
            outline_id=brief.outline_id,
            title_path=brief.title_path,
            target_words=brief.target_words,
            retrieval_queries=brief.retrieval_queries,
            required_evidence_types=brief.required_evidence_types,
            writing_constraints=brief.writing_constraints,
        )

    db.close()
    return {
        "message": "大纲生成成功",
        "chapters": len(outline.children),
        "sections": len(outline.leaves()),
    }


def _save_outline_tree(db: Database, project_id: str, node: Any, parent_id: str | None = None) -> None:
    """Recursively save outline nodes."""
    nid = db.save_outline_node(
        project_id=project_id,
        title=node.title,
        level=node.level,
        node_id=node.id,
        parent_id=parent_id,
        target_words=node.target_words,
        sort_order=int(node.id.split(".")[0]) if node.id != "root" else 0,
        requirements=node.requirements,
        required_evidence_types=node.required_evidence_types,
    )
    for child in node.children:
        _save_outline_tree(db, project_id, child, parent_id=nid if node.id != "root" else None)


@app.get("/api/v1/projects/{project_id}/outline")
def get_outline(project_id: str) -> list[dict[str, Any]]:
    db = get_db()
    nodes = db.list_outline_nodes(project_id)
    db.close()
    return nodes



# ── API: Documents ──────────────────────────────────────

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".md", ".txt", ".csv", ".doc", ".xls"}

@app.post("/api/v1/projects/{project_id}/documents")
async def upload_document(
    project_id: str,
    file: UploadFile = File(...),
    description: str = Form(""),
) -> dict[str, Any]:
    """上传资料并入库"""
    db = get_db()
    project = db.get_project(project_id)
    if not project:
        db.close()
        raise HTTPException(status_code=404, detail="项目不存在")

    # 检查文件扩展名
    file_ext = os.path.splitext(file.filename or "")[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        db.close()
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {file_ext}。支持: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # 保存文件
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "uploads", project_id)
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename or "unknown")
    with open(file_path, "wb") as f:
        content_bytes = await file.read()
        f.write(content_bytes)

    # 保存到数据库
    doc_id = db.save_document(
        project_id=project_id,
        file_name=file.filename or "unknown",
        file_path=file_path,
        file_type=file_ext,
        file_size=len(content_bytes),
        description=description,
    )

    # 尝试上传到 RAGFlow
    ragflow_dataset_id = project.get("ragflow_dataset_id")
    if ragflow_dataset_id:
        try:
            from lin_cao_planner.ragflow_client import RagflowClient
            from lin_cao_planner import LLMConfig
            llm_config = LLMConfig.from_env()
            rag_client = RagflowClient(
                base_url=llm_config.ragflow_base_url or "http://localhost:9380",
                api_key=llm_config.ragflow_api_key or "",
            )
            rag_doc_id = rag_client.upload_document(ragflow_dataset_id, file_path)
            if rag_doc_id:
                db.update_document_ragflow_id(doc_id, rag_doc_id)
                # 触发解析
                rag_client.parse_documents(ragflow_dataset_id, [rag_doc_id])
                # 更新 chunk count
                chunk_count = rag_client.get_chunk_count(ragflow_dataset_id, rag_doc_id)
                db.update_document_chunk_count(doc_id, chunk_count)
        except Exception:
            pass  # RAGFlow 上传失败不影响本地入库

    db.close()
    return {
        "id": doc_id,
        "file_name": file.filename,
        "file_type": file_ext,
        "file_size": len(content_bytes),
        "parse_status": "completed",
        "message": "资料上传成功",
    }


@app.get("/api/v1/projects/{project_id}/documents")
def list_documents(project_id: str) -> list[dict[str, Any]]:
    """获取项目资料列表"""
    db = get_db()
    docs = db.list_documents(project_id)
    db.close()
    return docs


@app.delete("/api/v1/projects/{project_id}/documents/{doc_id}")
def delete_document(project_id: str, doc_id: str) -> dict[str, Any]:
    """删除资料"""
    db = get_db()
    doc = db.get_document(doc_id)
    if not doc or doc.get("project_id") != project_id:
        db.close()
        raise HTTPException(status_code=404, detail="资料不存在")
    # 删除本地文件
    file_path = doc.get("file_path", "")
    if file_path and os.path.exists(file_path):
        os.remove(file_path)
    db.delete_document(doc_id)
    db.close()
    return {"message": "资料已删除"}


# ── API: Section Tasks ──────────────────────────────────

@app.get("/api/v1/projects/{project_id}/tasks")
def get_tasks(project_id: str) -> list[dict[str, Any]]:
    db = get_db()
    tasks = db.list_section_tasks(project_id)
    db.close()
    return tasks


@app.get("/api/v1/projects/{project_id}/tasks/{task_id}")
def get_task(project_id: str, task_id: str) -> dict[str, Any]:
    db = get_db()
    task = db.get_section_task(task_id)
    db.close()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@app.post("/api/v1/projects/{project_id}/tasks/generate")
def generate_tasks(project_id: str) -> dict[str, Any]:
    """基于大纲生成章节检索任务"""
    db = get_db()
    project_data = db.get_project(project_id)
    if not project_data:
        db.close()
        raise HTTPException(status_code=404, detail="项目不存在")

    project = ProjectInfo(
        name=project_data["name"],
        region=project_data["region"],
        period=project_data["period"],
        level=project_data.get("level", ""),
        planning_type=project_data["planning_type"],
        target_words=project_data.get("target_words", 50000),
    )

    outline = build_default_outline(project)
    briefs = build_retrieval_plan(project, outline)

    # 清除旧的检索任务
    db.clear_section_tasks(project_id)

    # 保存新的检索任务
    task_count = 0
    for brief in briefs:
        db.save_section_task(
            project_id=project_id,
            outline_id=brief.outline_id,
            title_path=brief.title_path,
            target_words=brief.target_words,
            retrieval_queries=brief.retrieval_queries,
            required_evidence_types=brief.required_evidence_types,
            writing_constraints=brief.writing_constraints,
        )
        task_count += 1

    db.close()
    return {
        "message": f"已生成 {task_count} 个章节检索任务",
        "tasks": task_count,
    }


# ── API: Draft Generation ───────────────────────────────

@app.post("/api/v1/projects/{project_id}/generate")
def generate_drafts(project_id: str, skip_llm: bool = False) -> dict[str, Any]:
    db = get_db()
    project_data = db.get_project(project_id)
    if not project_data:
        db.close()
        raise HTTPException(status_code=404, detail="项目不存在")

    project = ProjectInfo(
        name=project_data["name"],
        region=project_data["region"],
        period=project_data["period"],
        level=project_data.get("level", ""),
        planning_type=project_data["planning_type"],
        target_words=project_data.get("target_words", 50000),
    )

    outline = build_default_outline(project)
    briefs = build_retrieval_plan(project, outline)

    llm_config = LLMConfig.from_env()
    generated_count = 0

    for brief in briefs:
        gen_result = generate_chapter_draft(
            outline_id=brief.outline_id,
            title_path=" / ".join(brief.title_path),
            target_words=brief.target_words,
            requirements=brief.writing_constraints[:3],
            evidence_types=brief.required_evidence_types,
            constraints=brief.writing_constraints,
            evidence_chunks=[],  # No RAG in API mode for now
            llm_client=None if skip_llm else None,  # Will use env config
        )
        db.save_chapter_draft(
            project_id=project_id,
            outline_id=brief.outline_id,
            title=gen_result.title,
            content=gen_result.content,
            evidence_ids=gen_result.evidence_ids,
        )
        generated_count += 1

    db.close()
    return {"message": f"已生成 {generated_count} 个章节草稿"}


# ── API: Chapter Drafts ─────────────────────────────────

@app.get("/api/v1/projects/{project_id}/drafts")
def get_drafts(project_id: str) -> list[dict[str, Any]]:
    db = get_db()
    drafts = db.list_chapter_drafts(project_id)
    db.close()
    return drafts


@app.get("/api/v1/projects/{project_id}/drafts/{outline_id}")
def get_draft(project_id: str, outline_id: str) -> dict[str, str]:
    db = get_db()
    drafts = db.list_chapter_drafts(project_id)
    db.close()
    for draft in drafts:
        if draft["outline_id"] == outline_id:
            return draft
    raise HTTPException(status_code=404, detail="草稿不存在")


@app.post("/api/v1/projects/{project_id}/tasks/{task_id}/generate-draft")
def generate_single_draft(project_id: str, task_id: str, skip_llm: bool = False) -> dict[str, Any]:
    """为单个章节任务生成草稿"""
    db = get_db()
    task = db.get_section_task(task_id)
    if not task or task.get("project_id") != project_id:
        db.close()
        raise HTTPException(status_code=404, detail="任务不存在")

    from lin_cao_planner import ChapterDraft
    from lin_cao_planner.generator import generate_chapter_draft, EvidenceChunk, LLMConfig, LLMClient
    from lin_cao_planner.domain import SectionBrief

    # 构建 SectionBrief
    brief = SectionBrief(
        outline_id=task["outline_id"],
        title_path=json.loads(task.get("title_path", "[]")) if isinstance(task.get("title_path"), str) else task.get("title_path", []),
        target_words=task.get("target_words", 3000),
        retrieval_queries=json.loads(task.get("retrieval_queries", "[]")) if isinstance(task.get("retrieval_queries"), str) else task.get("retrieval_queries", []),
        required_evidence_types=json.loads(task.get("required_evidence_types", "[]")) if isinstance(task.get("required_evidence_types"), str) else task.get("required_evidence_types", []),
        writing_constraints=json.loads(task.get("writing_constraints", "[]")) if isinstance(task.get("writing_constraints"), str) else task.get("writing_constraints", []),
    )

    # 获取证据（如果有 RAGFlow）
    evidence_chunks: list[EvidenceChunk] = []
    project_data = db.get_project(project_id)
    ragflow_dataset_id = project_data.get("ragflow_dataset_id") if project_data else None
    
    if ragflow_dataset_id and brief.retrieval_queries:
        try:
            from lin_cao_planner.ragflow_client import RagflowClient
            llm_config = LLMConfig.from_env()
            rag_client = RagflowClient(
                base_url=llm_config.ragflow_base_url or "http://localhost:9380",
                api_key=llm_config.ragflow_api_key or "",
            )
            # 用第一条检索问题检索
            chunks = rag_client.retrieve_chunks(
                dataset_id=ragflow_dataset_id,
                question=brief.retrieval_queries[0],
                page_size=5,
            )
            for i, chunk in enumerate(chunks):
                evidence_chunks.append(EvidenceChunk(
                    content=chunk.get("content", ""),
                    document_name=chunk.get("document_name", "未知"),
                    similarity=chunk.get("similarity", 0.0),
                ))
        except Exception:
            pass  # RAGFlow 检索失败不影响

    # 生成草稿
    llm_config = LLMConfig.from_env()
    llm_client = LLMClient(llm_config) if llm_config.api_key else None

    result = generate_chapter_draft(
        outline_id=brief.outline_id,
        title_path=" / ".join(brief.title_path),
        target_words=brief.target_words,
        requirements=brief.writing_constraints[:3] if brief.writing_constraints else [],
        evidence_types=brief.required_evidence_types,
        constraints=brief.writing_constraints,
        evidence_chunks=evidence_chunks,
        llm_client=llm_client,
    )

    # 保存草稿
    db.save_chapter_draft(
        project_id=project_id,
        outline_id=result.outline_id,
        title=result.title,
        content=result.content,
        evidence_ids=result.evidence_ids,
        status=result.status,
    )

    db.close()
    return {
        "id": result.outline_id,
        "title": result.title,
        "content": result.content,
        "word_count": result.word_count,
        "evidence_ids": result.evidence_ids,
        "status": result.status,
        "warnings": result.warnings,
    }


# ── API: Quality Check ──────────────────────────────────

@app.post("/api/v1/projects/{project_id}/quality-check")
def quality_check(project_id: str) -> dict[str, Any]:
    db = get_db()
    project_data = db.get_project(project_id)
    if not project_data:
        db.close()
        raise HTTPException(status_code=404, detail="项目不存在")

    project = ProjectInfo(
        name=project_data["name"],
        region=project_data["region"],
        period=project_data["period"],
        level=project_data.get("level", ""),
        planning_type=project_data["planning_type"],
        target_words=project_data.get("target_words", 50000),
    )

    outline = build_default_outline(project)
    drafts_data = db.list_chapter_drafts(project_id)
    db.close()

    from lin_cao_planner import ChapterDraft
    drafts = [
        ChapterDraft(
            outline_id=d["outline_id"],
            title=d.get("title", ""),
            content=d.get("content", ""),
            evidence_ids=[],
            status=d.get("status", "draft"),
        )
        for d in drafts_data
    ]

    findings = validate_document(outline, drafts)

    errors = sum(1 for f in findings if f.severity == "error")
    warnings = sum(1 for f in findings if f.severity == "warning")

    return {
        "total": len(findings),
        "errors": errors,
        "warnings": warnings,
        "findings": [
            {
                "severity": f.severity,
                "code": f.code,
                "message": f.message,
                "location": f.location,
                "suggestion": f.suggestion,
            }
            for f in findings
        ],
    }


# ── API: Full Pipeline ──────────────────────────────────

@app.post("/api/v1/projects/{project_id}/run-full")
def run_full_pipeline(project_id: str) -> dict[str, Any]:
    db = get_db()
    project_data = db.get_project(project_id)
    if not project_data:
        db.close()
        raise HTTPException(status_code=404, detail="项目不存在")

    project = ProjectInfo(
        name=project_data["name"],
        region=project_data["region"],
        period=project_data["period"],
        level=project_data.get("level", ""),
        planning_type=project_data["planning_type"],
        target_words=project_data.get("target_words", 50000),
    )

    config = PipelineConfig.from_env()
    config.output_dir = str(Path(__file__).parent.parent / "dist" / project_id)

    result = run_pipeline(project, config)

    # Save to database
    for draft in result.drafts:
        db.save_chapter_draft(
            project_id=project_id,
            outline_id=draft.outline_id,
            title=draft.title,
            content=draft.content,
            evidence_ids=draft.evidence_ids,
            status=draft.status,
        )

    db.close()
    return {
        "message": "完整流程执行成功",
        "chapters": len(result.outline.children),
        "sections": len(result.outline.leaves()),
        "drafts": len(result.drafts),
        "findings": len(result.findings),
        "output_files": result.output_files,
    }


# ── API: Export ─────────────────────────────────────────

@app.post("/api/v1/projects/{project_id}/export/markdown")
def export_markdown(project_id: str) -> dict[str, Any]:
    """导出完整规划文本为 Markdown"""
    db = get_db()
    project_data = db.get_project(project_id)
    if not project_data:
        db.close()
        raise HTTPException(status_code=404, detail="项目不存在")

    project = ProjectInfo(
        name=project_data["name"],
        region=project_data["region"],
        period=project_data["period"],
        level=project_data.get("level", ""),
        planning_type=project_data["planning_type"],
        target_words=project_data.get("target_words", 50000),
    )

    outline = build_default_outline(project)
    drafts_data = db.list_chapter_drafts(project_id)
    findings_data = []  # Optional: run quality check first

    from lin_cao_planner import ChapterDraft
    drafts = [
        ChapterDraft(
            outline_id=d["outline_id"],
            title=d.get("title", ""),
            content=d.get("content", ""),
            evidence_ids=[],
            status=d.get("status", "draft"),
        )
        for d in drafts_data
    ]

    from lin_cao_planner.renderer import render_full_document
    markdown_content = render_full_document(outline, drafts, findings_data if findings_data else None)

    db.close()
    return {
        "content": markdown_content,
        "file_path": f"dist/{project_id}/output.md",
        "word_count": len(markdown_content),
    }


# ── Static Files (Frontend) ─────────────────────────────

STATIC_DIR = Path(__file__).parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def serve_frontend() -> Any:
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "林草规划智能编制 API", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("LINCAO_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
