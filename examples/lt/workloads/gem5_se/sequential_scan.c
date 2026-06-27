#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>

#define PROJECT_C_ACCESS_COUNT 64u

static uint32_t buffer[PROJECT_C_ACCESS_COUNT];
static volatile uint32_t sink;

static void init_buffer(void)
{
    for (uint32_t i = 0; i < PROJECT_C_ACCESS_COUNT; ++i) {
        buffer[i] = i + 1u;
    }
}

static void emit_access(uint32_t seq, const volatile uint32_t *address)
{
    printf(
        "PROJECT_C_MEM workload=sequential_scan seq=%" PRIu32
        " command=READ address=0x%016" PRIxPTR
        " size=4 pc=0x0 symbol=sequential_scan\n",
        seq,
        (uintptr_t)address);
}

int main(void)
{
    init_buffer();
    printf(
        "PROJECT_C_TRACE_BEGIN workload=sequential_scan count=%u "
        "element_size=4\n",
        PROJECT_C_ACCESS_COUNT);

    for (uint32_t i = 0; i < PROJECT_C_ACCESS_COUNT; ++i) {
        const volatile uint32_t *address = &buffer[i];
        emit_access(i + 1u, address);
        sink += *address;
    }

    printf("PROJECT_C_TRACE_END workload=sequential_scan sink=%" PRIu32 "\n", sink);
    return sink == 0u;
}
