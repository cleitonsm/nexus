"""E7: orquestrador `scripts/validation/run-all.sh` (ordem, selecao e pendencias)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "validation" / "run-all.sh"

if not SCRIPT.is_file() or shutil.which("bash") is None:
    raise unittest.SkipTest("run-all.sh ou bash indisponivel neste ambiente.")


def run(*args: str, report_dir: str | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ}
    if report_dir:
        env["NEXUS_REPORT_DIR"] = report_dir
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def stages(output: str) -> list[str]:
    return re.findall(r"^\[(V\d)\]", output, flags=re.MULTILINE)


class RunAllTestCase(unittest.TestCase):
    def test_dry_run_lists_every_stage_in_order(self) -> None:
        result = run("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        order = []
        for stage in stages(result.stdout):
            if not order or order[-1] != stage:
                order.append(stage)
        self.assertEqual(order, [f"V{n}" for n in range(9)])

    def test_dry_run_does_not_create_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "relatorios"
            run("--dry-run", report_dir=str(target))
            self.assertFalse(target.exists())

    def test_only_and_from_select_stages(self) -> None:
        only = stages(run("--dry-run", "--only", "V4").stdout)
        self.assertEqual(set(only), {"V4"})
        later = set(stages(run("--dry-run", "--from", "V7").stdout))
        self.assertEqual(later, {"V7", "V8"})

    def test_unknown_option_is_refused(self) -> None:
        self.assertEqual(run("--nope").returncode, 2)

    def test_manual_stage_is_pending_so_the_run_is_not_approved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run("--only", "V5", report_dir=tmp)
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
            self.assertIn("PENDENTE", (Path(tmp) / "resumo.md").read_text(encoding="utf-8"))

    def test_failed_step_stops_the_run_with_code_one(self) -> None:
        # V4 falha sem npm/rede no ambiente de teste ou passa se houver tudo;
        # para ser deterministico, forca um PATH sem npm.
        with tempfile.TemporaryDirectory() as tmp:
            env = {**os.environ, "NEXUS_REPORT_DIR": tmp, "PATH": "/usr/bin:/bin"}
            if shutil.which("npm", path="/usr/bin:/bin"):
                self.skipTest("npm presente em /usr/bin")
            result = subprocess.run(
                ["bash", str(SCRIPT), "--only", "V4"],
                cwd=ROOT, env=env, capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            summary = (Path(tmp) / "resumo.md").read_text(encoding="utf-8")
            self.assertIn("FALHA", summary)
            self.assertNotIn("npm test", summary)  # parou no primeiro item


if __name__ == "__main__":
    unittest.main()
