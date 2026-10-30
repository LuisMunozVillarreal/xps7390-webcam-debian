import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FirmwareExtractionTest(unittest.TestCase):
    def test_local_extraction_rejects_wrong_hash_without_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            tools = base / "bin"
            tools.mkdir()
            extractor = tools / "cabextract"
            # Deliberately invalid test fixture. No firmware is downloaded or shipped.
            extractor.write_text('#!/bin/sh\nprintf "invalid test firmware" > "$3/cpd_component_signed.bin"\n')
            extractor.chmod(0o755)
            cab = base / "local-test.cab"
            cab.touch()
            output = base / "extracted"
            env = dict(os.environ, PATH=str(tools) + ":" + os.environ["PATH"])
            result = subprocess.run(["bash", str(ROOT / "scripts/extract-firmware.sh"),
                                     str(cab), str(output)], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("untested SHA-256", result.stderr)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
