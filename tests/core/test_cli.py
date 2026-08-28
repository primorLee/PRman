from __future__ import annotations

import contextlib
import hashlib
import io
import json
import subprocess
import sys
import unittest

from helpers import ROOT

from prman.cli import main


class CliTests(unittest.TestCase):
    def test_candidate_id_hashes_exact_diff_bytes(self) -> None:
        diff = ROOT / "examples" / "change.diff"
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = main(["candidate-id", "--diff", str(diff)])
        self.assertEqual(status, 0)
        self.assertEqual(output.getvalue().strip(), hashlib.sha256(diff.read_bytes()).hexdigest())

    def test_fixture_provider_requires_explicit_test_flag(self) -> None:
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            status = main(
                [
                    "assess",
                    "--input",
                    str(ROOT / "examples" / "assessment.json"),
                    "--decision-config",
                    str(ROOT / "configs" / "decision.json"),
                    "--scorer-config",
                    str(ROOT / "configs" / "scorer" / "fixture.example.json"),
                ]
            )
        self.assertEqual(status, 2)
        self.assertIn("test-only", errors.getvalue())

    def test_skill_wrapper_runs_complete_fixture_smoke(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "skills" / "prman" / "scripts" / "assess.py"),
                "--input",
                str(ROOT / "examples" / "assessment.json"),
                "--scorer-config",
                str(ROOT / "configs" / "scorer" / "fixture.example.json"),
                "--allow-test-scorer",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["selection"]["decision"], "ready")
        self.assertTrue(result["test_only"])
        self.assertFalse(result["policy"]["external_write_authorized"])


if __name__ == "__main__":
    unittest.main()
