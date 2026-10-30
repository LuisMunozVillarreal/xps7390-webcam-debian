import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class HardwareCheckTest(unittest.TestCase):
    def test_active_int346f_instance_two_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, value in {"class/dmi/id/product_name": "XPS 13 7390 2-in-1",
                                "class/dmi/id/sys_vendor": "Dell Inc.",
                                "bus/acpi/devices/OVTI01A0:00/status": "15",
                                "bus/acpi/devices/INT346F:02/status": "15"}.items():
                p = root / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(value + "\n")
            tools = root / "bin"
            tools.mkdir()
            lspci = tools / "lspci"
            lspci.write_text("#!/bin/sh\nprintf '00:05.0 0480: 8086:8a19\\n'\n")
            lspci.chmod(0o755)
            env = dict(os.environ, XPS_SYSFS_ROOT=str(root), PATH=str(tools) + ":" + os.environ["PATH"])
            command = ["bash", str(ROOT / "scripts/check-hardware.sh")]
            result = subprocess.run(command, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            (root / "bus/acpi/devices/INT346F:02/status").write_text("0\n")
            self.assertNotEqual(subprocess.run(command, env=env, capture_output=True).returncode, 0)


if __name__ == "__main__":
    unittest.main()
