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

import boot.cmdline as m

def check(label, cond):
    print(label, ':', 'OK' if cond else 'FAIL')
    if not cond:
        raise SystemExit(1)

p2 = m.parse_cmdline('console="ttyS0,115200n8"')
print('console value:', repr(p2['console'].value))
print('console kind :', p2['console'].kind)
print('quoted       :', m.CmdParamKind.QUOTED)
print('expected match:', p2['console'].value == 'ttyS0,115200n8')
print('expected kind :', p2['console'].kind == m.CmdParamKind.QUOTED)
