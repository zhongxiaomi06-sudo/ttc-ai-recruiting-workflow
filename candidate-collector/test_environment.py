"""Tests for environment and configuration files."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class EnvironmentConfigTests(unittest.TestCase):
    def test_python_version_pinned_to_312(self) -> None:
        path = ROOT / ".python-version"
        self.assertTrue(path.is_file(), ".python-version should exist")
        content = path.read_text().strip()
        self.assertTrue(content.startswith("3.12"), f".python-version should pin 3.12, got {content}")

    def test_run_sh_uses_python312(self) -> None:
        path = ROOT / "run.sh"
        content = path.read_text()
        self.assertIn("python3.12", content, "run.sh should default to python3.12")
        self.assertIn("TTC_PYTHON", content, "run.sh should allow TTC_PYTHON override")

    def test_requirements_include_paddleocr(self) -> None:
        path = ROOT / "requirements.txt"
        content = path.read_text()
        self.assertIn("paddlepaddle", content)
        self.assertIn("paddleocr", content)
        self.assertIn("python_version", content, "paddlepaddle should have environment markers")


if __name__ == "__main__":
    unittest.main()
