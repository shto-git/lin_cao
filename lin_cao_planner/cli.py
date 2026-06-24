from __future__ import annotations

import argparse
import json
from pathlib import Path

from .domain import ProjectInfo
from .evidence import build_retrieval_plan
from .outline import build_default_outline
from .renderer import render_outline, render_retrieval_plan


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate forestry planning outline and retrieval tasks.")
    parser.add_argument("project_json", help="Path to project JSON.")
    parser.add_argument("--out", default="dist/demo", help="Output directory.")
    args = parser.parse_args()

    project_path = Path(args.project_json)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    data = json.loads(project_path.read_text(encoding="utf-8"))
    project = ProjectInfo.from_mapping(data)
    outline = build_default_outline(project)
    briefs = build_retrieval_plan(project, outline)

    (out_dir / "outline.md").write_text(render_outline(outline), encoding="utf-8")
    (out_dir / "retrieval_plan.md").write_text(render_retrieval_plan(briefs), encoding="utf-8")
    print(f"Wrote {out_dir / 'outline.md'}")
    print(f"Wrote {out_dir / 'retrieval_plan.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
