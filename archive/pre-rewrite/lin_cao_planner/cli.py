"""CLI entry point for the forestry planning pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .domain import ProjectInfo
from .evidence import build_retrieval_plan
from .outline import build_default_outline
from .pipeline import PipelineConfig, run_pipeline
from .renderer import render_outline, render_retrieval_plan, render_quality_report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="林草规划智能编制工具 — 生成大纲、检索计划、章节草稿和质检报告"
    )
    parser.add_argument("project_json", help="项目信息 JSON 文件路径")
    parser.add_argument("--out", default="dist/output", help="输出目录")
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="跳过 LLM 章节生成（仅生成大纲和检索计划）",
    )
    parser.add_argument(
        "--type",
        help="覆盖规划类型（如：林业发展规划、湿地保护修复规划）",
    )
    args = parser.parse_args()

    project_path = Path(args.project_json)
    if not project_path.exists():
        print(f"错误：找不到项目文件 {project_path}", file=sys.stderr)
        return 1

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load project
    data = json.loads(project_path.read_text(encoding="utf-8"))
    if args.type:
        data["planning_type"] = args.type
    project = ProjectInfo.from_mapping(data)

    print(f"📋 项目：{project.name}")
    print(f"📍 区域：{project.region}")
    print(f"📅 期限：{project.period}")
    print(f"📝 类型：{project.planning_type}")
    print(f"📏 目标字数：{project.target_words}")
    print()

    # Build config
    config = PipelineConfig.from_env()
    config.output_dir = str(out_dir)

    if args.skip_llm:
        # Simple mode: outline + retrieval plan only
        print("🔄 生成大纲...")
        outline = build_default_outline(project)
        print(f"   {len(outline.children)} 章，{len(outline.leaves())} 节")

        print("🔄 生成检索计划...")
        briefs = build_retrieval_plan(project, outline)
        print(f"   {len(briefs)} 个章节任务")

        # Export
        outline_path = out_dir / "outline.md"
        outline_path.write_text(render_outline(outline), encoding="utf-8")
        print(f"✅ 大纲：{outline_path}")

        retrieval_path = out_dir / "retrieval_plan.md"
        retrieval_path.write_text(render_retrieval_plan(briefs), encoding="utf-8")
        print(f"✅ 检索计划：{retrieval_path}")

    else:
        # Full pipeline
        print("🚀 运行完整流程...")
        result = run_pipeline(project, config)

        print(f"\n📊 结果：")
        print(f"   大纲：{len(result.outline.children)} 章，{len(result.outline.leaves())} 节")
        print(f"   检索计划：{len(result.briefs)} 个任务")
        print(f"   草稿：{len(result.drafts)} 个章节")
        print(f"   质检发现：{len(result.findings)} 个问题")

        if result.findings:
            errors = sum(1 for f in result.findings if f.severity == "error")
            warnings = sum(1 for f in result.findings if f.severity == "warning")
            print(f"      - 错误：{errors}")
            print(f"      - 警告：{warnings}")

        print(f"\n📁 输出文件：")
        for name, path in result.output_files.items():
            print(f"   ✅ {name}: {path}")

    print("\n🎉 完成！")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
