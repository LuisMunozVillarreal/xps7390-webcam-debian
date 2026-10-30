#!/usr/bin/env python3
"""Build and unpack the actual packages without installing anything."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.0+debian1"


class PackageTest(unittest.TestCase):
    def test_packages_are_inert_and_complete(self):
        builder = ROOT / "scripts/build-debs.py"
        self.assertTrue(builder.is_file(), "Debian package builder is missing")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            subprocess.run(["python3", str(builder), "--output", str(out)], check=True)
            packages = sorted(out.glob("*.deb"))
            self.assertEqual(len(packages), 2)
            for deb in packages:
                package = subprocess.check_output(["dpkg-deb", "-f", str(deb), "Package"], text=True).strip()
                dest = out / package
                subprocess.run(["dpkg-deb", "-R", str(deb), str(dest)], check=True)
                self.assertFalse(list(dest.rglob("*.ko")))
                self.assertFalse(list(dest.rglob("*.bin")))
                self.assertFalse(list(dest.rglob("*.CAB")))
                self.assertFalse((dest / "etc/modules-load.d").exists())
                for name in ("postinst", "preinst", "prerm", "postrm"):
                    hook = dest / "DEBIAN" / name
                    if hook.exists():
                        text = hook.read_text()
                        for forbidden in ("modprobe", "insmod", "systemctl", "invoke-rc.d", "deb-systemd-invoke"):
                            self.assertNotIn(forbidden, text)
                if package.endswith("-dkms"):
                    src = dest / f"usr/src/xps7390-webcam-{VERSION}"
                    self.assertTrue((src / "driver/int346f/int3472.h").is_file())
                    self.assertTrue((src / "driver/ipu4p/ipu4p.c").is_file())
                    self.assertIn('AUTOINSTALL="no"', (src / "dkms.conf").read_text())
                    conf = (dest / "etc/modprobe.d/xps7390-webcam-experimental.conf").read_text()
                    for module in ("int346f", "ov01a10-i346f", "intel-ipu4p", "intel-ipu4p-isys"):
                        self.assertIn("blacklist " + module + "\n", conf)
                    self.assertNotIn("blacklist ov01a10\n", conf)
                else:
                    unit = (dest / "usr/lib/systemd/system/xps7390-webcam.service").read_text()
                    self.assertNotIn("[Install]", unit)
                    self.assertIn("ConditionPathExists=/etc/xps7390-webcam/enable-experimental", unit)
                    self.assertIn("DynamicUser=yes", unit)
                    self.assertIn("Restart=no", unit)
                    self.assertFalse((dest / "etc/xps7390-webcam/enable-experimental").exists())
                    binary = dest / "usr/bin/ipu4-softisp"
                    self.assertTrue(os.access(binary, os.X_OK))
                    result = subprocess.run([str(binary), "/nonexistent-xps-raw", "/nonexistent-xps-output"], capture_output=True)
                    self.assertEqual(result.returncode, 1)
                    self.assertIn(b"/nonexistent-xps-raw", result.stderr)


if __name__ == "__main__":
    unittest.main()
