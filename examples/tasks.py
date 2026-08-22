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