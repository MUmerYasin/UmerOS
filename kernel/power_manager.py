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

from . import cpuidle

class PowerManager:
    """Manages power‑related actions for the kernel.

    Currently it provides a simple ``cpu_idle`` method which invokes the
    registered ``cpuidle`` driver (if any) and returns the name of the idle
    state entered.
    """
    def cpu_idle(self):
        state_name = cpuidle.cpuidle_enter()
        if state_name is None:
            return 'No cpuidle driver registered – idle skipped.'
        return f'CPU entered idle state: {state_name}'

# Export a singleton instance used by the shell command.
POWER_MANAGER = PowerManager()
