# Isolated Debian 13 build

Run on Debian 13 amd64 with GCC 14, make, binutils, Python 3 and dpkg tools already available. This procedure extracts packages into a private workspace; it does not install them or touch `/usr/src`, `/lib/modules`, services or devices. Build concurrency is limited to two workers.

```sh
# From the repository root. Keep WORK outside the repository.
REPO=$PWD
WORK=$(mktemp -d "${TMPDIR:-/tmp}/xps7390-build.XXXXXX")
mkdir -p "$WORK/root" "$WORK/dkms" "$WORK/modules"
cd "$WORK"
python3 - <<'PY'
from pathlib import Path
from urllib.request import urlretrieve
import subprocess
names = [
    'linux-headers-6.12.113+deb13-amd64_6.12.113-1_amd64.deb',
    'linux-headers-6.12.113+deb13-common_6.12.113-1_all.deb',
    'linux-kbuild-6.12.113+deb13_6.12.113-1_amd64.deb',
]
for name in names:
    urlretrieve('https://deb.debian.org/debian/pool/main/l/linux/' + name, name)
    subprocess.run(['dpkg-deb', '-x', name, 'root'], check=True)
# Debian's generated wrapper contains an absolute source-header path.
# Relocate only the extracted copy, not an installed system header tree.
p = Path('root/usr/src/linux-headers-6.12.113+deb13-amd64/Makefile')
p.write_text('include ' + str(Path('root/usr/src/linux-headers-6.12.113+deb13-common/Makefile').resolve()) + '\n')
PY
# apt download reads the existing APT indexes; it does not install packages.
apt download pahole libbpf1 libdw1t64 dkms kmod
for deb in pahole_*.deb libbpf1_*.deb libdw1t64_*.deb dkms_*.deb kmod_*.deb; do
  dpkg-deb -x "$deb" root
done
export PATH="$WORK/root/usr/sbin:$WORK/root/usr/bin:$PATH"
export LD_LIBRARY_PATH="$WORK/root/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
KDIR="$WORK/root/usr/src/linux-headers-6.12.113+deb13-amd64"
cd "$REPO"
python3 -m unittest discover -s tests -v
make -j2 KDIR="$KDIR" all
python3 scripts/build-debs.py --output artifacts
```

Only the wrapper Makefile path is relocated. Config, generated headers, `Module.symvers`, Debian kbuild binaries and BTF data remain from version `6.12.113-1`. Do not substitute source excerpts or a different kernel's symbols. If the distribution mirror has aged out that version, retrieve the exact packages from Debian's archive and verify their provenance, rather than silently building against another release.

## Build through DKMS from the actual package

```sh
dpkg-deb -x artifacts/xps7390-webcam-dkms_0.1.0+debian1_amd64.deb "$WORK/package-root"
dkms add -m xps7390-webcam -v 0.1.0+debian1 \
  --dkmstree "$WORK/dkms" --sourcetree "$WORK/package-root/usr/src" \
  --installtree "$WORK/modules"
dkms build -m xps7390-webcam -v 0.1.0+debian1 -k 6.12.113+deb13-amd64 -j 2 \
  --kernelsourcedir "$KDIR" --dkmstree "$WORK/dkms" \
  --sourcetree "$WORK/package-root/usr/src" --installtree "$WORK/modules"
dkms status --dkmstree "$WORK/dkms" --sourcetree "$WORK/package-root/usr/src" \
  --installtree "$WORK/modules"
for module in "$WORK/dkms/xps7390-webcam/0.1.0+debian1/6.12.113+deb13-amd64/x86_64/module/"*.ko; do
  modinfo "$module"
done
```

Do not run `dkms install`, `modprobe`, the hardware setup helper or systemd activation as a build check. The isolated build has no installed kernel signing path, so DKMS reports that modules are not signed. That is expected; these are compile-test artifacts, not Secure Boot-ready modules.

## Verified results and limits

Actual execution produced `int346f.ko`, `ov01a10-i346f.ko`, `intel-ipu4p.ko` and `intel-ipu4p-isys.ko` through both make and DKMS. Modpost passed against the exact Debian symbol table. All four report vermagic `6.12.113+deb13-amd64 SMP preempt mod_unload modversions`. The IPU modules import `INTEL_IPU_BRIDGE` without literal quote characters.

The focused tests compile and execute the actual DMA sgtable wrapper with injected mapper results, exercise explicit sensor selection with intercepted device calls, check active ACPI instance 02 using a fixture tree, reject setup without opt-in, reject invalid local firmware, and build/unpack both packages to check their contents and lack of activation hooks. They do not exercise real DMA or hardware.

The userspace executable is compiled with warnings as errors, stack protection, FORTIFY, PIE and RELRO. Its missing-device failure path is executed. Neither successful capture nor the systemd runtime sandbox has been tested. Package installation/removal against a live dpkg database is also untested; archive contents and hooks are checked without installing them.
