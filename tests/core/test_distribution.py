from __future__ import annotations

import json
import tomllib
import unittest

from helpers import ROOT


class DistributionTests(unittest.TestCase):
    def test_plugin_manifest_names_skill_directory(self) -> None:
        manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "prman")
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertTrue((ROOT / "skills" / "prman" / "SKILL.md").is_file())

    def test_python_distribution_excludes_the_legacy_harness(self) -> None:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(project["tool"]["setuptools"]["packages"], ["prman", "prman.scorers"])
        manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(project["project"]["version"], manifest["version"])

    def test_skill_has_no_scaffold_placeholders(self) -> None:
        skill = (ROOT / "skills" / "prman" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("name: prman", skill)
        self.assertNotIn("[TODO:", skill)

    def test_public_json_contracts_parse(self) -> None:
        paths = [
            ROOT / "configs" / "decision.json",
            *(ROOT / "schemas").glob("*.schema.json"),
        ]
        for path in paths:
            with self.subTest(path=path.name):
                self.assertIsInstance(json.loads(path.read_text(encoding="utf-8")), dict)

    def test_github_roadmap_is_valid_jsonl_with_resolved_dependencies(self) -> None:
        issues = [
            json.loads(line)
            for line in (ROOT / "github_issues.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        identifiers = [issue["external_id"] for issue in issues]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        known = set(identifiers)
        for issue in issues:
            self.assertLessEqual(set(issue["depends_on"]), known)


if __name__ == "__main__":
    unittest.main()
