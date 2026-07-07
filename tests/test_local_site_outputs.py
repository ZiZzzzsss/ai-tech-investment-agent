"""Tests for local-only site generation and privacy rules."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import run_dashboard
import run_report


class LocalSiteOutputTests(unittest.TestCase):
    def test_run_report_generates_local_company_memo_by_default_live_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                with patch("sys.argv", ["run_report.py", "--ticker", "NVDA", "--format", "html"]):
                    self.assertEqual(run_report.main(), 0)

                self.assertTrue(Path("local_site/company_memos/NVDA.html").exists())
                self.assertTrue(Path("local_site/index.html").exists())
                self.assertTrue(Path("local_site/assets/styles.css").exists())
                self.assertTrue(Path("local_site/assets/app.js").exists())
                self.assertFalse(Path("docs").exists())
            finally:
                os.chdir(original_cwd)

    def test_run_report_generates_local_company_memo(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                with patch("sys.argv", ["run_report.py", "--ticker", "NVDA", "--format", "html", "--mock"]):
                    self.assertEqual(run_report.main(), 0)

                self.assertTrue(Path("local_site/company_memos/NVDA.html").exists())
                self.assertTrue(Path("local_site/assets/styles.css").exists())
                self.assertTrue(Path("local_site/assets/app.js").exists())
            finally:
                os.chdir(original_cwd)

    def test_run_dashboard_generates_local_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                with patch("sys.argv", ["run_dashboard.py", "--live"]):
                    self.assertEqual(run_dashboard.main(), 0)

                index_path = Path("local_site/index.html")
                self.assertTrue(index_path.exists())
                html = index_path.read_text(encoding="utf-8")
                self.assertIn("company_memos/NVDA.html", html)
                self.assertIn("company_memos/AMD.html", html)
                self.assertIn("company_memos/ASML.html", html)
            finally:
                os.chdir(original_cwd)

    def test_private_output_paths_are_gitignored(self) -> None:
        gitignore = Path(__file__).resolve().parents[1] / ".gitignore"
        content = gitignore.read_text(encoding="utf-8")

        self.assertIn(".env", content)
        self.assertIn("local_site/", content)
        self.assertIn("outputs/", content)
        self.assertIn("reports/", content)
        self.assertIn("*.html", content)
        self.assertIn("**pycache**/", content)


if __name__ == "__main__":
    unittest.main()
