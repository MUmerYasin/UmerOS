"""H9 — CI gate infrastructure validation.

Validates that the canonical CI / linting / type-checking configs are
present and well-formed per the code-review standards:

- pyproject.toml : Ruff + Mypy + pytest + coverage sections
- .pre-commit-config.yaml : Ruff + gitleaks + general hooks
- .github/workflows/ci.yml : test + secret-scan + pre-commit jobs
- requirements.txt : ruff, mypy, bandit, pre-commit, safety
- setup.py dev extras : ruff, mypy, bandit, pre-commit, safety

Rules checked: H9 (RED blocker) — Section 7 of Code Review Standards.
"""

from __future__ import annotations

import os
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestPyprojectToml(unittest.TestCase):
    """Validate pyproject.toml has required tool sections."""

    PATH = ROOT / "pyproject.toml"

    def test_file_exists(self) -> None:
        self.assertTrue(self.PATH.exists(), f"{self.PATH} must exist")

    def test_has_ruff_section(self) -> None:
        content = self.PATH.read_text(encoding="utf-8")
        self.assertIn("[tool.ruff]", content)
        self.assertIn("[tool.ruff.lint]", content)

    def test_ruff_select_includes_security_rules(self) -> None:
        content = self.PATH.read_text(encoding="utf-8")
        self.assertIn('"S"', content, "Ruff should include S (flake8-bandit)")

    def test_has_mypy_section(self) -> None:
        content = self.PATH.read_text(encoding="utf-8")
        self.assertIn("[tool.mypy]", content)

    def test_has_pytest_section(self) -> None:
        content = self.PATH.read_text(encoding="utf-8")
        self.assertIn("[tool.pytest.ini_options]", content)

    def test_has_coverage_section(self) -> None:
        content = self.PATH.read_text(encoding="utf-8")
        self.assertIn("[tool.coverage.run]", content)
        self.assertIn("[tool.coverage.report]", content)

    def test_coverage_fail_under(self) -> None:
        content = self.PATH.read_text(encoding="utf-8")
        match = re.search(r"fail_under\s*=\s*(\d+)", content)
        self.assertIsNotNone(match, "coverage fail_under must be set")
        self.assertGreaterEqual(int(match.group(1)), 1)


class TestPreCommitConfig(unittest.TestCase):
    """Validate .pre-commit-config.yaml has required hooks."""

    PATH = ROOT / ".pre-commit-config.yaml"

    def test_file_exists(self) -> None:
        self.assertTrue(self.PATH.exists(), f"{self.PATH} must exist")

    def test_has_ruff_hooks(self) -> None:
        content = self.PATH.read_text(encoding="utf-8")
        self.assertIn("ruff-pre-commit", content)
        self.assertIn('id: ruff', content)

    def test_has_gitleaks_hook(self) -> None:
        content = self.PATH.read_text(encoding="utf-8")
        self.assertIn("gitleaks", content)

    def test_has_general_hooks(self) -> None:
        content = self.PATH.read_text(encoding="utf-8")
        self.assertIn("trailing-whitespace", content)
        self.assertIn("end-of-file-fixer", content)
        self.assertIn("check-yaml", content)
        self.assertIn("detect-private-key", content)


class TestGitHubCI(unittest.TestCase):
    """Validate .github/workflows/ci.yml has required jobs."""

    PATH = ROOT / ".github" / "workflows" / "ci.yml"

    def test_file_exists(self) -> None:
        self.assertTrue(self.PATH.exists(), f"{self.PATH} must exist")

    def test_has_test_job(self) -> None:
        content = self.PATH.read_text(encoding="utf-8")
        self.assertIn("test:", content)

    def test_has_secret_scan_job(self) -> None:
        content = self.PATH.read_text(encoding="utf-8")
        self.assertIn("secret-scan:", content)

    def test_has_pre_commit_job(self) -> None:
        content = self.PATH.read_text(encoding="utf-8")
        self.assertIn("pre-commit:", content)

    def test_has_coverage_gate(self) -> None:
        content = self.PATH.read_text(encoding="utf-8")
        self.assertIn("--cov-fail-under", content)

    def test_has_ruff_lint_step(self) -> None:
        content = self.PATH.read_text(encoding="utf-8")
        self.assertIn("ruff check", content)

    def test_triggers_on_push_pr(self) -> None:
        content = self.PATH.read_text(encoding="utf-8")
        self.assertIn("push:", content)
        self.assertIn("pull_request:", content)


