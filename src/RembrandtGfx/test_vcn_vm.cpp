#include <cstdint>
#include <cstddef>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <initializer_list>
#include "vcn_vm.hpp"

int main() {
    struct { uint32_t before, registers[214], after; } table;
    for (uint32_t base : {0u, 0x1a000u, 0x1b000u}) {
        table.before = table.after = 0x12345678;
        for (size_t i = 0; i < 214; i++)
            table.registers[i] = base + VcnVmRegisters[i].oldOffset;
        VcnVmLayout layout {};
        assert(remapVcnVmRegisters(table.registers, 214, &layout));
        assert(layout.base == base && layout.matched == 214);
        assert(table.before == 0x12345678 && table.after == 0x12345678);
        assert(table.registers[12 + 2 * 7] == 0x1a950); // Context 2 base low.
        assert(table.registers[12 + 16 * 7 + 6 * 5 + 2] == 0x1aa31); // Engine 6 request.
        assert(table.registers[12 + 16 * 7 + 6 * 5 + 3] == 0x1aa32); // Engine 6 ack.
    }
    for (size_t i = 0; i < 214; i++)
        table.registers[i] = 0x1a000 + VcnVmRegisters[i].oldOffset;
    table.registers[26] ^= 1;
    auto copy = table;
    VcnVmLayout layout {};
    assert(!remapVcnVmRegisters(table.registers, 214, &layout));
    assert(layout.base == 0x1a000 && layout.matched == 26);
    assert(!memcmp(&table, &copy, sizeof(table)));
    assert(!remapVcnVmRegisters(table.registers, 213));
    assert(!remapVcnVmRegisters(nullptr, 214));
    puts("PASS: actual remapper; complete table, three bases, layout diagnostics, context2/engine6, bounds and mismatch refusal.");
}
