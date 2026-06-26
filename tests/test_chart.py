"""Tests for chart engine."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lin_cao_planner.chart_engine import (
    svg_bar_chart,
    svg_line_chart,
    svg_pie_chart,
    svg_stacked_bar_chart,
    bar_chart,
    line_chart,
    pie_chart,
    stacked_bar_chart,
)


class SVGChartTest(unittest.TestCase):
    """Test SVG fallback chart generation."""

    def test_bar_chart_returns_svg(self):
        svg = svg_bar_chart([100, 200, 150], ["A", "B", "C"], "柱状图")
        self.assertTrue(svg.startswith("<svg"))
        self.assertTrue(svg.endswith("</svg>"))
        self.assertIn("柱状图", svg)
        self.assertIn("A", svg)
        self.assertIn("100", svg)

    def test_line_chart_returns_svg(self):
        svg = svg_line_chart([10, 20, 15, 25], ["Q1", "Q2", "Q3", "Q4"], "折线图")
        self.assertTrue(svg.startswith("<svg"))
        self.assertTrue(svg.endswith("</svg>"))
        self.assertIn("折线图", svg)

    def test_pie_chart_returns_svg(self):
        svg = svg_pie_chart([30, 20, 50], ["类别A", "类别B", "类别C"], "饼图")
        self.assertTrue(svg.startswith("<svg"))
        self.assertTrue(svg.endswith("</svg>"))
        self.assertIn("饼图", svg)
        self.assertIn("类别A", svg)

    def test_stacked_bar_chart_returns_svg(self):
        data = {
            "森林": [100, 120, 140],
            "草原": [80, 90, 100],
            "湿地": [30, 35, 40],
        }
        svg = svg_stacked_bar_chart(data, ["2023", "2024", "2025"], "堆叠图")
        self.assertTrue(svg.startswith("<svg"))
        self.assertTrue(svg.endswith("</svg>"))
        self.assertIn("堆叠图", svg)

    def test_empty_data(self):
        self.assertEqual(svg_bar_chart([], []), "<svg></svg>")
        self.assertEqual(svg_line_chart([], []), "<svg></svg>")
        self.assertEqual(svg_pie_chart([], []), "<svg></svg>")

    def test_bar_chart_save_to_file(self):
        tmp_path = os.path.join(os.path.dirname(__file__), "_test_chart.svg")
        result = bar_chart([1, 2, 3], ["A", "B", "C"], title="测试", save_path=tmp_path)
        if os.path.exists(tmp_path):
            with open(tmp_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("<svg", content)
            os.remove(tmp_path)

    def test_public_api_returns_string(self):
        """All public API functions should return a string."""
        result = bar_chart([1, 2], ["a", "b"])
        self.assertIsInstance(result, str)
        result = line_chart([1, 2], ["a", "b"])
        self.assertIsInstance(result, str)
        result = pie_chart([1, 2], ["a", "b"])
        self.assertIsInstance(result, str)
        result = stacked_bar_chart({"x": [1, 2]}, ["a", "b"])
        self.assertIsInstance(result, str)


if __name__ == "__main__":
    unittest.main()
