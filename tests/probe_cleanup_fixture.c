/* Actual firmware mapping and probe unwind run with kernel API test doubles.
 * DMA_FIXTURE supplies the existing IOVA/MMU ownership assertions.
 */
/* DMA_FIXTURE */
#include <stdbool.h>
#include <string.h>
#define GFP_KERNEL 0
#define PAGE_SIZE 4096
#define IS_ERR_OR_NULL(p) (!(p))
#define IRQF_SHARED 0
#define IPU4P_NAME "test"
#define BUTTRESS_REG_SKU 0
#define GENMASK(a, b) 0
#define FIELD_GET(mask, val) (val)
#define dev_info dev_dbg
#define dev_err_probe(dev, ret, ...) dev_dbg(dev, __VA_ARGS__)
#define PKG_DIR_SIZE 64
#define PKG_DIR_ENT_LEN 16
#define MAX_PKG_DIR_ENT_CNT 4

struct firmware { const void *data; size_t size; };
struct pci_dev { struct device dev; int irq, device; };
struct ipu4p_device {
    struct pci_dev *pdev;
    struct ipu4p_bus_device *psys, *isys;
    const struct firmware *cpd_fw;
    void *base;
    int hw_ver;
    bool bus_ready_to_probe;
};
struct page { int unused; };
struct ipu4p_cpd_ent { unsigned int len, offset; };
static const struct ipu4p_cpd_ent entry = { .len = 16, .offset = 64 };
static int failure;
/* Failures before/inside mapping and at each subsequent acquisition. */
enum { RESUME = 1, HW_INIT, INVALID_FW, PAGES_ALLOC, PAGE_LOOKUP,
       SG_ALLOC, PCI_MAP, IOVA_ALLOC, FIRST_MAP, LATER_MAP,
       PKG_ALLOC, PKG_PARSE, IRQ, AUTH, SUCCESS };
static int pci_live, sg_live, pages_live, pkg_live, rpm_live, hw_live, irq_live;
static int pci_maps, pci_unmaps, sg_allocs, sg_frees, pkg_allocs, pkg_frees;
static int releases, bus_deletes, buttress_exits, mmu_cleanups, pkg_free_calls;
static unsigned char firmware_data[4 * PAGE_SIZE];
static const unsigned long original_addresses[] = {0x200000, 0x500000, 0x900000};

static bool is_vmalloc_addr(const void *addr) { return false; }
static bool virt_addr_valid(const void *addr) { return failure != INVALID_FW; }
static void *kmalloc_array(size_t count, size_t size, int flags)
{
    if (failure == PAGES_ALLOC) return NULL;
    assert(!pages_live++);
    return calloc(count, size);
}
static void kfree(void *ptr) { assert(pages_live-- == 1); free(ptr); }
static struct page *virt_to_page(const void *addr)
{
    static struct page page;
    return failure == PAGE_LOOKUP ? NULL : &page;
}
#define vmalloc_to_page virt_to_page
static int sg_alloc_table_from_pages(struct sg_table *sgt, struct page **pages,
                                    unsigned long count, int offset,
                                    size_t size, int flags)
{
    if (failure == SG_ALLOC) return -ENOMEM;
    assert(!sg_live++);
    sg_allocs++;
    sgt->sgl = calloc(3, sizeof(*sgt->sgl));
    assert(sgt->sgl);
    sgt->nents = 3;
    sgt->sgl[0].length = 4096;
    sgt->sgl[1].length = 5000;
    sgt->sgl[2].length = 123;
    return 0;
}
static void sg_free_table(struct sg_table *sgt)
{
    assert(rpm_live && hw_live);
    assert(!pci_live && sg_live-- == 1);
    sg_frees++;
    free(sgt->sgl);
    sgt->sgl = NULL; /* Match sg_free_table's postcondition in the kernel. */
}
static int dma_map_sgtable(struct device *dev, struct sg_table *sgt, int dir,
                           unsigned long attrs)
{
    if (failure == PCI_MAP) return -EIO;
    assert(sg_live && !pci_live++);
    pci_maps++;
    for (int i = 0; i < 3; i++) sgt->sgl[i].address = original_addresses[i];
    return 0;
}
static void dma_unmap_sgtable(struct device *dev, struct sg_table *sgt, int dir,
                             unsigned long attrs)
{
    assert(rpm_live && hw_live);
    assert(!live && !mapped && pci_live-- == 1);
    for (int i = 0; i < 3; i++) assert(sgt->sgl[i].address == original_addresses[i]);
    pci_unmaps++;
}
static void ipu4p_dma_sync_sgtable(struct ipu4p_bus_device *sys, struct sg_table *sgt)
{ assert(live && pci_live && sg_live); }

/* ACTUAL_DMA_FUNCTIONS */
/* ACTUAL_FIRMWARE_FUNCTIONS */

static const struct ipu4p_cpd_ent *ipu4p_cpd_get_manifest(const void *src) { return &entry; }
#define ipu4p_cpd_get_metadata ipu4p_cpd_get_manifest
#define ipu4p_cpd_get_moduledata ipu4p_cpd_get_manifest
static void *ipu4p_dma_alloc(struct ipu4p_bus_device *sys, size_t size,
                             dma_addr_t *dma, int flags, int attrs)
{
    if (failure == PKG_ALLOC) return NULL;
    assert(live && !pkg_live++);
    pkg_allocs++;
    *dma = 0xa00000;
    return calloc(1, size);
}
static void ipu4p_dma_free(struct ipu4p_bus_device *sys, size_t size,
                          void *ptr, dma_addr_t dma, int attrs)
{
    pkg_free_calls++;
    /* Production warns and returns when no package IOVA exists. The final
     * call count still rejects any attempt to free an unacquired package. */
    if (!ptr) return;
    assert(pkg_live-- == 1);
    assert(live && hw_live && rpm_live);
    pkg_frees++;
    free(ptr);
}
static int ipu4p_cpd_parse_module_data(struct ipu4p_device *isp, const void *src,
                                      unsigned int len, dma_addr_t dma,
                                      void *pkg, const void *meta, unsigned int mlen)
{ return failure == PKG_PARSE ? -EINVAL : 0; }
static void ipu4p_dma_sync_single(struct ipu4p_bus_device *sys, dma_addr_t dma, size_t size) {}
/* ACTUAL_PACKAGE_FUNCTIONS */

