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

import re

with open('bin/usr_commands.py') as f:
    uc = set(re.findall(r'class (\w+Command):', f.read()))

with open('bin/usr_cmds.py') as f:
    ucs = set(re.findall(r'class (\w+Command):', f.read()))

unique = sorted(ucs - uc)
for c in unique:
    cmd = c.replace('Command', '').lower()
    print(f'    "{cmd}": ("usr_cmds", "{c}"),')
