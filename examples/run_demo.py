# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import asyncio
from kernel.scheduler import HybridScheduler as Scheduler
from kernel.ipc import IPCBroker
from kernel.hal import HAL
from quantum.simulator import StatevectorSimulator, QuantumCircuit
from examples.tasks import simple_io_task, long_compute_task

async def demo():
    # Build components
    ipc = IPCBroker()
    ipc.register("q_orchestrator")
    ipc.register("worker")
    hal = HAL()
    print("[demo] HAL init device 1:", hal.init_device(1))
    print("[demo] HAL read reg:", hal.read_register(1, 10))

    sim = StatevectorSimulator()
    # Build a sample circuit
    circuit = QuantumCircuit(2)
    circuit.h(0)
    circuit.x(1)
    result = sim.run(circuit, shots=500)
    print("[demo] job result", result)

    # Scheduler
    sched = Scheduler(time_slice=0.05)

    # Add tasks with different success_prob values (simulating AI Orchestrator hints)
    sched.add_task(simple_io_task, priority=1, success_prob=0.9)
    sched.add_task(long_compute_task, priority=0, success_prob=0.2)

    sched.start()

    # Let scheduler run for a bit
    await asyncio.sleep(1.0)

    sched.stop()
    # wait a short while for graceful stop
    await asyncio.sleep(0.1)

if __name__ == "__main__":
    asyncio.run(demo())