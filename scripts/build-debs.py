#!/usr/bin/env python3
"""Build two binary Debian packages without root, installs or network access."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.0+debian1"


def copy(source, stage, target, mode=0o644):
    dest = stage / target
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / source, dest)
    dest.chmod(mode)


def build(output):
    arch = subprocess.check_output(["dpkg", "--print-architecture"], text=True).strip()
    if arch != "amd64":
        raise SystemExit("Only native Debian amd64 builds are supported")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="xps7390-debs-") as tmp:
        work = Path(tmp)
        binary = work / "ipu4-softisp"
        subprocess.run(["cc", "-O2", "-Wall", "-Wextra", "-Werror", "-fstack-protector-strong",
                        "-D_FORTIFY_SOURCE=2", "-fPIE", "-pie", "-Wl,-z,relro,-z,now",
                        str(ROOT / "softisp/ipu4-softisp.c"), "-lm", "-o", str(binary)], check=True)
        subprocess.run(["strip", "--strip-unneeded", str(binary)], check=True)
        for kind in ("dkms", "userspace"):
            package = "xps7390-webcam-" + kind
            stage = work / package
            (stage / "DEBIAN").mkdir(parents=True)
            depends = ("dkms (>= 3.0), gcc-14, make, linux-headers-6.12.113+deb13-amd64, pahole"
                       if kind == "dkms" else
                       f"xps7390-webcam-dkms (= {VERSION}), libc6 (>= 2.38), bash, python3, v4l-utils, kmod, pciutils, v4l2loopback-dkms")
            (stage / "DEBIAN/control").write_text(
                f"Package: {package}\nVersion: {VERSION}\nArchitecture: {arch}\n"
                "Maintainer: XPS7390 Webcam Contributors <noreply@users.noreply.github.com>\n"
                f"Depends: {depends}\nSection: video\nPriority: optional\n"
                f"Description: Experimental XPS 13 7390 2-in-1 camera {kind}\n"
                " Local build for Debian 13 Linux 6.12.113+deb13-amd64.\n"
                " Hardware capture is unverified; installation never starts the camera.\n")
            docs = f"usr/share/doc/{package}"
            for source, name in [("packaging/copyright", "copyright"),
                                 ("LICENSES/GPL-2.0", "GPL-2.0"),
                                 ("README.md", "README.md"),
                                 ("docs/provenance.md", "docs/provenance.md"),
                                 ("docs/architecture.md", "docs/architecture.md"),
                                 ("docs/debian-build.md", "docs/debian-build.md")]:
                copy(source, stage, docs + "/" + name)
            if kind == "dkms":
                src = f"usr/src/xps7390-webcam-{VERSION}"
                for source in ("Makefile", "dkms.conf", "COPYING", "LICENSES/GPL-2.0"):
                    copy(source, stage, src + "/" + source)
                for source in sorted((ROOT / "driver").rglob("*")):
                    if source.is_file() and (source.suffix in (".c", ".h") or source.name == "Makefile"):
                        if source.name.endswith(".mod.c"):
                            continue
                        rel = source.relative_to(ROOT).as_posix()
                        copy(rel, stage, src + "/" + rel)
                for hook in ("postinst", "prerm"):
                    copy("packaging/dkms." + hook, stage, "DEBIAN/" + hook, 0o755)
                conf = "etc/modprobe.d/xps7390-webcam-experimental.conf"
                copy("packaging/xps7390-webcam-experimental.conf", stage, conf)
                (stage / "DEBIAN/conffiles").write_text("/" + conf + "\n")
            else:
                (stage / "usr/bin").mkdir(parents=True)
                shutil.copyfile(binary, stage / "usr/bin/ipu4-softisp")
                (stage / "usr/bin/ipu4-softisp").chmod(0o755)
                copy("packaging/xps7390-webcam.service", stage,
                     "usr/lib/systemd/system/xps7390-webcam.service")
                for name in ("check-hardware.sh", "setup-camera.sh", "extract-firmware.sh"):
                    copy("scripts/" + name, stage, "usr/libexec/xps7390-webcam/" + name, 0o755)
            subprocess.run(["dpkg-deb", "--root-owner-group", "--threads-max=2", "--build",
                            str(stage), str(output / f"{package}_{VERSION}_{arch}.deb")], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts")
    build(parser.parse_args().output.resolve())
