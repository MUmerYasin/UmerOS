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
