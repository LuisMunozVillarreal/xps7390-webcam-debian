import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class OptInTest(unittest.TestCase):
    def test_setup_without_opt_in_does_not_load_modules(self):
        with tempfile.TemporaryDirectory() as tmp:
            tools = Path(tmp)
            probe = tools / "modprobe"
            probe.write_text('#!/bin/sh\nprintf "called\\n" >> "$PROBE_LOG"\nexit 99\n')
            probe.chmod(0o755)
            log = tools / "calls"
            env = dict(os.environ, PROBE_LOG=str(log), PATH=str(tools) + ":" + os.environ["PATH"])
            result = subprocess.run(["bash", str(ROOT / "scripts/setup-camera.sh")], env=env, capture_output=True)
            self.assertFalse(log.exists(), "Module loading was attempted without explicit opt-in")
            self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
