#!/usr/bin/env bash
# Explicit, manual setup only. Never invoked by package installation or systemd.
set -euo pipefail

if [[ $# -ne 1 || $1 != --enable-hardware-test ]]; then
  echo "Refusing hardware changes. Read README.md before passing --enable-hardware-test." >&2
  exit 2
fi
if [[ $EUID -ne 0 || ! -f /etc/xps7390-webcam/enable-experimental ]]; then
  echo "Root and /etc/xps7390-webcam/enable-experimental are required." >&2
  exit 1
fi
if [[ $(uname -r) != 6.12.113+deb13-amd64 ]]; then
  echo "Only 6.12.113+deb13-amd64 has been build-validated." >&2
  exit 1
fi
unset XPS_SYSFS_ROOT
"$(dirname "${BASH_SOURCE[0]}")/check-hardware.sh"
if [[ -d /sys/module/ov01a10 ]]; then
  echo "The in-tree ov01a10 is loaded. Resolve the conflict manually; nothing was unloaded." >&2
  exit 1
fi
if [[ ! -f /lib/firmware/intel/ipu/ipu4p_cpd.bin ]]; then
  echo "Install your locally extracted firmware before hardware setup." >&2
  exit 1
fi
for name in video-ipu4-raw video-ipu4-sensor; do
  if [[ -e /dev/$name && ! -L /dev/$name ]]; then
    echo "Refusing to replace /dev/$name." >&2
    exit 1
  fi
done
# Do not unload or reconfigure a loopback module already used by another app.
if [[ -d /sys/module/v4l2loopback ]] &&
   [[ $(cat /sys/class/video4linux/video57/name 2>/dev/null || true) != "XPS7390 Camera" ]]; then
  echo "Existing v4l2loopback is not configured for this service; resolve it manually." >&2
  exit 1
fi
modprobe ipu-bridge
modprobe int346f
modprobe ov01a10-i346f
modprobe intel-ipu4p
modprobe intel-ipu4p-isys
modprobe v4l2loopback video_nr=57 card_label="XPS7390 Camera" exclusive_caps=1

media=""
for _ in $(seq 1 50); do
  for candidate in /dev/media*; do
    [[ -e "$candidate" ]] || continue
    if media-ctl -d "$candidate" -p 2>/dev/null | grep -q 'Intel IPU4P'; then
      media=$candidate
      break 2
    fi
  done
  sleep 0.2
done
if [[ -z "$media" ]]; then
  echo "The IPU4P media device did not appear." >&2
  exit 1
fi
sensor=$(media-ctl -d "$media" -p | python3 -c '
import re, sys
names = re.findall(r"entity \d+: (ov01a10 [^\s]+) \(", sys.stdin.read())
if len(names) != 1:
    sys.exit("Expected exactly one OV01A10 entity in the IPU4P graph")
print(names[0])
')
raw=$(media-ctl -d "$media" -e "Intel IPU4P ISYS Capture 8")
subdev=$(media-ctl -d "$media" -e "$sensor")
[[ "$raw" == /dev/video* && -c "$raw" ]]
[[ "$subdev" == /dev/v4l-subdev* && -c "$subdev" ]]
[[ $(cat /sys/class/video4linux/video57/name) == "XPS7390 Camera" ]]
format=SBGGR10_1X10/1280x800
media-ctl -d "$media" -V '"'"$sensor"'":0 [fmt:'"$format"']'
media-ctl -d "$media" -V '"Intel IPU4P CSI2 1":0 [fmt:'"$format"']'
media-ctl -d "$media" -V '"Intel IPU4P CSI2 1":1 [fmt:'"$format"']'
media-ctl -d "$media" -l '"Intel IPU4P CSI2 1":1 -> "Intel IPU4P ISYS Capture 8":0 [1]'
v4l2-ctl -d "$raw" --set-fmt-video=width=1280,height=800,pixelformat=pBAA
v4l2-ctl -d "$subdev" --set-ctrl exposure=888,analogue_gain=1024,digital_gain=1024
ln -sfn "$raw" /dev/video-ipu4-raw
ln -sfn "$subdev" /dev/video-ipu4-sensor
echo "Configured $raw and $subdev. Capture has not been started."
echo "Explicitly start xps7390-webcam.service only when ready to test capture."
