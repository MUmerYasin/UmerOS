// Minimal HAL C stub (drivers/hal.c)
// Build as shared lib: cc -fPIC -shared -O2 -o libumerhal.so hal.c

#include <stdint.h>

// Simulate device init; return 0 on success.
int hw_init_device(int device_id) {
    (void)device_id;
    return 0;
}

// Read register: simulate a register read by returning device_id + reg.
int hw_read_register(int device_id, uint32_t reg, uint32_t *out) {
    if (!out) return -1;
    *out = (uint32_t)(device_id + reg);
    return 0;
}

// Write register: simulate a write; return 0 on success.
int hw_write_register(int device_id, uint32_t reg, uint32_t val) {
    (void)device_id;
    (void)reg;
    (void)val;
    return 0;
}