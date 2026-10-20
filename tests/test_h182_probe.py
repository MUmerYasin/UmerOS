from __future__ import annotations
import asyncio

def test_sync_asyncio_run():
    asyncio.run(asyncio.sleep(0.01))
    assert True
