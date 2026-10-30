#!/usr/bin/env bash
set -euo pipefail

EXPECTED_SHA256=ee534f37f979dfc20e1cb4681bae47c9ec57639f3a2d032b79d77b3097b74d97

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 PATH-TO-7390-2IN1-WIN11-A00-4PY3P.CAB OUTPUT-DIRECTORY" >&2
  exit 2
fi
if ! command -v cabextract >/dev/null; then
  echo "cabextract is required." >&2
  exit 1
fi

cab=$(realpath "$1")
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
cabextract -q -d "$tmp" "$cab"
source_file=$(find "$tmp" -type f -iname cpd_component_signed.bin -print -quit)
if [[ -z "$source_file" ]]; then
  echo "cpd_component_signed.bin was not found in the Dell package." >&2
  exit 1
fi

actual=$(sha256sum "$source_file" | cut -d' ' -f1)
if [[ "$actual" != "$EXPECTED_SHA256" ]]; then
  echo "The firmware has an untested SHA-256 value: $actual" >&2
  echo "Expected the firmware from Dell package 4PY3P." >&2
  exit 1
fi

mkdir -p "$2/intel/ipu"
install -m644 "$source_file" "$2/intel/ipu/ipu4p_cpd.bin"
echo "Firmware extracted to $2/intel/ipu/ipu4p_cpd.bin"
