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

def _read_file(path: str) -> str:
    """Read a file from the real /proc if it exists, otherwise return empty string."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""

def parse_key_value(raw: str) -> dict:
    """Parse simple ``Key: Value`` lines into a dictionary.
    Empty lines are ignored. Whitespace around keys and values is stripped.
    """
    result = {}
    for line in raw.splitlines():
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        result[key.strip()] = value.strip()
    return result

def parse_key_value_multi(raw: str) -> list[dict]:
    """Parse files that contain multiple sections separated by blank lines
    (e.g., /proc/cpuinfo). Returns a list of dictionaries, one per section.
    """
    sections = []
    current = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            if current:
                sections.append(current)
                current = {}
            continue
        if ':' in line:
            key, value = line.split(':', 1)
            current[key.strip()] = value.strip()
    if current:
        sections.append(current)
    return sections
