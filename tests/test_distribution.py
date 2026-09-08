import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DistributionTest(unittest.TestCase):
    def test_package_checks_pass_for_shippable_skill(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/check_package.py")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_standalone_install_is_self_contained_and_non_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "skills"
            command = [sys.executable, str(ROOT / "scripts/install_skill.py"), "--dest", str(target)]
            dry_run = subprocess.run(command + ["--dry-run"], capture_output=True, text=True)
            self.assertEqual(dry_run.returncode, 0, dry_run.stderr)
            self.assertFalse(target.exists())
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            entry = target / "distill-work/scripts/workskill.py"
            version = subprocess.run([sys.executable, str(entry), "--version"], capture_output=True, text=True)
            self.assertEqual(version.returncode, 0, version.stderr)
            self.assertEqual(version.stdout.strip(), "0.1.0")
            entry.write_text("user modification\n")
            again = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(again.returncode, 0)
            self.assertEqual(entry.read_text(), "user modification\n")

    def test_synthetic_demo_completes_learning_and_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "demo"
            result = subprocess.run([sys.executable, str(ROOT / "scripts/demo.py"), "--output", str(output)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual(data["accepted"], 1)
            self.assertEqual(data["rejected"], 1)
            self.assertTrue(Path(data["report"]).is_file())


if __name__ == "__main__":
    unittest.main()
