#pragma once
#include "vcn_vm_table.hpp"

struct VcnVmLayout { uint32_t base; size_t matched; };

inline bool remapVcnVmRegisters(uint32_t *registers, size_t count, VcnVmLayout *layout = nullptr) {
    if (layout)
        *layout = {};
    if (!registers || count != VcnVmRegisterCount)
        return false;
    const uint32_t base = registers[0] - VcnVmRegisters[0].oldOffset;
    // Apple queries the source base from hardware; validate its complete layout.
    size_t matched = 0;
    while (matched < count && registers[matched] == base + VcnVmRegisters[matched].oldOffset)
        matched++;
    if (layout)
        *layout = {base, matched};
    if (matched != count)
        return false;
    for (size_t i = 0; i < count; i++)
        registers[i] = 0x1a000 + VcnVmRegisters[i].newOffset;
    return true;
}
