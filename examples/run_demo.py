import asyncio
from kernel.scheduler import Scheduler
from kernel.ipc import IPCBroker, Message
from kernel.hal import HAL
from quantum.simulator import SimpleQuantumSimulator
from examples.tasks import simple_io_task, long_compute_task

async def demo():
    # Build components
    ipc = IPCBroker()
    ipc.register("q_orchestrator")
    ipc.register("worker")
    hal = HAL()
    print("[demo] HAL init device 1:", hal.init_device(1))
    print("[demo] HAL read reg:", hal.read_register(1, 10))

    sim = SimpleQuantumSimulator()
    # submit a sample job
    job_id = await sim.submit_circuit({"gates": [("h",), ("x",)]}, shots=500)
    print("[demo] submitted job", job_id)

    # Scheduler
    sched = Scheduler(time_slice=0.05)

    # Add tasks with different success_prob values (simulating AI Orchestrator hints)
    sched.add_task(simple_io_task, priority=1, success_prob=0.9)
    sched.add_task(long_compute_task, priority=0, success_prob=0.2)

    sched.start()

    # Let scheduler run for a bit
    await asyncio.sleep(1.0)

    # Poll job status
    st = await sim.status(job_id)
    print("[demo] job status", st)
    try:
        res = await sim.result(job_id)
        print("[demo] job result", res)
    except RuntimeError:
        print("[demo] job not ready yet")

    sched.stop()
    # wait a short while for graceful stop
    await asyncio.sleep(0.1)

if __name__ == "__main__":
    asyncio.run(demo())