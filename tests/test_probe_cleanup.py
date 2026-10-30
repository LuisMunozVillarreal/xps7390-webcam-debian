#!/usr/bin/env python3
"""Execute actual firmware/package mapping and probe cleanup, not real DMA.

The probe excerpt starts after bus-device acquisition. Kernel API doubles own
resources and inject failures; production C owns all mapping and unwind logic.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def functions(path, start, end):
    source = (ROOT / path).read_text()
    source = source[source.index(start):]
    source = source[:source.index(end)]
    return "\n".join(line for line in source.splitlines()
                     if not line.startswith("EXPORT_SYMBOL"))


class ProbeCleanupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dma_fixture = (ROOT / "tests/dma_mapper_fixture.c").read_text()
        dma_fixture = dma_fixture.split("/* ACTUAL_DMA_FUNCTIONS */")[0]
        # Extend only the fixture types needed by the firmware/probe functions.
        dma_fixture = dma_fixture.replace(
            "struct ipu4p_bus_device {",
            "struct scatterlist;\n"
            "struct sg_table { struct scatterlist *sgl; int nents; };\n"
            "struct ipu4p_bus_device {\n"
            "    struct ipu4p_device *isp;\n"
            "    struct sg_table fw_sgt;\n"
            "    void *pkg_dir;\n"
            "    unsigned int pkg_dir_size;\n"
            "    dma_addr_t pkg_dir_dma_addr;")
        fixture = (ROOT / "tests/probe_cleanup_fixture.c").read_text()
        replacements = {
            "DMA_FIXTURE": dma_fixture,
            "ACTUAL_DMA_FUNCTIONS": functions(
                "driver/ipu4p/ipu4p-dma.c", "void ipu4p_dma_unmap_sg(",
                "EXPORT_SYMBOL_NS_GPL(ipu4p_dma_unmap_sgtable,"),
            "ACTUAL_FIRMWARE_FUNCTIONS": functions(
                "driver/ipu4p/ipu4p-buttress.c", "int ipu4p_buttress_map_fw_image(",
                "EXPORT_SYMBOL_NS_GPL(ipu4p_buttress_unmap_fw_image,"),
            "ACTUAL_PACKAGE_FUNCTIONS": functions(
                "driver/ipu4p/ipu4p-cpd.c", "int ipu4p_cpd_create_pkg_dir(",
                "EXPORT_SYMBOL_NS_GPL(ipu4p_cpd_free_pkg_dir,"),
            "ACTUAL_PROBE_TAIL": functions(
                "driver/ipu4p/ipu4p.c",
                "\tret = pm_runtime_resume_and_get(&isp->psys->auxdev.dev);",
                "\nstatic void ipu4p_pci_remove("),
        }
        for marker, source in replacements.items():
            fixture = fixture.replace("/* " + marker + " */", source)
        tmp = tempfile.TemporaryDirectory(prefix="xps-probe-cleanup-")
        cls.addClassCleanup(tmp.cleanup)
        src = Path(tmp.name) / "probe.c"
        cls.exe = Path(tmp.name) / "probe"
        src.write_text(fixture)
        subprocess.run([os.environ.get("CC", "cc"), "-Wall", "-Wextra", "-Werror",
                        "-Wno-unused-parameter", "-Wno-unused-label",
                        "-fsanitize=undefined", "-fno-sanitize-recover=all",
                        str(src), "-o", str(cls.exe)], check=True)

    def test_firmware_map_failure_and_adjacent_probe_ownership(self):
        # First exercise the reported first-entry MMU failure, then every
        # acquisition from runtime PM through authentication and success.
        for failure in (9, 1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15):
            with self.subTest(failure=failure):
                subprocess.run([str(self.exe), str(failure)], check=True)


if __name__ == "__main__":
    unittest.main()
