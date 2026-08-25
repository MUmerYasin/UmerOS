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

# [FIX H98] Re-export the real, feature-complete installer (installer.py), not the
# dead non-functional stub (install.py), so `from installer import UmerInstaller`
# returns the canonical class. (The stub was deleted — see H98/H106.)
from .installer import UmerInstaller
