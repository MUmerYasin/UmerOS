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

"""
UmerOS /opt Installers Package

This package provides standardized installation scripts for common software
packages to be installed in /opt according to Linux Filesystem Hierarchy standards.
"""

from .sample_app import install_sample_app
from .web_server import install_web_server
from .database import install_database
from .development import install_development_tools

__all__ = [
    'install_sample_app',
    'install_web_server',
    'install_database',
    'install_development_tools'
]
