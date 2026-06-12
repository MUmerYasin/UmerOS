import asyncio

async def simple_io_task():
    # Simulated blocking I/O broken into cooperative awaits
    for i in range(3):
        print("[task] simple_io_task step", i)
        await asyncio.sleep(0.02)

async def long_compute_task():
    # Simulated CPU-bound work; break into small awaits to remain cooperative
    total = 0
    for i in range(100000):
        total += i
        if i % 10000 == 0:
            await asyncio.sleep(0)  # yield control
    print("[task] long_compute_task done", total)