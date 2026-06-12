#!/usr/bin/env bash
set -e
cc -fPIC -shared -O2 -o libumerhal.so hal.c
echo "Built drivers/libumerhal.so"