# Source provenance and licensing

## Debian adaptation

This downstream work preserves the history and attribution of Maxime Rivest's
[xps-13-7390-2-in-1-webcam-linux](https://github.com/MaximeRivest/xps-13-7390-2-in-1-webcam-linux),
pinned at `336a8a369a9d83f6d9805e2541c56bc7fa4d076a`.
The original implementation and hardware bring-up are upstream work, not work
newly implemented by this Debian port.

`driver/int346f/int3472.h` is an unmodified copy of
[Linux v6.18 include/linux/platform_data/x86/int3472.h](https://github.com/torvalds/linux/blob/v6.18/include/linux/platform_data/x86/int3472.h),
authored by Dan Scally and distributed under GPL-2.0. It is private to this
out-of-tree module. None of its structures is passed to the in-tree INT3472 driver.
Debian 6.12's older private structure is not ABI-compatible with these sources.

The Debian changes adapt the V4L2 link-frequency call and namespace macros to
6.12, reject failed DMA mappings, constrain sensor selection, and add opt-in
packaging. Packaging and tests in this branch are GPL-2.0-only, like the combined
project. The inherited COPYING file describes Linux's original licensing and
is retained for provenance; the actual GPL-2.0 text is in LICENSES/GPL-2.0.


## Kernel modules

The IPU4P modules started from the mainline Linux Intel IPU6 driver.
They use IPU4 hardware definitions from Intel's `linux-intel-lts` `4.19/base` branch.
The port targets the Ice Lake IPU4P PCI device `8086:8a19`.

The INT346F module started from the mainline Linux INT3472 discrete camera driver.
The OV01A10 module started from the mainline Linux OV01A10 sensor driver.

Each source file keeps its original SPDX license identifier.
The combined kernel module work is distributed under GPL-2.0-only.

## Hardware values

The IPU4P PHY and lane configuration values were determined from Dell's Windows camera driver.
Only the required numeric hardware settings are present here.
This repository does not contain the Windows driver.

## Firmware

The required `$CPD` firmware comes from Dell package `4PY3P`.
The package maps `cpd_component_signed.bin` to Intel device `8086:8a19`.
The known firmware SHA-256 value is:

```text
ee534f37f979dfc20e1cb4681bae47c9ec57639f3a2d032b79d77b3097b74d97
```

The firmware is proprietary. Users must download and extract it themselves.
Do not add the firmware or the Dell Windows package to this repository.
