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
UmerOS /usr/share/sgml Hierarchy Commands
==========================================
FHS 3.0 §4.11.11: SGML/XML data files.

The /usr/share/sgml directory contains architecture-independent
SGML (Standard Generalized Markup Language) and XML files.
Subdirectories include:
  - docbook/  - DocBook DTD and stylesheets
  - dsssl/    - DSSSL stylesheets
  - iso8879/  - ISO 8879 entity sets
  - sgml-ent/ - General SGML entities
  - xml/      - XML-specific data
"""

from __future__ import annotations

from core.command import Command


class SgmlDirCommand(Command):
    """Display /usr/share/sgml directory structure."""

    name = "sgml-dir"
    description = "Display /usr/share/sgml directory structure"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/share/sgml/ - SGML/XML architecture-independent data\n"
            "  docbook/    - DocBook DTD and stylesheets\n"
            "  dsssl/      - DSSSL (Document Style Semantics and Specification Language)\n"
            "  iso8879/    - ISO 8879 character entity sets\n"
            "  sgml-ent/   - General SGML entity definitions\n"
            "  xml/        - XML data files\n"
            "  catalog     - Main SGML catalog file\n"
            "  sgml.gis    - SGML document type declarations\n"
        )


class SgmlCatalogCommand(Command):
    """Manage SGML/XML catalog files."""

    name = "sgml-catalog"
    description = "Manage SGML/XML catalog files"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "SGML Catalog Files:\n"
            "  /etc/sgml/catalog         - System-wide catalog\n"
            "  /etc/sgml/*/cat catalogs   - Per-package catalogs\n"
            "  $SGML_CATALOG_FILES        - User catalog override\n"
            "  Functions: Maps public identifiers to system files\n"
            "  Used by: OpenJade, JadeTeX, SGML tools\n"
        )


class DocbookCommand(Command):
    """DocBook DTD and stylesheet management."""

    name = "docbook"
    description = "DocBook DTD and stylesheet management"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "DocBook Documentation System:\n"
            "  /usr/share/sgml/docbook/sgml-dtd/  - SGML DTDs\n"
            "  /usr/share/sgml/docbook/xml-dtd/   - XML DTDs\n"
            "  /usr/share/sgml/docbook/xsl-stylesheets/ - XSL stylesheets\n"
            "  Versions: 3.1, 4.1.2, 4.2, 4.3, 4.4, 4.5\n"
            "  Formats: article, book, report, set\n"
        )


class SgmlEntitiesCommand(Command):
    """SGML entity definitions."""

    name = "sgml-entities"
    description = "SGML entity definition files"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "SGML Entity Files:\n"
            "  /usr/share/sgml/iso8879/ - ISO 8879 character entities\n"
            "    isoamsa.ent  - Mathematical symbols A\n"
            "    isoamsb.ent  - Mathematical symbols B\n"
            "    isogrk1.ent  - Greek letters\n"
            "    isonum.ent   - Numeric entities\n"
            "    isolat1.ent  - Latin characters\n"
            "  Usage: Referenced in DTDs for special characters\n"
        )
