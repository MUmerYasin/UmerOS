"""
UmerOS /sbin Hierarchy
=======================
Essential system administration binaries.

According to FHS 3.0 / TLDP:
  - /sbin contains essential system binaries for administration.
  - These are typically only usable by root.
  - Used for system maintenance, recovery, and boot operations.
"""

from .sbin_manager import SbinManager, get_sbin_manager

__all__ = ["SbinManager", "get_sbin_manager"]
