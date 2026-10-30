# xps7390-webcam-debian

Experimental Debian 13 adaptation of [Maxime Rivest's XPS 13 7390 2-in-1 camera driver](https://github.com/MaximeRivest/xps-13-7390-2-in-1-webcam-linux), based on commit `336a8a369a9d83f6d9805e2541c56bc7fa4d076a`.

**All four modules compile against Debian's exact `6.12.113+deb13-amd64` headers. Hardware capture on Debian has not been tested.** A successful build does not establish safe DMA, firmware authentication, privacy LED operation, suspend/resume, or usable video.

The target is the Dell XPS 13 7390 **2-in-1**, Intel `8086:8a19`, sensor `OVTI01A0:00`, active power controller `INT346F:02`. Other XPS models and kernels are not supported by this branch. Upstream reports RAW10 1280x800 capture and 640x400 YUYV software-ISP output on NixOS/Linux 6.18. Those capture results have not been reproduced here.

## Build without installation

On a Debian 13 amd64 build machine with GCC 14, make, binutils, Python 3, dpkg-dev, pahole and the exact headers available:

```sh
python3 -m unittest discover -s tests -v
make -j2 KDIR=/path/to/linux-headers-6.12.113+deb13-amd64 all
python3 scripts/build-debs.py --output artifacts
```

The packager builds the userspace executable and creates two real binary packages. It does not download anything, require root, install packages or load modules:

- `xps7390-webcam-dkms_0.1.0+debian1_amd64.deb` contains the four-module DKMS source tree.
- `xps7390-webcam-userspace_0.1.0+debian1_amd64.deb` contains the software ISP, manual setup tools and a hardened systemd unit.

Module compilation is a separate explicit build gate; building the packages alone does not prove kernel compatibility. See [isolated build instructions](docs/debian-build.md) for extracted headers and a rootless DKMS build from the actual package. No proprietary firmware is needed to compile.

## Installation is not activation

Do not run the inherited `install.sh`, `uninstall.sh`, Nix flake or old `systemd/` units on Debian. They describe the upstream deployment, not these packages. The Debian unit is maintained under `packaging/`; only it is packaged. The inherited Nix CI workflow was removed from this branch because it does not verify this Debian build.

After separately approving changes to the laptop, package installation would be:

```sh
sudo apt install ./artifacts/xps7390-webcam-dkms_0.1.0+debian1_amd64.deb \
  ./artifacts/xps7390-webcam-userspace_0.1.0+debian1_amd64.deb
```

The DKMS post-install hook **only registers source**. `AUTOINSTALL=no` prevents automatic builds on kernel updates. Both compilation and installation of modules require explicit `dkms` commands. A modprobe blacklist suppresses modalias autoload for the experimental modules; it does not blacklist the in-tree `ov01a10`. The userspace package has no maintainer scripts, boot enablement or automatic service start. No firmware is included. Installing dependencies such as `v4l2loopback-dkms` can build those dependencies according to Debian's policies.

This conservative first version supports only `6.12.113+deb13-amd64`. A later kernel needs a new compatibility build and updated DKMS restriction. Do not silently override that guard.

## Firmware stays local

Obtain `7390 2in1-win11-A00-4PY3P.CAB` from [Dell](https://www.dell.com/support/home/product-support/product/xps-13-7390-2-in-1-laptop/drivers) under its applicable terms. With `cabextract` available, extract into a private directory outside this repository:

```sh
bash scripts/extract-firmware.sh /path/to/7390\ 2in1-win11-A00-4PY3P.CAB "$HOME/xps7390-firmware"
```

The installed equivalent is `/usr/libexec/xps7390-webcam/extract-firmware.sh`. Both require a local CAB and an explicit output directory, check the known SHA-256, and make no network requests. Do not commit the CAB or resulting `intel/ipu/ipu4p_cpd.bin`. No real firmware was downloaded or extracted during the build verification.

## Later, explicitly approved hardware test

These commands change the laptop and **were not executed as part of the build**. Back up work first. Have a recovery boot option and arrange a test window. Keep IOMMU protection enabled. Check Secure Boot before loading modules; all four project modules and v4l2loopback need trusted signatures when enforcement is enabled. The rootless build artifacts are unsigned and do not establish Secure Boot readiness. Use Debian's DKMS signing/MOK procedure rather than disabling Secure Boot by default.

After package installation and signature preparation:

```sh
sudo dkms build -m xps7390-webcam -v 0.1.0+debian1 -k 6.12.113+deb13-amd64 -j 2
sudo dkms install -m xps7390-webcam -v 0.1.0+debian1 -k 6.12.113+deb13-amd64
sudo install -D -m644 "$HOME/xps7390-firmware/intel/ipu/ipu4p_cpd.bin" \
  /lib/firmware/intel/ipu/ipu4p_cpd.bin
sudo install -d -m755 /etc/xps7390-webcam
sudo touch /etc/xps7390-webcam/enable-experimental
sudo /usr/libexec/xps7390-webcam/setup-camera.sh --enable-hardware-test
sudo systemctl daemon-reload
sudo systemctl start xps7390-webcam.service
```

The setup script checks the exact kernel/hardware and refuses a loaded in-tree `ov01a10` or conflicting loopback configuration. Resolve conflicts manually; it does not unload existing drivers or change their blacklist. It discovers the sensor's I2C entity in the IPU4P graph rather than assuming bus 3. Receiver 1 and Capture 8 remain hardware-specific assumptions and must be checked during the first test. Only that sensor receives exposure/gain controls.

**Starting the service starts continuous physical capture**, even when no browser is using it. It does not wait for an application. There is no automatic restart. The service uses a dynamic unprivileged user in the `video` group, with no capabilities or permission to load modules. Device permissions and sandbox compatibility remain hardware-test items. Applications should select `XPS7390 Camera`, `/dev/video57`, with 640x400 YUYV output.

Stop capture explicitly:

```sh
sudo systemctl stop xps7390-webcam.service
sudo rm -f /etc/xps7390-webcam/enable-experimental
```

Removing the opt-in file alone does not stop a running service. Stop it before removal, package upgrades or DKMS removal. Stopping capture does not unload modules. To return to a non-experimental boot, stop the service, remove the opt-in file, remove the packages and reboot; decide separately whether to retain locally supplied firmware. Do not use the upstream uninstaller for Debian packages.

Acceptance requires repeated stream start/stop, browser use, correct privacy LED behavior, suspend/resume, review of kernel/DMA faults, and acceptable CPU/power usage. None of those runtime checks has passed yet.

## Changes and licensing

This branch vendors the GPL-2.0 Linux v6.18 INT3472 header privately inside the INT346F module, retaining its regulator arrays and quirks rather than reinterpreting Debian 6.12's different private structure. It adapts namespace macros and `v4l2_get_link_freq` to 6.12, and fixes zero-result DMA mapping being treated as success. Original DMA overshoot allocation is unchanged.

Original copyright notices, SPDX identifiers, GPL license and git history are preserved. See [source provenance](docs/provenance.md) and [upstream architecture](docs/architecture.md). These packages are an experimental downstream adaptation, not an official Debian or upstream release.
