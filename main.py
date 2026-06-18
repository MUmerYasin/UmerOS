import asyncio

from bootloader.init import boot
from kernel.umer_kernel import UmerKernel


async def main():
    env = boot()
    kernel = UmerKernel(environment=env)
    await kernel.start()


if __name__ == "__main__":
    asyncio.run(main())