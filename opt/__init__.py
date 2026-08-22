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
UmerOS /opt Package Management System

This module implements the Filesystem Hierarchy compliant /opt directory
structure for add-on software packages in UmerOS.

According to the FHS:
- /opt is reserved for all software and add-on packages not part of default installation
- Each package must locate its static files in /opt/'package' or /opt/'provider' directory tree
- Host-specific configuration files are installed in /etc/opt
- Variable data is installed in /var/opt
- Reserved directories for local system administrator use: bin, doc, include, info, lib, man
"""

__version__ = "1.0.0"
__author__ = "UmerOS Development Team"

from .manager import OptManager
from .package import OptPackage
from .config import OptConfig

__all__ = ['OptManager', 'OptPackage', 'OptConfig', 'OptIntegration']
