#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>

#define PROJECT_C_ACCESS_COUNT 64u
#define PROJECT_C_STRIDE_WORDS 4u
#define PROJECT_C_BUFFER_WORDS (PROJECT_C_ACCESS_COUNT * PROJECT_C_STRIDE_WORDS)

static uint32_t buffer[PROJECT_C_BUFFER_WORDS];
static volatile uint32_t sink;

static void init_buffer(void)
{
    for (uint32_t i = 0; i < PROJECT_C_BUFFER_WORDS; ++i) {
        buffer[i] = i + 1u;
    }
}

static void emit_access(uint32_t seq, const volatile uint32_t *address)
{
    printf(
        "PROJECT_C_MEM workload=stride_scan seq=%" PRIu32
        " command=READ address=0x%016" PRIxPTR
        " size=4 pc=0x0 symbol=stride_scan\n",
        seq,
        (uintptr_t)address);
}

int main(void)
{
    init_buffer();
    printf(
        "PROJECT_C_TRACE_BEGIN workload=stride_scan count=%u "
        "stride_bytes=%u element_size=4\n",
        PROJECT_C_ACCESS_COUNT,
        PROJECT_C_STRIDE_WORDS * 4u);

    for (uint32_t i = 0; i < PROJECT_C_ACCESS_COUNT; ++i) {
        const volatile uint32_t *address = &buffer[i * PROJECT_C_STRIDE_WORDS];
        emit_access(i + 1u, address);
        sink += *address;
    }

    printf("PROJECT_C_TRACE_END workload=stride_scan sink=%" PRIu32 "\n", sink);
    return sink == 0u;
}