class TestRequirementsDevDeps(unittest.TestCase):
    """Validate requirements.txt has new dev deps, not old ones."""

    PATH = ROOT / "requirements.txt"

    def test_file_exists(self) -> None:
        self.assertTrue(self.PATH.exists(), f"{self.PATH} must exist")

    def test_has_ruff(self) -> None:
        content = self.PATH.read_text(encoding="utf-8")
        self.assertIn("ruff", content)

    def test_has_mypy(self) -> None:
        content = self.PATH.read_text(encoding="utf-8")
        self.assertIn("mypy", content)

    def test_has_bandit(self) -> None:
        content = self.PATH.read_text(encoding="utf-8")
        self.assertIn("bandit", content)

    def test_has_pre_commit(self) -> None:
        content = self.PATH.read_text(encoding="utf-8")
        self.assertIn("pre-commit", content)

    def test_has_safety(self) -> None:
        content = self.PATH.read_text(encoding="utf-8")
        self.assertIn("safety", content)

    def test_no_black(self) -> None:
        content = self.PATH.read_text(encoding="utf-8")
        for line in content.splitlines():
            if line.strip().startswith("#"):
                continue
            self.assertNotIn("black", line, "black should be removed")

    def test_no_flake8(self) -> None:
        content = self.PATH.read_text(encoding="utf-8")
        for line in content.splitlines():
            if line.strip().startswith("#"):
                continue
            self.assertNotIn("flake8", line, "flake8 should be removed")

    def test_no_pylint(self) -> None:
        content = self.PATH.read_text(encoding="utf-8")
        for line in content.splitlines():
            if line.strip().startswith("#"):
                continue
            self.assertNotIn("pylint", line, "pylint should be removed")


class TestSetupPyDevDeps(unittest.TestCase):
    """Validate setup.py dev+all extras reference new toolchain."""

    PATH = ROOT / "setup.py"

    def test_file_exists(self) -> None:
        self.assertTrue(self.PATH.exists(), f"{self.PATH} must exist")

    def test_has_ruff_in_extras(self) -> None:
        content = self.PATH.read_text(encoding="utf-8")
        self.assertIn("ruff", content)

    def test_has_mypy_in_extras(self) -> None:
        content = self.PATH.read_text(encoding="utf-8")
        self.assertIn("mypy", content)

    def test_no_black_in_extras(self) -> None:
        content = self.PATH.read_text(encoding="utf-8")
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "black" in stripped and ("==" in stripped or "install_requires" in stripped or "ruff" in stripped):
                self.fail(f"black should be removed from setup.py: {stripped}")


class TestH9LintGate(unittest.TestCase):
    """Verify H9 passes basic lint sanity (no critical import errors)."""

    def test_pyproject_toml_parseable(self) -> None:
        """pyproject.toml must be parseable TOML."""
        try:
            import tomllib  # Python 3.11+
        except ImportError:
            import tomli as tomllib  # type: ignore[no-redef]

        path = ROOT / "pyproject.toml"
        with open(path, "rb") as f:
            data = tomllib.load(f)
        self.assertIn("tool", data)
        self.assertIn("ruff", data["tool"])
        self.assertIn("mypy", data["tool"])

    def test_precommit_yaml_parseable(self) -> None:
        """pre-commit config must be parseable YAML."""
        import yaml  # type: ignore[import-untyped]

        path = ROOT / ".pre-commit-config.yaml"
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self.assertIn("repos", data)
        self.assertIsInstance(data["repos"], list)
        self.assertGreater(len(data["repos"]), 0)

    def test_ci_yml_parseable(self) -> None:
        """CI workflow must be parseable YAML."""
        import yaml  # type: ignore[import-untyped]

        path = ROOT / ".github" / "workflows" / "ci.yml"
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self.assertIn("jobs", data)
        self.assertIn("test", data["jobs"])
        self.assertIn("secret-scan", data["jobs"])
        self.assertIn("pre-commit", data["jobs"])


if __name__ == "__main__":
    unittest.main()
