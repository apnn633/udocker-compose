import importlib.machinery
import importlib.util
import io
import os
import subprocess
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "udocker-compose"


class CliTest(unittest.TestCase):
    def test_version_flag(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--version"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("udocker-compose", result.stdout)

    def test_no_color_respected(self):
        env = os.environ.copy()
        env["NO_COLOR"] = "1"
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--help"],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("\033[", result.stdout)


if __name__ == "__main__":
    unittest.main()
