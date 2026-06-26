"""Word document export using python-docx (optional dependency)."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def export_to_word(
    markdown_content: str,
    output_path: str | Path,
    title: str = "林草规划文档",
) -> str:
    """Export Markdown content to a Word (.docx) file.

    Requires: pip install python-docx
    """
    try:
        from docx import Document
        from docx.shared import Pt, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH
    except ImportError:
        raise ImportError(
            "Word 导出需要 python-docx。请运行: pip install python-docx"
        )

    doc = Document()

    # Set default font
    style = doc.styles["Normal"]
    font = style.font
    font.name = "宋体"
    font.size = Pt(12)

    # Title
    title_para = doc.add_heading(title, level=0)
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Parse markdown lines
    for line in markdown_content.split("\n"):
        line = line.rstrip()
        if not line:
            doc.add_paragraph("")
            continue

        # Headings
        if line.startswith("# "):
            doc.add_heading(line[2:], level=1)
        elif line.startswith("## "):
            doc.add_heading(line[3:], level=2)
        elif line.startswith("### "):
            doc.add_heading(line[4:], level=3)
        elif line.startswith("#### "):
            doc.add_heading(line[5:], level=4)
        # Bullet points
        elif line.startswith("- ") or line.startswith("* "):
            p = doc.add_paragraph(line[2:])
            p.style = doc.styles["List Bullet"]
        # Blockquote
        elif line.startswith("> "):
            p = doc.add_paragraph(line[2:])
            p.paragraph_format.left_indent = Inches(0.3)
        # Normal paragraph
        else:
            p = doc.add_paragraph(line)
            p.paragraph_format.first_line_indent = Pt(24)  # 首行缩进2字符

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    return str(output_path)