static int pm_runtime_resume_and_get(struct device *dev)
{ if (failure == RESUME) return -EIO; assert(!rpm_live++); return 0; }
static void pm_runtime_put_sync(struct device *dev)
{
    assert(!hw_live && rpm_live-- == 1);
    if (failure != SUCCESS) assert(!live && !pci_live && !pkg_live && !irq_live);
}
#define pm_runtime_put pm_runtime_put_sync
static int ipu4p_mmu_hw_init(struct ipu4p_mmu *mmu)
{ assert(rpm_live); if (failure == HW_INIT) return -EIO; assert(!hw_live++); return 0; }
static void ipu4p_mmu_hw_cleanup(struct ipu4p_mmu *mmu)
{ assert(rpm_live && hw_live-- == 1); }
static int ipu4p_buttress_isr, ipu4p_buttress_isr_threaded;
static int devm_request_threaded_irq(struct device *dev, int irq, int isr,
                                     int threaded, int flags, const char *name,
                                     struct ipu4p_device *isp)
{ assert(pkg_live); if (failure == IRQ) return -EIO; assert(!irq_live++); return 0; }
static void devm_free_irq(struct device *dev, int irq, struct ipu4p_device *isp)
{ assert(irq_live-- == 1 && rpm_live && hw_live); }
static int ipu4p_buttress_authenticate(struct ipu4p_device *isp)
{ assert(irq_live); return failure == AUTH ? -EIO : 0; }
static void ipu4p_mmu_cleanup(struct ipu4p_mmu *mmu)
{ assert(!live && !hw_live); mmu_cleanups++; }
static void ipu4p_bus_del_devices(struct pci_dev *pdev)
{ assert(!rpm_live && !pci_live && !pkg_live && !irq_live); bus_deletes++; }
static void release_firmware(const struct firmware *fw) { releases++; }
static void ipu4p_buttress_exit(struct ipu4p_device *isp) { buttress_exits++; }
static void ipu4p_configure_vc_mechanism(struct ipu4p_device *isp) {}
static unsigned int readl(void *addr) { return 0; }
static void pm_runtime_put_noidle(struct device *dev) {}
static void pm_runtime_allow(struct device *dev) {}

/* Start at the probe's runtime-PM acquisition with both bus devices owned.
 * Everything from that acquisition through the failure labels is production C.
 */
static int probe_after_bus_init(struct ipu4p_device *isp)
{
    struct pci_dev *pdev = isp->pdev;
    struct device *dev = &pdev->dev;
    unsigned int val, sku_id, version;
    int ret;
/* ACTUAL_PROBE_TAIL */

int main(int argc, char **argv)
{
    assert(argc == 2);
    failure = atoi(argv[1]);
    fail_alloc = failure == IOVA_ALLOC;
    fail_at = failure == FIRST_MAP ? 0 : failure == LATER_MAP ? 1 : -1;
    struct info info = { .aperture_end = 0xffffffff };
    struct dmap dmap = { .mmu_info = &info };
    struct ipu4p_mmu mmu = { .dmap = &dmap, .tlb_invalidate = invalidate };
    struct pci_dev pci = {0};
    struct firmware fw = { .data = firmware_data, .size = sizeof(firmware_data) };
    struct ipu4p_device isp = { .pdev = &pci, .cpd_fw = &fw };
    struct ipu4p_bus_device psys = { .mmu = &mmu, .isp = &isp };
    struct ipu4p_bus_device isys = { .mmu = &mmu, .isp = &isp };
    isp.psys = &psys;
    isp.isys = &isys;
    int ret = probe_after_bus_init(&isp);
    int expected = failure == SUCCESS ? 0 : failure == INVALID_FW ? -EDOM :
        (failure == PAGES_ALLOC || failure == PAGE_LOOKUP ||
         failure == SG_ALLOC || failure == PKG_ALLOC) ? -ENOMEM :
        failure == PKG_PARSE ? -EINVAL : -EIO;
    assert(ret == expected);
    if (failure == SUCCESS) {
        assert(isp.bus_ready_to_probe && live && pci_live && pkg_live && irq_live);
        assert(!rpm_live && !hw_live && !bus_deletes && !releases && !buttress_exits);
        assert(!freed && !pci_unmaps && !sg_frees && !pkg_frees);
        /* Normal removal is outside this probe-unwind regression. */
        return 0;
    }
    assert(!isp.bus_ready_to_probe);
    assert(!live && !mapped && !pci_live && !sg_live && !pages_live && !pkg_live);
    assert(!rpm_live && !hw_live && !irq_live);
    assert(allocated == freed && pci_maps == pci_unmaps && sg_allocs == sg_frees);
    assert(pkg_allocs == pkg_frees && pkg_free_calls == pkg_allocs);
    assert(releases == 1 && bus_deletes == 1 && buttress_exits == 1 && mmu_cleanups == 2);
    printf("probe failure=%d ret=%d: all acquired resources released once\n", failure, ret);
    return 0;
}
