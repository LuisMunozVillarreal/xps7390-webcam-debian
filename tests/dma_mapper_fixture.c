/* Compile with the actual DMA mapper/unmapper inserted at the marker. */
#include <assert.h>
#include <errno.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

typedef unsigned long dma_addr_t;
typedef unsigned long phys_addr_t;
struct device { int unused; };
struct iova { unsigned long pfn_lo, pfn_hi; };
struct info { unsigned long aperture_end; };
struct dmap { int iovad; struct info *mmu_info; };
struct ipu4p_mmu {
    struct dmap *dmap;
    void (*tlb_invalidate)(struct ipu4p_mmu *);
};
struct ipu4p_bus_device {
    struct { struct device dev; } auxdev;
    struct ipu4p_mmu *mmu;
};
struct scatterlist { unsigned offset; dma_addr_t address; unsigned length; };
enum dma_data_direction { DMA_TO_DEVICE };
#define sg_dma_address(sg) ((sg)->address)
#define sg_dma_len(sg) ((sg)->length)
#define for_each_sg(list, sg, n, i) \
    for ((i) = 0, (sg) = (list); (unsigned)(i) < (unsigned)(n); (i)++, (sg)++)
#define PHYS_PFN(x) ((x) >> 12)
#define PFN_PHYS(x) ((x) << 12)
#define PFN_UP(x) (((x) + 4095) >> 12)
#define PAGE_ALIGN(x) (((x) + 4095) & ~4095UL)
static void dev_dbg(struct device *dev, const char *format, ...) {}
#define dev_err dev_dbg
#define WARN_ON(x) (x)

static struct iova allocation;
static int allocated, freed, map_calls, unmap_calls, invalidations;
static int fail_at, fail_alloc, live;
static struct { unsigned long iova, phys, size; } mappings[3];
static int mapped;

static struct iova *alloc_iova(int *domain, size_t pages,
                               unsigned long end, int aligned)
{
    assert(!live);
    assert(pages == 4);
    if (fail_alloc)
        return NULL;
    allocation.pfn_lo = 0x100;
    allocation.pfn_hi = allocation.pfn_lo + pages - 1;
    allocated++;
    live = 1;
    return &allocation;
}
static struct iova *find_iova(int *domain, unsigned long pfn)
{
    return live && pfn >= allocation.pfn_lo && pfn <= allocation.pfn_hi
        ? &allocation : NULL;
}
static void __free_iova(int *domain, struct iova *iova)
{
    assert(iova == &allocation);
    assert(live); /* Detect double-free, including after later-entry failure. */
    assert(mapped == 0);
    live = 0;
    freed++;
}
static unsigned long iova_size(struct iova *iova)
{
    return iova->pfn_hi - iova->pfn_lo + 1;
}
static int ipu4p_mmu_map(struct info *info, unsigned long iova,
                        unsigned long addr, unsigned long size)
{
    assert(live);
    if (map_calls++ == fail_at)
        return -ENOMEM;
    assert(mapped < 3);
    assert(iova == (mapped ? mappings[mapped - 1].iova +
                            mappings[mapped - 1].size : 0x100000));
    mappings[mapped].iova = iova;
    mappings[mapped].phys = addr;
    mappings[mapped++].size = size;
    return 0;
}
static unsigned long ipu4p_mmu_iova_to_phys(struct info *info,
                                           unsigned long iova)
{
    for (int i = 0; i < mapped; i++)
        if (mappings[i].iova == iova)
            return mappings[i].phys;
    assert(0 && "restoring an address that was never mapped");
    return 0;
}
static void ipu4p_mmu_unmap(struct info *info, unsigned long iova,
                           unsigned long size)
{
    assert(live);
    assert(iova == 0x100000);
    assert(size == 4 * 4096);
    mapped = 0;
    unmap_calls++;
}
static void invalidate(struct ipu4p_mmu *mmu) { invalidations++; }

/* ACTUAL_DMA_FUNCTIONS */

int main(int argc, char **argv)
{
    assert(argc == 2);
    fail_at = atoi(argv[1]); /* -1: success; -2: allocation failure. */
    fail_alloc = fail_at == -2;
    struct info info = { .aperture_end = 0xffffffff };
    struct dmap dmap = { .mmu_info = &info };
    struct ipu4p_mmu mmu = { .dmap = &dmap, .tlb_invalidate = invalidate };
    struct ipu4p_bus_device sys = { .mmu = &mmu };
    const unsigned long addresses[] = {0x200000, 0x500000, 0x900000};
    const unsigned lengths[] = {4096, 5000, 123};
    struct scatterlist sg[3] = {
        {0, addresses[0], lengths[0]},
        {0, addresses[1], lengths[1]},
        {0, addresses[2], lengths[2]},
    };
    int result = ipu4p_dma_map_sg(&sys, sg, 3, DMA_TO_DEVICE, 0);
    assert(result == (fail_at == -1 ? 3 : 0));
    assert(allocated == !fail_alloc);
    assert(map_calls == (fail_alloc ? 0 : fail_at == -1 ? 3 : fail_at + 1));
    if (fail_at == -1) {
        assert(live && freed == 0 && mapped == 3);
        assert(unmap_calls == 0 && invalidations == 0);
        for (int i = 0; i < 3; i++)
            assert(sg[i].address == mappings[i].iova);
        ipu4p_dma_unmap_sg(&sys, sg, 3, DMA_TO_DEVICE, 0);
    }
    /* Every successful allocation must be freed exactly once. */
    assert(freed == allocated);
    assert(!live && mapped == 0);
    assert(unmap_calls == (fail_at > 0 || fail_at == -1));
    assert(invalidations == unmap_calls);
    for (int i = 0; i < 3; i++) {
        assert(sg[i].address == addresses[i]);
        assert(sg[i].length == lengths[i]);
        assert(sg[i].offset == 0);
    }
    printf("case=%d result=%d allocated=%d freed=%d map_calls=%d unmap_calls=%d\n",
           fail_at, result, allocated, freed, map_calls, unmap_calls);
    return 0;
}
