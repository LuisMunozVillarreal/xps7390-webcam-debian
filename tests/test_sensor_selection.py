import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SensorSelectionTest(unittest.TestCase):
    def test_sensor_is_explicit_not_scanned(self):
        program = r'''
#define main softisp_main
#define open test_open
#define ioctl test_ioctl
#include "ipu4-softisp.c"
#undef main
#undef open
#undef ioctl
#include <assert.h>
static int opens;
static const char *paths[40];
int test_open(const char *path, int flags, ...) {
    (void)flags;
    paths[opens++] = path;
    return 100 + opens;
}
int test_ioctl(int fd, unsigned long request, ...) {
    (void)fd; (void)request;
    errno = ENOTTY;
    return -1;
}
int main(void) {
    char *argv[] = {"softisp", "/explicit-input", "/explicit-output", "/explicit-sensor", NULL};
    assert(softisp_main(4, argv) == 1);
    assert(opens == 3);
    assert(strcmp(paths[2], "/explicit-sensor") == 0);
    opens = 0;
    assert(softisp_main(3, argv) == 1);
    assert(opens == 2);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "sensor-test.c"
            exe = Path(tmp) / "sensor-test"
            src.write_text(program)
            subprocess.run([os.environ.get("CC", "cc"), "-Wall", "-Wextra", "-Werror",
                            "-I", str(ROOT / "softisp"), str(src), "-lm", "-o", str(exe)], check=True)
            result = subprocess.run([str(exe)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
