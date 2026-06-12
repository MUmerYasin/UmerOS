import asyncio
from kernel.scheduler import Scheduler
from kernel.ipc import IPCBroker, Message
import pytest

@pytest.mark.asyncio
async def test_ipc_send_recv():
    ipc = IPCBroker()
    ipc.register("a")
    ipc.register("b")
    msg = Message(sender="a", target="b", payload={"x":1})
    await ipc.send(msg)
    r = await ipc.recv("b")
    assert r.payload == {"x":1}

@pytest.mark.asyncio
async def test_scheduler_runs_tasks():
    sched = Scheduler(time_slice=0.01)

    async def quick_task():
        await asyncio.sleep(0)
    tid = sched.add_task(quick_task, priority=0, success_prob=0.5)
    sched.start()
    await asyncio.sleep(0.05)
    sched.stop()
    # Ensure task completed (ready queue should not contain tid)
    assert tid not in sched.ready