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
UmerOS /usr/share/templates Hierarchy Commands
===============================================
FHS 3.0 §4.11.13: Default configuration templates.

The /usr/share/templates directory contains default template
files for various applications. These are used as starting
points when creating new configurations. Not all systems
include this directory.
"""

from __future__ import annotations

from core.command import Command


class TemplatesDirCommand(Command):
    """Display /usr/share/templates directory."""

    name = "templates-dir"
    description = "Display /usr/share/templates directory structure"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/share/templates/ - Default configuration templates\n"
            "  Contains default templates for applications\n"
            "  Used as starting points for new configurations\n"
            "  Not all systems include this directory\n"
            "  Subdirectories may include:\n"
            "    email/       - Email templates\n"
            "    documents/   - Document templates\n"
            "    web/         - Web page templates\n"
        )


class TemplateListCommand(Command):
    """List available template categories."""

    name = "template-list"
    description = "List available template categories"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "Template Categories:\n"
            "  email/        - Email message templates\n"
            "  documents/    - Document templates (reports, letters)\n"
            "  web/          - HTML/CSS templates\n"
            "  scripts/      - Script templates (bash, python)\n"
            "  config/       - Configuration file templates\n"
            "  Project: /usr/share/templates/ or ~/.config/templates/\n"
        )


class TemplateShowCommand(Command):
    """Show a specific template."""

    name = "template-show"
    description = "Show contents of a specific template"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        if not args:
            return "Usage: template-show <template-name>\n"
        template = args[0]
        return (
            f"Template: {template}\n"
            f"Location: /usr/share/templates/{template}\n"
            f"Description: Default template file\n"
            f"Usage: Copy to working directory and customize\n"
        )
