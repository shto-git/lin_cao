"""Chart engine for forestry planning visualizations.

Pure SVG fallback - no external dependencies required.
Optionally uses matplotlib if available.
"""

from __future__ import annotations

import math
import os
from typing import Any


def _get_matplotlib():
    """Try to import matplotlib, return None if unavailable."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        return plt
    except ImportError:
        return None


# ── Pure SVG Charts (no dependencies) ────────────────────

def svg_bar_chart(
    data: list[float],
    labels: list[str],
    title: str = "",
    width: int = 600,
    height: int = 400,
    color: str = "#4A90D9",
) -> str:
    """Generate a bar chart as SVG string."""
    if not data:
        return "<svg></svg>"

    margin_left, margin_right = 80, 40
    margin_top, margin_bottom = 60, 80
    chart_w = width - margin_left - margin_right
    chart_h = height - margin_top - margin_bottom

    max_val = max(data) if max(data) > 0 else 1
    bar_w = chart_w / len(data) * 0.7
    gap = chart_w / len(data) * 0.3

    bars = []
    for i, (val, label) in enumerate(zip(data, labels)):
        x = margin_left + i * (bar_w + gap) + gap / 2
        bar_h = (val / max_val) * chart_h
        y = margin_top + chart_h - bar_h
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" '
            f'fill="{color}" rx="3"/>'
        )
        bars.append(
            f'<text x="{x + bar_w/2:.1f}" y="{y - 8:.1f}" text-anchor="middle" '
            f'font-size="12" fill="#333">{val}</text>'
        )
        bars.append(
            f'<text x="{x + bar_w/2:.1f}" y="{height - margin_bottom + 20}" '
            f'text-anchor="middle" font-size="11" fill="#666">{label}</text>'
        )

    # Y-axis line
    axis_y = (
        f'<line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" '
        f'y2="{margin_top + chart_h}" stroke="#ccc" stroke-width="1"/>'
    )
    # X-axis line
    axis_x = (
        f'<line x1="{margin_left}" y1="{margin_top + chart_h}" '
        f'x2="{width - margin_right}" y2="{margin_top + chart_h}" '
        f'stroke="#ccc" stroke-width="1"/>'
    )

    title_svg = ""
    if title:
        title_svg = (
            f'<text x="{width/2}" y="30" text-anchor="middle" font-size="16" '
            f'font-weight="bold" fill="#333">{title}</text>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}">' 
        f'{title_svg}{axis_y}{axis_x}{"".join(bars)}</svg>'
    )


def svg_line_chart(
    data: list[float],
    labels: list[str],
    title: str = "",
    width: int = 600,
    height: int = 400,
    color: str = "#E74C3C",
) -> str:
    """Generate a line chart as SVG string."""
    if not data:
        return "<svg></svg>"

    margin_left, margin_right = 80, 40
    margin_top, margin_bottom = 60, 80
    chart_w = width - margin_left - margin_right
    chart_h = height - margin_top - margin_bottom

    max_val = max(data) if max(data) > 0 else 1
    min_val = min(data)
    val_range = max_val - min_val if max_val != min_val else 1

    points = []
    for i, val in enumerate(data):
        x = margin_left + (i / max(len(data) - 1, 1)) * chart_w
        y = margin_top + chart_h - ((val - min_val) / val_range) * chart_h
        points.append(f"{x:.1f},{y:.1f}")

    # Data points circles
    circles = []
    for i, val in enumerate(data):
        x = margin_left + (i / max(len(data) - 1, 1)) * chart_w
        y = margin_top + chart_h - ((val - min_val) / val_range) * chart_h
        circles.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}" stroke="white" stroke-width="2"/>'
        )
        circles.append(
            f'<text x="{x:.1f}" y="{y - 12:.1f}" text-anchor="middle" '
            f'font-size="11" fill="#333">{val}</text>'
        )

    # X-axis labels
    x_labels = []
    for i, label in enumerate(labels):
        x = margin_left + (i / max(len(data) - 1, 1)) * chart_w
        x_labels.append(
            f'<text x="{x:.1f}" y="{height - margin_bottom + 20}" '
            f'text-anchor="middle" font-size="11" fill="#666">{label}</text>'
        )

    polyline = '<polyline points="{" ".join(points)}" fill="none" stroke="' + color + '" stroke-width="2"/>'

    title_svg = ""
    if title:
        title_svg = (
            f'<text x="{width/2}" y="30" text-anchor="middle" font-size="16" '
            f'font-weight="bold" fill="#333">{title}</text>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}">' 
        f'{title_svg}{polyline}{"".join(circles)}{"".join(x_labels)}</svg>'
    )


def svg_pie_chart(
    data: list[float],
    labels: list[str],
    title: str = "",
    width: int = 500,
    height: int = 400,
    colors: list[str] | None = None,
) -> str:
    """Generate a pie chart as SVG string."""
    if not data:
        return "<svg></svg>"

    default_colors = ["#4A90D9", "#E74C3C", "#2ECC71", "#F39C12", "#9B59B6", "#1ABC9C", "#E67E22", "#3498DB"]
    if not colors:
        colors = [default_colors[i % len(default_colors)] for i in range(len(data))]

    total = sum(data)
    if total == 0:
        return "<svg></svg>"

    cx, cy = width // 2 - 50, height // 2
    r = min(width // 3, height // 3)

    slices = []
    start_angle = -90  # Start from top
    for i, (val, label, color) in enumerate(zip(data, labels, colors)):
        angle = (val / total) * 360
        end_angle = start_angle + angle

        # Calculate path
        x1 = cx + r * math.cos(math.radians(start_angle))
        y1 = cy + r * math.sin(math.radians(start_angle))
        x2 = cx + r * math.cos(math.radians(end_angle))
        y2 = cy + r * math.sin(math.radians(end_angle))

        large_arc = 1 if angle > 180 else 0

        path = f'M {cx} {cy} L {x1:.1f} {y1:.1f} A {r} {r} 0 {large_arc} 1 {x2:.1f} {y2:.1f} Z'
        slices.append(f'<path d="{path}" fill="{color}" stroke="white" stroke-width="2"/>')

        # Label position
        mid_angle = start_angle + angle / 2
        label_r = r * 0.7
        lx = cx + label_r * math.cos(math.radians(mid_angle))
        ly = cy + label_r * math.sin(math.radians(mid_angle))
        pct = (val / total) * 100
        slices.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" dominant-baseline="middle" '
            f'font-size="11" fill="white" font-weight="bold">{pct:.1f}%</text>'
        )

        start_angle = end_angle

    # Legend
    legend = []
    for i, (label, color) in enumerate(zip(labels, colors)):
        ly = 30 + i * 25
        legend.append(f'<rect x="{width - 100}" y="{ly}" width="14" height="14" fill="{color}" rx="2"/>')
        legend.append(
            f'<text x="{width - 80}" y="{ly + 11}" font-size="12" fill="#333">{label}</text>'
        )

    title_svg = ""
    if title:
        title_svg = (
            f'<text x="{width/2 - 25}" y="20" text-anchor="middle" font-size="16" '
            f'font-weight="bold" fill="#333">{title}</text>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}">' 
        f'{title_svg}{"".join(slices)}{"".join(legend)}</svg>'
    )


def svg_stacked_bar_chart(
    data: dict[str, list[float]],
    labels: list[str],
    title: str = "",
    width: int = 600,
    height: int = 400,
    colors: list[str] | None = None,
) -> str:
    """Generate a stacked bar chart as SVG string.

    data: {"category1": [v1, v2, ...], "category2": [v1, v2, ...], ...}
    labels: ["label1", "label2", ...]  (x-axis labels)
    """
    if not data or not labels:
        return "<svg></svg>"

    default_colors = ["#4A90D9", "#E74C3C", "#2ECC71", "#F39C12", "#9B59B6", "#1ABC9C"]
    categories = list(data.keys())
    if not colors:
        colors = [default_colors[i % len(default_colors)] for i in range(len(categories))]

    margin_left, margin_right = 80, 40
    margin_top, margin_bottom = 60, 100
    chart_w = width - margin_left - margin_right
    chart_h = height - margin_top - margin_bottom

    # Calculate max stack height
    max_total = 0
    for i in range(len(labels)):
        total = sum(data[cat][i] for cat in categories if i < len(data[cat]))
        max_total = max(max_total, total)
    if max_total == 0:
        max_total = 1

    bar_w = chart_w / len(labels) * 0.6
    gap = chart_w / len(labels) * 4

    bars = []
    for i, label in enumerate(labels):
        x = margin_left + i * (bar_w + gap) + gap / 2
        y_base = margin_top + chart_h

        for j, (cat, color) in enumerate(zip(categories, colors)):
            if i >= len(data[cat]):
                continue
            val = data[cat][i]
            bar_h = (val / max_total) * chart_h
            y = y_base - bar_h
            bars.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" '
                f'fill="{color}" rx="2"/>'
            )
            y_base = y

        bars.append(
            f'<text x="{x + bar_w/2:.1f}" y="{height - margin_bottom + 20}" '
            f'text-anchor="middle" font-size="11" fill="#666">{label}</text>'
        )

    # Legend
    legend = []
    for j, (cat, color) in enumerate(zip(categories, colors)):
        ly = 30 + j * 22
        legend.append(f'<rect x="{width - 120}" y="{ly}" width="12" height="12" fill="{color}" rx="2"/>')
        legend.append(
            f'<text x="{width - 104}" y="{ly + 10}" font-size="11" fill="#333">{cat}</text>'
        )

    title_svg = ""
    if title:
        title_svg = (
            f'<text x="{width/2}" y="25" text-anchor="middle" font-size="16" '
            f'font-weight="bold" fill="#333">{title}</text>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}">' 
        f'{title_svg}{"".join(bars)}{"".join(legend)}</svg>'
    )


# ── Public API (auto-select backend) ─────────────────────

def bar_chart(
    data: list[float],
    labels: list[str],
    title: str = "",
    save_path: str | None = None,
    **kwargs: Any,
) -> str:
    """Generate a bar chart. Returns SVG string."""
    plt = _get_matplotlib()
    if plt:
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.bar(labels, data, color=kwargs.get("color", "#4A90D9"))
        ax.set_title(title)
        ax.set_ylabel("数值")
        plt.tight_layout()
        if save_path:
            os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
            plt.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close()
        return f"<img src=\"{save_path}\" />"
    else:
        svg = svg_bar_chart(data, labels, title, **kwargs)
        if save_path:
            os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(svg)
        return svg


def line_chart(
    data: list[float],
    labels: list[str],
    title: str = "",
    save_path: str | None = None,
    **kwargs: Any,
) -> str:
    """Generate a line chart. Returns SVG string."""
    plt = _get_matplotlib()
    if plt:
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(labels, data, marker="o", color=kwargs.get("color", "#E74C3C"), linewidth=2)
        ax.set_title(title)
        ax.set_ylabel("数值")
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        if save_path:
            os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
            plt.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close()
        return f"<img src=\"{save_path}\" />"
    else:
        svg = svg_line_chart(data, labels, title, **kwargs)
        if save_path:
            os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(svg)
        return svg


def pie_chart(
    data: list[float],
    labels: list[str],
    title: str = "",
    save_path: str | None = None,
    **kwargs: Any,
) -> str:
    """Generate a pie chart. Returns SVG string."""
    plt = _get_matplotlib()
    if plt:
        fig, ax = plt.subplots(figsize=(7, 6))
        ax.pie(data, labels=labels, autopct="%1.1f%%", startangle=90)
        ax.set_title(title)
        plt.tight_layout()
        if save_path:
            os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
            plt.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close()
        return f"<img src=\"{save_path}\" />"
    else:
        svg = svg_pie_chart(data, labels, title, **kwargs)
        if save_path:
            os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(svg)
        return svg


def stacked_bar_chart(
    data: dict[str, list[float]],
    labels: list[str],
    title: str = "",
    save_path: str | None = None,
    **kwargs: Any,
) -> str:
    """Generate a stacked bar chart. Returns SVG string."""
    plt = _get_matplotlib()
    if plt:
        fig, ax = plt.subplots(figsize=(8, 5))
        bottom = [0] * len(labels)
        for i, (cat, values) in enumerate(data.items()):
            ax.bar(labels, values, bottom=bottom, label=cat)
            bottom = [b + v for b, v in zip(bottom, values)]
        ax.set_title(title)
        ax.legend()
        plt.tight_layout()
        if save_path:
            os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
            plt.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close()
        return f"<img src=\"{save_path}\" />"
    else:
        svg = svg_stacked_bar_chart(data, labels, title, **kwargs)
        if save_path:
            os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(svg)
        return svg
