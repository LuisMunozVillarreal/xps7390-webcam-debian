#!/usr/bin/env python3
"""Compile actual DMA mapping functions with injected allocation/MMU failures.

No hardware or kernel is needed. Test rollback and propagation, not real DMA.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DmaResultTest(unittest.TestCase):
    def test_zero_negative_and_positive_mapping_results(self):
        source = (ROOT / "driver/ipu4p/ipu4p-dma.c").read_text()
        start = source.index("int ipu4p_dma_map_sgtable(")
        end = source.index("\nEXPORT_SYMBOL", start)
        wrapper = source[start:end]
        program = r'''
#include <assert.h>
#include <errno.h>
struct ipu4p_bus_device { int unused; };
struct sg_table { void *sgl; int nents; };
enum dma_data_direction { DMA_TO_DEVICE };
static int result;
static int ipu4p_dma_map_sg(struct ipu4p_bus_device *sys, void *sgl,
                          int nents, enum dma_data_direction dir,
                          unsigned long attrs)
{
    (void)sys; (void)sgl; (void)nents; (void)dir; (void)attrs;
    return result;
}
''' + wrapper + r'''
int main(void) {
    struct ipu4p_bus_device sys = {0};
    struct sg_table sgt = {0, 4};
    result = 0;
    assert(ipu4p_dma_map_sgtable(&sys, &sgt, DMA_TO_DEVICE, 0) == -EIO);
    assert(sgt.nents == 4);
    result = -ENOMEM;
    assert(ipu4p_dma_map_sgtable(&sys, &sgt, DMA_TO_DEVICE, 0) == -ENOMEM);
    assert(sgt.nents == 4);
    result = 2;
    assert(ipu4p_dma_map_sgtable(&sys, &sgt, DMA_TO_DEVICE, 0) == 0);
    assert(sgt.nents == 2);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "dma-test.c"
            exe = Path(tmp) / "dma-test"
            src.write_text(program)
            subprocess.run([os.environ.get("CC", "cc"), "-Wall", "-Wextra", "-Werror",
                            str(src), "-o", str(exe)], check=True)
            subprocess.run([str(exe)], check=True)


class DmaMapperRollbackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (ROOT / "driver/ipu4p/ipu4p-dma.c").read_text()
        start = source.index("void ipu4p_dma_unmap_sg(")
        end = source.index("\nEXPORT_SYMBOL_NS_GPL(ipu4p_dma_map_sg,", start)
        functions = "\n".join(line for line in source[start:end].splitlines()
                              if not line.startswith("EXPORT_SYMBOL"))
        fixture = (ROOT / "tests/dma_mapper_fixture.c").read_text()
        tmp = tempfile.TemporaryDirectory(prefix="xps-dma-mapper-")
        cls.addClassCleanup(tmp.cleanup)
        src = Path(tmp.name) / "mapper.c"
        cls.exe = Path(tmp.name) / "mapper"
        src.write_text(fixture.replace("/* ACTUAL_DMA_FUNCTIONS */", functions))
        subprocess.run([os.environ.get("CC", "cc"), "-Wall", "-Wextra", "-Werror",
                        "-Wno-unused-parameter", str(src), "-o", str(cls.exe)],
                       check=True)

    def test_first_entry_failure_frees_iova(self):
        subprocess.run([str(self.exe), "0"], check=True)

    def test_later_entry_failures_restore_addresses_and_free_once(self):
        for entry in (1, 2):
            with self.subTest(entry=entry):
                subprocess.run([str(self.exe), str(entry)], check=True)

    def test_iova_allocation_failure_leaves_addresses_unchanged(self):
        subprocess.run([str(self.exe), "-2"], check=True)

    def test_success_keeps_iova_until_unmap(self):
        subprocess.run([str(self.exe), "-1"], check=True)


if __name__ == "__main__":
    unittest.main()
