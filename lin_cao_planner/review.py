"""Review comment management and closed-loop revision handling.

Supports: submit review → locate chapter → apply revision → re-review.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ReviewComment:
    """A single review comment targeting a specific chapter/section."""
    id: str = ""
    project_id: str = ""
    chapter_id: str = ""  # outline_id of the targeted chapter
    severity: str = "info"  # error, warning, info
    content: str = ""  # review comment text
    suggestion: str = ""  # suggested revision
    status: str = "open"  # open, in_progress, resolved, rejected
    reviewer: str = ""
    created_at: str = ""
    resolved_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "chapter_id": self.chapter_id,
            "severity": self.severity,
            "content": self.content,
            "suggestion": self.suggestion,
            "status": self.status,
            "reviewer": self.reviewer,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
        }


def submit_review(
    project_id: str,
    chapter_id: str,
    severity: str,
    content: str,
    suggestion: str = "",
    reviewer: str = "",
) -> ReviewComment:
    """Submit a new review comment."""
    comment = ReviewComment(
        id=str(uuid.uuid4())[:8],
        project_id=project_id,
        chapter_id=chapter_id,
        severity=severity,
        content=content,
        suggestion=suggestion,
        reviewer=reviewer or "匿名专家",
        created_at=datetime.now().isoformat(),
    )
    return comment


def group_reviews_by_chapter(reviews: list[ReviewComment]) -> dict[str, list[ReviewComment]]:
    """Group review comments by chapter."""
    groups: dict[str, list[ReviewComment]] = {}
    for r in reviews:
        if r.chapter_id not in groups:
            groups[r.chapter_id] = []
        groups[r.chapter_id].append(r)
    return groups


def check_review_resolution(reviews: list[ReviewComment]) -> dict[str, Any]:
    """Check overall review resolution status."""
    total = len(reviews)
    resolved = sum(1 for r in reviews if r.status == "resolved")
    open_count = sum(1 for r in reviews if r.status == "open")
    in_progress = sum(1 for r in reviews if r.status == "in_progress")
    error_count = sum(1 for r in reviews if r.severity == "error" and r.status != "resolved")

    return {
        "total": total,
        "resolved": resolved,
        "open": open_count,
        "in_progress": in_progress,
        "blocking_errors": error_count,
        "resolution_rate": (resolved / total * 100) if total > 0 else 100,
        "is_approved": error_count == 0 and open_count == 0,
    }
