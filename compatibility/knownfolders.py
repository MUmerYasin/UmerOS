"""
Umer OS /compatibility/knownfolders — KNOWNFOLDERID / CSIDL catalogue
======================================================================

Pure-Python implementation of the Windows 10 *Known Folder* surface.

Windows Vista replaced the old ``CSIDL`` (constant special item ID list)
identifiers with GUID-based ``KNOWNFOLDERID`` constants.  The CSIDL system
is still supported for backwards compatibility but Microsoft explicitly
recommends ``SHGetKnownFolderPath`` for all new code.  Both surfaces are
modelled here:

* :class:`Csidl` -- the numeric ``CSIDL_*`` constants from ``shlobj.h``.
* :class:`KnownFolder` -- a ``KNOWNFOLDERID`` record: GUID, display name,
  folder type (PERUSER / COMMON / FIXED / VIRTUAL), default path template
  and the CSIDL it replaced.
* :func:`resolve_known_folder` -- the modern lookup, honouring the
  32-bit-app-on-64-bit-OS redirection rules.
* :func:`resolve_csidl` -- the legacy lookup, translated through the
  CSIDL -> KNOWNFOLDERID mapping.

Folder categories
-----------------

============================ =================================================
``KnownFolderType.PERUSER``  one per user account; roaming by default.
``KnownFolderType.COMMON``   shared by every user on the machine.
``KnownFolderType.FIXED``    tied to the OS installation itself.
``KnownFolderType.VIRTUAL``  a shell namespace object with no real path.
============================ =================================================

Redirection rules
-----------------

``FOLDERID_ProgramFiles``, ``FOLDERID_ProgramFilesCommon`` and
``FOLDERID_System`` resolve differently depending on the bitness of the
calling application and the operating system:

=============================== ============== ======================
Calling app                     OS             Result
=============================== ============== ======================
64-bit                          64-bit         ``Program Files``
32-bit                          64-bit         ``Program Files (x86)``
64-bit                          32-bit         ``Program Files``
32-bit                          32-bit         ``Program Files``
64-bit                          64-bit         ``system32``
32-bit                          64-bit         ``syswow64``
=============================== ============== ======================

References
----------

* https://learn.microsoft.com/en-us/windows/win32/shell/knownfolderid
* https://learn.microsoft.com/en-us/windows/win32/shell/csidl
* https://learn.microsoft.com/en-us/windows/win32/shell/known-folders
* https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/nf-shlobj_core-shgetknownfolderpath
* https://learn.microsoft.com/en-us/windows/deployment/usmt/usmt-recognized-environment-variables

Author:  Umer OS Project
License: GPL-3.0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, IntEnum, IntFlag
from typing import Dict, Iterable, List, Optional, Tuple

log = logging.getLogger("UmerOS.Compat.KnownFolders")


# ---------------------------------------------------------------------------
# CSIDL
# ---------------------------------------------------------------------------

class Csidl(IntEnum):
    """The ``CSIDL_*`` constants from ``shlobj.h``.

    Values are the numeric identifiers Windows uses; they are *not*
    sequential and the gaps are historical.  ``CSIDL_MYDOCUMENTS`` is an
    alias of ``CSIDL_PERSONAL`` exactly as the SDK defines it.
    """

    DESKTOP = 0x0000
    INTERNET = 0x0001
    PROGRAMS = 0x0002
    CONTROLS = 0x0003
    PRINTERS = 0x0004
    PERSONAL = 0x0005
    FAVORITES = 0x0006
    STARTUP = 0x0007
    RECENT = 0x0008
    SENDTO = 0x0009
    BITBUCKET = 0x000A
    STARTMENU = 0x000B
    MYDOCUMENTS = 0x0005          # alias of PERSONAL
    MYMUSIC = 0x000D
    MYVIDEO = 0x000E
    DESKTOPDIRECTORY = 0x0010
    DRIVES = 0x0011
    NETWORK = 0x0012
    NETHOOD = 0x0013
    FONTS = 0x0014
    TEMPLATES = 0x0015
    COMMON_STARTMENU = 0x0016
    COMMON_PROGRAMS = 0x0017
    COMMON_STARTUP = 0x0018
    COMMON_DESKTOPDIRECTORY = 0x0019
    APPDATA = 0x001A
    PRINTHOOD = 0x001B
    LOCAL_APPDATA = 0x001C
    ALTSTARTUP = 0x001D
    COMMON_ALTSTARTUP = 0x001E
    COMMON_FAVORITES = 0x001F
    INTERNET_CACHE = 0x0020
    COOKIES = 0x0021
    HISTORY = 0x0022
    COMMON_APPDATA = 0x0023
    WINDOWS = 0x0024
    SYSTEM = 0x0025
    PROGRAM_FILES = 0x0026
    MYPICTURES = 0x0027
    PROFILE = 0x0028
    SYSTEMX86 = 0x0029
    PROGRAM_FILESX86 = 0x002A
    PROGRAM_FILES_COMMON = 0x002B
    PROGRAM_FILES_COMMONX86 = 0x002C
    COMMON_TEMPLATES = 0x002D
    COMMON_DOCUMENTS = 0x002E
    COMMON_ADMINTOOLS = 0x002F
    ADMINTOOLS = 0x0030
    CONNECTIONS = 0x0031
    COMMON_MUSIC = 0x0035
    COMMON_PICTURES = 0x0036
    COMMON_VIDEO = 0x0037
    RESOURCES = 0x0038
    RESOURCES_LOCALIZED = 0x0039
    COMMON_OEM_LINKS = 0x003A
    CDBURN_AREA = 0x003B
    COMPUTERSNEARME = 0x003D


class CsidlFlag(IntFlag):
    """Flags OR-ed into a :class:`Csidl` value."""

    CREATE = 0x8000
    DONT_UNEXPAND = 0x2000
    DONT_VERIFY = 0x1000
    NO_ALIAS = 0x0800
    PER_USER_INIT = 0x0200
    MASK = 0xFF00


class KnownFolderFlag(IntFlag):
    """``KNOWN_FOLDER_FLAG`` values used by ``SHGetKnownFolderPath``."""

    DEFAULT = 0x0000
    INIT = 0x0200
    NO_ALIAS = 0x0800
    DONT_VERIFY = 0x1000
    DONT_EXPAND = 0x2000
    NO_APPCONTAINER = 0x4000
    CREATE = 0x8000


# ---------------------------------------------------------------------------
# Known Folder records
# ---------------------------------------------------------------------------

class KnownFolderType(Enum):
    """The ``Folder Type`` column of the KNOWNFOLDERID reference table."""

    VIRTUAL = "VIRTUAL"
    PERUSER = "PERUSER"
    COMMON = "COMMON"
    FIXED = "FIXED"


@dataclass(frozen=True)
class KnownFolder:
    """One ``KNOWNFOLDERID`` entry.

    Attributes
    ----------
    name:
        The constant name, e.g. ``FOLDERID_Desktop``.
    guid:
        Canonical registry-form GUID (uppercase, braces).
    display_name:
        Shell display name.
    folder_type:
        PERUSER / COMMON / FIXED / VIRTUAL.
    default_path:
        The default path *template* (``%USERPROFILE%\\Desktop``).  ``None``
        for virtual folders, which have no file-system location.
    csidl_equivalent:
        The CSIDL constants this folder replaced.
    legacy_default_path:
        The pre-Vista path template, when it differed.
    deprecated:
        ``True`` for folders Microsoft has since retired (e.g.
        ``FOLDERID_Games`` returns ``E_INVALIDARG`` on Windows 10 1803+).
    x64_only:
        ``True`` when the folder only exists on 64-bit systems / for
        64-bit callers (``FOLDERID_ProgramFilesX64``).
    """

    name: str
    guid: str
    display_name: str
    folder_type: KnownFolderType
    default_path: Optional[str] = None
    csidl_equivalent: Tuple[Csidl, ...] = ()
    legacy_default_path: Optional[str] = None
    legacy_display_name: Optional[str] = None
    deprecated: bool = False
    x64_only: bool = False

    @property
    def is_virtual(self) -> bool:
        """``True`` when the folder is a shell namespace object."""
        return self.folder_type is KnownFolderType.VIRTUAL

    @property
    def shell_path(self) -> str:
        """The ``::{GUID}`` shell namespace path for this folder."""
        return "::" + self.guid

    @property
    def csidl_names(self) -> Tuple[str, ...]:
        """The CSIDL constant names this folder replaced."""
        return tuple(f"CSIDL_{c.name}" for c in self.csidl_equivalent)


#: Raw table.  Kept as a tuple of plain tuples so the record objects can
#: be built once at import time and shared.
_SPECS: Tuple[Tuple[str, str, str, KnownFolderType, Optional[str],
                    Tuple[Csidl, ...], Optional[str], bool, bool], ...] = (
    ("FOLDERID_AccountPictures", "{008CA0B1-55B4-4C56-B8A8-4DE4B299D3BE}",
     "Account Pictures", KnownFolderType.PERUSER,
     r"%APPDATA%\Microsoft\Windows\AccountPictures", (), None, False, False),
    ("FOLDERID_AddNewPrograms", "{DE61D971-5EBC-4F02-A3A9-6C82895E5C04}",
     "Get Programs", KnownFolderType.VIRTUAL, None, (), None, False, False),
    ("FOLDERID_AdminTools", "{724EF170-A42D-4FEF-9F26-B60E846FBA4F}",
     "Administrative Tools", KnownFolderType.PERUSER,
     r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Administrative Tools",
     (Csidl.ADMINTOOLS,), None, False, False),
    ("FOLDERID_AppDataDesktop", "{B2C5E279-7ADD-439F-B28C-C41FE1BBF672}",
     "AppDataDesktop", KnownFolderType.PERUSER,
     r"%LOCALAPPDATA%\Desktop", (), None, False, False),
    ("FOLDERID_AppDataDocuments", "{7BE16610-1F7F-44AC-BFF0-83E15F2FFCA1}",
     "AppDataDocuments", KnownFolderType.PERUSER,
     r"%LOCALAPPDATA%\Documents", (), None, False, False),
    ("FOLDERID_AppDataFavorites", "{7CFBEFBC-DE1F-45AA-B843-A542AC536CC9}",
     "AppDataFavorites", KnownFolderType.PERUSER,
     r"%LOCALAPPDATA%\Favorites", (), None, False, False),
    ("FOLDERID_AppDataProgramData", "{559D40A3-A036-40FA-AF61-84CB430A4D34}",
     "AppDataProgramData", KnownFolderType.PERUSER,
     r"%LOCALAPPDATA%\ProgramData", (), None, False, False),
    ("FOLDERID_ApplicationShortcuts",
     "{A3918781-E5F2-4890-B3D9-A7E54332328C}",
     "Application Shortcuts", KnownFolderType.PERUSER,
     r"%LOCALAPPDATA%\Microsoft\Windows\Application Shortcuts", (), None,
     False, False),
    ("FOLDERID_AppsFolder", "{1E87508D-89C2-42F0-8A7E-645A0F50CA58}",
     "Applications", KnownFolderType.VIRTUAL, None, (), None, False, False),
    ("FOLDERID_AppUpdates", "{A305CE99-F527-492B-8B1A-7E76FA98D6E4}",
     "Installed Updates", KnownFolderType.VIRTUAL, None, (), None, False, False),
    ("FOLDERID_CameraRoll", "{AB5FB87B-7CE2-4F83-915D-550846C9537B}",
     "Camera Roll", KnownFolderType.PERUSER,
     r"%USERPROFILE%\Pictures\Camera Roll", (), None, False, False),
    ("FOLDERID_CDBurning", "{9E52AB10-F80D-49DF-ACB8-4330F5687855}",
     "Temporary Burn Folder", KnownFolderType.PERUSER,
     r"%LOCALAPPDATA%\Microsoft\Windows\Burn\Burn",
     (Csidl.CDBURN_AREA,), None, False, False),
    ("FOLDERID_ChangeRemovePrograms",
     "{DF7266AC-9274-4867-8D55-3BD661DE872D}",
     "Programs and Features", KnownFolderType.VIRTUAL, None, (), None,
     False, False),
    ("FOLDERID_CommonAdminTools", "{D0384E7D-BAC3-4797-8F14-CBA229B392B5}",
     "Administrative Tools", KnownFolderType.COMMON,
     r"%ALLUSERSPROFILE%\Microsoft\Windows\Start Menu\Programs\Administrative Tools",
     (Csidl.COMMON_ADMINTOOLS,), None, False, False),
    ("FOLDERID_CommonOEMLinks", "{C1BAE2D0-10DF-4334-BEDD-7AA20B227A9D}",
     "OEM Links", KnownFolderType.COMMON,
     r"%ALLUSERSPROFILE%\OEM Links", (Csidl.COMMON_OEM_LINKS,), None,
     False, False),
    ("FOLDERID_CommonPrograms", "{0139D44E-6AFE-49F2-8690-3DAFCAE6FFB8}",
     "Programs", KnownFolderType.COMMON,
     r"%ALLUSERSPROFILE%\Microsoft\Windows\Start Menu\Programs",
     (Csidl.COMMON_PROGRAMS,), None, False, False),
    ("FOLDERID_CommonStartMenu", "{A4115719-D62E-491D-AA7C-E74B8BE3B067}",
     "Start Menu", KnownFolderType.COMMON,
     r"%ALLUSERSPROFILE%\Microsoft\Windows\Start Menu",
     (Csidl.COMMON_STARTMENU,), None, False, False),
    ("FOLDERID_CommonStartup", "{82A5EA35-D9CD-47C5-9629-E15D2F714E6E}",
     "Startup", KnownFolderType.COMMON,
     r"%ALLUSERSPROFILE%\Microsoft\Windows\Start Menu\Programs\StartUp",
     (Csidl.COMMON_STARTUP, Csidl.COMMON_ALTSTARTUP), None, False, False),
    ("FOLDERID_CommonTemplates", "{B94237E7-57AC-4347-9151-B08C6C32D1F7}",
     "Templates", KnownFolderType.COMMON,
     r"%ALLUSERSPROFILE%\Microsoft\Windows\Templates",
     (Csidl.COMMON_TEMPLATES,), None, False, False),
    ("FOLDERID_ComputerFolder", "{0AC0837C-BBF8-452A-850D-79D08E667CA7}",
     "Computer", KnownFolderType.VIRTUAL, None, (Csidl.DRIVES,), None,
     False, False),
    ("FOLDERID_ConflictFolder", "{4BFEFB45-347D-4006-A5BE-AC0CB0567192}",
     "Conflicts", KnownFolderType.VIRTUAL, None, (), None, False, False),
    ("FOLDERID_ConnectionsFolder",
     "{6F0CD92B-2E97-45D1-88FF-B0D186B8DEDD}",
     "Network Connections", KnownFolderType.VIRTUAL, None,
     (Csidl.CONNECTIONS,), None, False, False),
    ("FOLDERID_Contacts", "{56784854-C6CB-462B-8169-88E350ACB882}",
     "Contacts", KnownFolderType.PERUSER, r"%USERPROFILE%\Contacts", (),
     None, False, False),
    ("FOLDERID_ControlPanelFolder",
     "{82A74AEB-AEB4-465C-A014-D097EE346D63}",
     "Control Panel", KnownFolderType.VIRTUAL, None, (Csidl.CONTROLS,),
     None, False, False),
    ("FOLDERID_Cookies", "{2B0F765D-C0E9-4171-908E-08A611B84FF6}",
     "Cookies", KnownFolderType.PERUSER,
     r"%APPDATA%\Microsoft\Windows\Cookies", (Csidl.COOKIES,), None,
     False, False),
    ("FOLDERID_Desktop", "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}",
     "Desktop", KnownFolderType.PERUSER, r"%USERPROFILE%\Desktop",
     (Csidl.DESKTOP, Csidl.DESKTOPDIRECTORY), None, False, False),
    ("FOLDERID_DeviceMetadataStore",
     "{5CE4A5E9-E4EB-479D-B89F-130C02886155}",
     "DeviceMetadataStore", KnownFolderType.COMMON,
     r"%ALLUSERSPROFILE%\Microsoft\Windows\DeviceMetadataStore", (), None,
     False, False),
    ("FOLDERID_Documents", "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}",
     "Documents", KnownFolderType.PERUSER, r"%USERPROFILE%\Documents",
     (Csidl.MYDOCUMENTS, Csidl.PERSONAL), None, False, False),
    ("FOLDERID_DocumentsLibrary",
     "{7B0DB17D-9CD2-4A93-9733-46CC89022E7C}",
     "Documents", KnownFolderType.PERUSER,
     r"%APPDATA%\Microsoft\Windows\Libraries\Documents.library-ms", (),
     None, False, False),
    ("FOLDERID_Downloads", "{374DE290-123F-4565-9164-39C4925E467B}",
     "Downloads", KnownFolderType.PERUSER, r"%USERPROFILE%\Downloads", (),
     None, False, False),
    ("FOLDERID_Favorites", "{1777F761-68AD-4D8A-87BD-30B759FA33DD}",
     "Favorites", KnownFolderType.PERUSER, r"%USERPROFILE%\Favorites",
     (Csidl.FAVORITES, Csidl.COMMON_FAVORITES), None, False, False),
    ("FOLDERID_Fonts", "{FD228CB7-AE11-4AE3-864C-16F3910AB8FE}",
     "Fonts", KnownFolderType.FIXED, r"%windir%\Fonts", (Csidl.FONTS,),
     None, False, False),
    ("FOLDERID_Games", "{CAC52C1A-B53D-4EDC-92D7-6B2E8AC19434}",
     "Games", KnownFolderType.VIRTUAL, None, (), None, True, False),
    ("FOLDERID_GameTasks", "{054FAE61-4DD8-4787-80B6-090220C4B700}",
     "GameExplorer", KnownFolderType.PERUSER,
     r"%LOCALAPPDATA%\Microsoft\Windows\GameExplorer", (), None, False, False),
    ("FOLDERID_History", "{D9DC8A3B-B784-432E-A781-5A1130A75963}",
     "History", KnownFolderType.PERUSER,
     r"%LOCALAPPDATA%\Microsoft\Windows\History", (Csidl.HISTORY,), None,
     False, False),
    ("FOLDERID_HomeGroup", "{52528A6B-B9E3-4ADD-B60D-588C2DBA842D}",
     "Homegroup", KnownFolderType.VIRTUAL, None, (), None, False, False),
    ("FOLDERID_HomeGroupCurrentUser",
     "{9B74B6A3-0DFD-4F11-9E78-5F7800F2E772}",
     "The user's username (%USERNAME%)", KnownFolderType.VIRTUAL, None, (),
     None, False, False),
    ("FOLDERID_ImplicitAppShortcuts",
     "{BCB5256F-79F6-4CEE-B725-DC34E402FD46}",
     "ImplicitAppShortcuts", KnownFolderType.PERUSER,
     r"%APPDATA%\Microsoft\Internet Explorer\Quick Launch\User Pinned\ImplicitAppShortcuts",
     (), None, False, False),
    ("FOLDERID_InternetCache", "{352481E8-33BE-4251-BA85-6007CAEDCF9D}",
     "Temporary Internet Files", KnownFolderType.PERUSER,
     r"%LOCALAPPDATA%\Microsoft\Windows\Temporary Internet Files",
     (Csidl.INTERNET_CACHE,), None, False, False),
    ("FOLDERID_InternetFolder",
     "{4D9F7874-4E0C-4904-967B-40B0D20C3E4B}",
     "The Internet", KnownFolderType.VIRTUAL, None, (Csidl.INTERNET,),
     None, False, False),
    ("FOLDERID_Libraries", "{1B3EA5DC-B587-4786-B4EF-BD1DC332AEAE}",
     "Libraries", KnownFolderType.PERUSER,
     r"%APPDATA%\Microsoft\Windows\Libraries", (), None, False, False),
    ("FOLDERID_Links", "{BFB9D5E0-C6A9-404C-B2B2-AE6DB6AF4968}",
     "Links", KnownFolderType.PERUSER, r"%USERPROFILE%\Links", (), None,
     False, False),
    ("FOLDERID_LocalAppData", "{F1B32785-6FBA-4FCF-9D55-7B8E7F157091}",
     "Local", KnownFolderType.PERUSER, r"%LOCALAPPDATA%",
     (Csidl.LOCAL_APPDATA,), None, False, False),
    ("FOLDERID_LocalAppDataLow", "{A520A1A4-1780-4FF6-BD18-167343C5AF16}",
     "LocalLow", KnownFolderType.PERUSER, r"%USERPROFILE%\AppData\LocalLow",
     (), None, False, False),
    ("FOLDERID_LocalizedResourcesDir",
     "{2A00375E-224C-49DE-B8D1-440DF7EF3DDC}",
     "Resources", KnownFolderType.FIXED, r"%windir%\resources\0409",
     (Csidl.RESOURCES_LOCALIZED,), None, False, False),
    ("FOLDERID_Music", "{4BD8D571-6D19-48D3-BE97-422220080E43}",
     "Music", KnownFolderType.PERUSER, r"%USERPROFILE%\Music",
     (Csidl.MYMUSIC,), None, False, False),
    ("FOLDERID_MusicLibrary", "{2112AB0A-C86A-4FFE-A368-0DE96E47012E}",
     "Music", KnownFolderType.PERUSER,
     r"%APPDATA%\Microsoft\Windows\Libraries\Music.library-ms", (), None,
     False, False),
    ("FOLDERID_NetHood", "{C5ABBF53-E17F-4121-8900-86626FC2C973}",
     "Network Shortcuts", KnownFolderType.PERUSER,
     r"%APPDATA%\Microsoft\Windows\Network Shortcuts", (Csidl.NETHOOD,),
     None, False, False),
    ("FOLDERID_NetworkFolder", "{D20BEEC4-5CA8-4905-AE3B-BF251EA09B53}",
     "Network", KnownFolderType.VIRTUAL, None,
     (Csidl.NETWORK, Csidl.COMPUTERSNEARME), None, False, False),
    ("FOLDERID_Objects3D", "{31C0DD25-9439-4F12-BF41-7FF4EDA38722}",
     "3D Objects", KnownFolderType.PERUSER, r"%USERPROFILE%\3D Objects", (),
     None, False, False),
    ("FOLDERID_OriginalImages",
     "{2C36C0AA-5812-4B87-BFD0-4CD0DFB19B39}",
     "Original Images", KnownFolderType.PERUSER,
     r"%LOCALAPPDATA%\Microsoft\Windows Photo Gallery\Original Images", (),
     None, False, False),
    ("FOLDERID_PhotoAlbums", "{69D2CF90-FC33-4FB7-9A0C-EBB0F0FCB43C}",
     "Slide Shows", KnownFolderType.PERUSER,
     r"%USERPROFILE%\Pictures\Slide Shows", (), None, False, False),
    ("FOLDERID_PicturesLibrary",
     "{A990AE9F-A03B-4E80-94BC-9912D7504104}",
     "Pictures", KnownFolderType.PERUSER,
     r"%APPDATA%\Microsoft\Windows\Libraries\Pictures.library-ms", (), None,
     False, False),
    ("FOLDERID_Pictures", "{33E28130-4E1E-4676-835A-98395C3BC3BB}",
     "Pictures", KnownFolderType.PERUSER, r"%USERPROFILE%\Pictures",
     (Csidl.MYPICTURES,), None, False, False),
    ("FOLDERID_Playlists", "{DE92C1C7-837F-4F69-A3BB-86E631204A23}",
     "Playlists", KnownFolderType.PERUSER, r"%USERPROFILE%\Music\Playlists",
     (), None, False, False),
    ("FOLDERID_PrintersFolder", "{76FC4E2D-D6AD-4519-A663-37BD56068185}",
     "Printers", KnownFolderType.VIRTUAL, None, (Csidl.PRINTERS,), None,
     False, False),
    ("FOLDERID_PrintHood", "{9274BD8D-CFD1-41C3-B35E-B13F55A758F4}",
     "Printer Shortcuts", KnownFolderType.PERUSER,
     r"%APPDATA%\Microsoft\Windows\Printer Shortcuts", (Csidl.PRINTHOOD,),
     None, False, False),
    ("FOLDERID_Profile", "{5E6C858F-0E22-4760-9AFE-EA3317B67173}",
     "The user's username (%USERNAME%)", KnownFolderType.FIXED,
     r"%USERPROFILE%", (Csidl.PROFILE,), None, False, False),
    ("FOLDERID_ProgramData", "{62AB5D82-FDC1-4DC3-A9DD-070D1D495D97}",
     "ProgramData", KnownFolderType.FIXED, r"%ALLUSERSPROFILE%",
     (Csidl.COMMON_APPDATA,), None, False, False),
    ("FOLDERID_ProgramFiles", "{905E63B6-C1BF-494E-B29C-65B732D3D21A}",
     "Program Files", KnownFolderType.FIXED, r"%ProgramFiles%",
     (Csidl.PROGRAM_FILES,), None, False, False),
    ("FOLDERID_ProgramFilesX64", "{6D809377-6AF0-444B-8957-A3773F02200E}",
     "Program Files", KnownFolderType.FIXED, r"%ProgramFiles%", (), None,
     False, True),
    ("FOLDERID_ProgramFilesX86", "{7C5A40EF-A0FB-4BFC-874A-C0F2E0B9FA8E}",
     "Program Files", KnownFolderType.FIXED, r"%ProgramFiles%",
     (Csidl.PROGRAM_FILESX86,), None, False, False),
    ("FOLDERID_ProgramFilesCommon",
     "{F7F1ED05-9F6D-47A2-AAAE-29D317C6F066}",
     "Common Files", KnownFolderType.FIXED, r"%ProgramFiles%\Common Files",
     (Csidl.PROGRAM_FILES_COMMON,), None, False, False),
    ("FOLDERID_ProgramFilesCommonX64",
     "{6365D5A7-0F0D-45E5-87F6-0DA56B6A4F7D}",
     "Common Files", KnownFolderType.FIXED, r"%ProgramFiles%\Common Files",
     (), None, False, True),
    ("FOLDERID_ProgramFilesCommonX86",
     "{DE974D24-D9C6-4D3E-BF91-F4455120B917}",
     "Common Files", KnownFolderType.FIXED, r"%ProgramFiles%\Common Files",
     (Csidl.PROGRAM_FILES_COMMONX86,), None, False, False),
    ("FOLDERID_Programs", "{A77F5D77-2E2B-44C3-A6A2-ABA601054A51}",
     "Programs", KnownFolderType.PERUSER,
     r"%APPDATA%\Microsoft\Windows\Start Menu\Programs", (Csidl.PROGRAMS,),
     None, False, False),
    ("FOLDERID_Public", "{DFDF76A2-C82A-4D63-906A-5644AC457385}",
     "Public", KnownFolderType.FIXED, r"%PUBLIC%", (), None, False, False),
    ("FOLDERID_PublicDesktop", "{C4AA340D-F20F-4863-AFEF-F87EF2E6BA25}",
     "Public Desktop", KnownFolderType.COMMON, r"%PUBLIC%\Desktop",
     (Csidl.COMMON_DESKTOPDIRECTORY,), None, False, False),
    ("FOLDERID_PublicDocuments",
     "{ED4824AF-DCE4-45A8-81E2-FC7965083634}",
     "Public Documents", KnownFolderType.COMMON, r"%PUBLIC%\Documents",
     (Csidl.COMMON_DOCUMENTS,), None, False, False),
    ("FOLDERID_PublicDownloads", "{3D644C9B-1FB8-4F30-9B45-F670235F79C0}",
     "Public Downloads", KnownFolderType.COMMON, r"%PUBLIC%\Downloads", (),
     None, False, False),
    ("FOLDERID_PublicGameTasks",
     "{DEBF2536-E1A8-4C59-B6A2-414586476AEA}",
     "GameExplorer", KnownFolderType.COMMON,
     r"%ALLUSERSPROFILE%\Microsoft\Windows\GameExplorer", (), None,
     False, False),
    ("FOLDERID_PublicLibraries",
     "{48DAF80B-E6CF-4F4E-B800-0E69D84EE384}",
     "Libraries", KnownFolderType.COMMON,
     r"%ALLUSERSPROFILE%\Microsoft\Windows\Libraries", (), None, False, False),
    ("FOLDERID_PublicMusic", "{3214FAB5-9757-4298-BB61-92A9DEAA44FF}",
     "Public Music", KnownFolderType.COMMON, r"%PUBLIC%\Music",
     (Csidl.COMMON_MUSIC,), None, False, False),
    ("FOLDERID_PublicPictures", "{B6EBFB86-6907-413C-9AF7-4FC2ABF07CC5}",
     "Public Pictures", KnownFolderType.COMMON, r"%PUBLIC%\Pictures",
     (Csidl.COMMON_PICTURES,), None, False, False),
    ("FOLDERID_PublicRingtones",
     "{E555AB60-153B-4D17-9F04-A5FE99FC15EC}",
     "Ringtones", KnownFolderType.COMMON,
     r"%ALLUSERSPROFILE%\Microsoft\Windows\Ringtones", (), None, False, False),
    ("FOLDERID_PublicUserTiles",
     "{0482AF6C-08F1-4C34-8C90-E17EC98B1E17}",
     "Public Account Pictures", KnownFolderType.COMMON,
     r"%PUBLIC%\AccountPictures", (), None, False, False),
    ("FOLDERID_PublicVideos", "{2400183A-6185-49FB-A2D8-4A392A602BA3}",
     "Public Videos", KnownFolderType.COMMON, r"%PUBLIC%\Videos",
     (Csidl.COMMON_VIDEO,), None, False, False),
    ("FOLDERID_QuickLaunch", "{52A4F021-7B75-48A9-9F6B-4B87A210BC8F}",
     "Quick Launch", KnownFolderType.PERUSER,
     r"%APPDATA%\Microsoft\Internet Explorer\Quick Launch", (), None,
     False, False),
    ("FOLDERID_Recent", "{AE50C081-EBD2-438A-8655-8A092E34987A}",
     "Recent Items", KnownFolderType.PERUSER,
     r"%APPDATA%\Microsoft\Windows\Recent", (Csidl.RECENT,), None,
     False, False),
    ("FOLDERID_RecordedTVLibrary",
     "{1A6FDBA2-F42D-4358-A798-B74D745926C5}",
     "Recorded TV", KnownFolderType.COMMON,
     r"%PUBLIC%\RecordedTV.library-ms", (), None, False, False),
    ("FOLDERID_RecycleBinFolder",
     "{B7534046-3ECB-4C18-BE4E-64CD4CB7D6AC}",
     "Recycle Bin", KnownFolderType.VIRTUAL, None, (Csidl.BITBUCKET,), None,
     False, False),
    ("FOLDERID_ResourceDir", "{8AD10C31-2ADB-4296-A8F7-E4701232C972}",
     "Resources", KnownFolderType.FIXED, r"%windir%\Resources",
     (Csidl.RESOURCES,), None, False, False),
    ("FOLDERID_Ringtones", "{C870044B-F49E-4126-A9C3-B52A1FF411E8}",
     "Ringtones", KnownFolderType.PERUSER,
     r"%LOCALAPPDATA%\Microsoft\Windows\Ringtones", (), None, False, False),
    ("FOLDERID_RoamingAppData",
     "{3EB685DB-65F9-4CF6-A03A-E3EF65729F3D}",
     "Roaming", KnownFolderType.PERUSER, r"%APPDATA%",
     (Csidl.APPDATA,), None, False, False),
    ("FOLDERID_RoamedTileImages",
     "{AAA8D5A5-F1D6-4259-BAA8-78E7EF60835E}",
     "RoamedTileImages", KnownFolderType.PERUSER,
     r"%LOCALAPPDATA%\Microsoft\Windows\RoamedTileImages", (), None,
     False, False),
    ("FOLDERID_RoamingTiles", "{00BCFC5A-ED94-4E48-96A1-3F6217F21990}",
     "RoamingTiles", KnownFolderType.PERUSER,
     r"%LOCALAPPDATA%\Microsoft\Windows\RoamingTiles", (), None, False, False),
    ("FOLDERID_SampleMusic", "{B250C668-F57D-4EE1-A63C-290EE7D1AA1F}",
     "Sample Music", KnownFolderType.COMMON, r"%PUBLIC%\Music\Sample Music",
     (), None, False, False),
    ("FOLDERID_SamplePictures",
     "{C4900540-2379-4C75-844B-64E6FAF8716B}",
     "Sample Pictures", KnownFolderType.COMMON,
     r"%PUBLIC%\Pictures\Sample Pictures", (), None, False, False),
    ("FOLDERID_SamplePlaylists",
     "{15CA69B3-30EE-49C1-ACE1-6B5EC372AFB5}",
     "Sample Playlists", KnownFolderType.COMMON,
     r"%PUBLIC%\Music\Sample Playlists", (), None, False, False),
    ("FOLDERID_SampleVideos", "{859EAD94-2E85-48AD-A71A-0969CB56A6CD}",
     "Sample Videos", KnownFolderType.COMMON,
     r"%PUBLIC%\Videos\Sample Videos", (), None, False, False),
    ("FOLDERID_SavedGames", "{4C5C32FF-BB9D-43B0-B5B4-2D72E54EAAA4}",
     "Saved Games", KnownFolderType.PERUSER, r"%USERPROFILE%\Saved Games",
     (), None, False, False),
    ("FOLDERID_SavedPictures", "{3B193882-D3AD-4EAB-965A-69829D1FB59F}",
     "Saved Pictures", KnownFolderType.PERUSER,
     r"%USERPROFILE%\Pictures\Saved Pictures", (), None, False, False),
    ("FOLDERID_SavedPicturesLibrary",
     "{E25B5812-BE88-4BD9-94B0-29233477B6C3}",
     "Saved Pictures Library", KnownFolderType.PERUSER,
     r"%APPDATA%\Microsoft\Windows\Libraries\SavedPictures.library-ms", (),
     None, False, False),
    ("FOLDERID_SavedSearches", "{7D1D3A04-DEBB-4115-95CF-2F29DA2920DA}",
     "Searches", KnownFolderType.PERUSER, r"%USERPROFILE%\Searches", (),
     None, False, False),
    ("FOLDERID_Screenshots", "{B7BEDE81-DF94-4682-A7D8-57A52620B86F}",
     "Screenshots", KnownFolderType.PERUSER,
     r"%USERPROFILE%\Pictures\Screenshots", (), None, False, False),
    ("FOLDERID_SEARCH_CSC", "{EE32E446-31CA-4ABA-814F-A5EBD2FD6D5E}",
     "Offline Files", KnownFolderType.VIRTUAL, None, (), None, False, False),
    ("FOLDERID_SearchHistory", "{0D4C3DB6-03A3-462F-A0E6-08924C41B5D4}",
     "History", KnownFolderType.PERUSER,
     r"%LOCALAPPDATA%\Microsoft\Windows\ConnectedSearch\History", (), None,
     False, False),
    ("FOLDERID_SearchHome", "{190337D1-B8CA-4121-A639-6D472D16972A}",
     "Search Results", KnownFolderType.VIRTUAL, None, (), None, False, False),
    ("FOLDERID_SEARCH_MAPI", "{98EC0E18-2098-4D44-8644-66979315A281}",
     "Microsoft Office Outlook", KnownFolderType.VIRTUAL, None, (), None,
     False, False),
    ("FOLDERID_SearchTemplates",
     "{7E636BFE-DFA9-4D5E-B456-D7B39851D8A9}",
     "Templates", KnownFolderType.PERUSER,
     r"%LOCALAPPDATA%\Microsoft\Windows\ConnectedSearch\Templates", (),
     None, False, False),
    ("FOLDERID_SendTo", "{8983036C-27C0-404B-8F08-102D10DCFD74}",
     "SendTo", KnownFolderType.PERUSER,
     r"%APPDATA%\Microsoft\Windows\SendTo", (Csidl.SENDTO,), None,
     False, False),
    ("FOLDERID_SidebarDefaultParts",
     "{7B396E54-9EC5-4300-BE0A-2482EBAE1A26}",
     "Gadgets", KnownFolderType.COMMON,
     r"%ProgramFiles%\Windows Sidebar\Gadgets", (), None, False, False),
    ("FOLDERID_SidebarParts", "{A75D362E-50FC-4FB7-AC2C-A8BEAA314493}",
     "Gadgets", KnownFolderType.PERUSER,
     r"%LOCALAPPDATA%\Microsoft\Windows\Sidebar\Gadgets", (), None,
     False, False),
    ("FOLDERID_SkyDrive", "{A52BBA46-E9E1-435F-B3D9-28DAA648C0F6}",
     "OneDrive", KnownFolderType.PERUSER, r"%USERPROFILE%\OneDrive", (),
     None, False, False),
    ("FOLDERID_SkyDriveCameraRoll",
     "{767E6811-49CB-4273-87C2-20F355E1085B}",
     "Camera Roll", KnownFolderType.PERUSER,
     r"%USERPROFILE%\OneDrive\Pictures\Camera Roll", (), None, False, False),
    ("FOLDERID_SkyDriveDocuments",
     "{24D89E24-2F19-4534-9DDE-6A6671FBB8FE}",
     "Documents", KnownFolderType.PERUSER,
     r"%USERPROFILE%\OneDrive\Documents", (), None, False, False),
    ("FOLDERID_SkyDrivePictures",
     "{339719B5-8C47-4894-94C2-D8F77ADD44A6}",
     "Pictures", KnownFolderType.PERUSER, r"%USERPROFILE%\OneDrive\Pictures",
     (), None, False, False),
    ("FOLDERID_StartMenu", "{625B53C3-AB48-4EC1-BA1F-A1EF4146FC19}",
     "Start Menu", KnownFolderType.PERUSER,
     r"%APPDATA%\Microsoft\Windows\Start Menu", (Csidl.STARTMENU,), None,
     False, False),
    ("FOLDERID_Startup", "{B97D20BB-F46A-4C97-BA10-5E3608430854}",
     "Startup", KnownFolderType.PERUSER,
     r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\StartUp",
     (Csidl.STARTUP, Csidl.ALTSTARTUP), None, False, False),
    ("FOLDERID_SyncManagerFolder",
     "{43668BF8-C14E-49B2-97C9-747784D784B7}",
     "Sync Center", KnownFolderType.VIRTUAL, None, (), None, False, False),
    ("FOLDERID_SyncResultsFolder",
     "{289A9A43-BE44-4057-A41B-587A76D7E7F9}",
     "Sync Results", KnownFolderType.VIRTUAL, None, (), None, False, False),
    ("FOLDERID_SyncSetupFolder",
     "{0F214138-B1D3-4A90-BBA9-27CBC0C5389A}",
     "Sync Setup", KnownFolderType.VIRTUAL, None, (), None, False, False),
    ("FOLDERID_System", "{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}",
     "System32", KnownFolderType.FIXED, r"%windir%\system32",
     (Csidl.SYSTEM,), None, False, False),
    ("FOLDERID_SystemX86", "{D65231B0-B2F1-4857-A4CE-A8E7C6EA7D27}",
     "System32", KnownFolderType.FIXED, r"%windir%\system32",
     (Csidl.SYSTEMX86,), None, False, False),
    ("FOLDERID_Templates", "{A63293E8-664E-48DB-A079-DF759E0509F7}",
     "Templates", KnownFolderType.PERUSER,
     r"%APPDATA%\Microsoft\Windows\Templates", (Csidl.TEMPLATES,), None,
     False, False),
    ("FOLDERID_UserPinned", "{9E3995AB-1F9C-4F13-B827-48B24B6C7174}",
     "User Pinned", KnownFolderType.PERUSER,
     r"%APPDATA%\Microsoft\Internet Explorer\Quick Launch\User Pinned", (),
     None, False, False),
    ("FOLDERID_UserProfiles", "{0762D272-C50A-4BB0-A382-697DCD729B80}",
     "Users", KnownFolderType.FIXED, r"%SystemDrive%\Users", (), None,
     False, False),
    ("FOLDERID_UserProgramFiles",
     "{5CD7AEE2-2219-4A67-B85D-6C9CE15660CB}",
     "Programs", KnownFolderType.PERUSER, r"%LOCALAPPDATA%\Programs", (),
     None, False, False),
    ("FOLDERID_UserProgramFilesCommon",
     "{BCBD3057-CA5C-4622-B42D-BC56DB0AE516}",
     "Programs", KnownFolderType.PERUSER, r"%LOCALAPPDATA%\Programs\Common",
     (), None, False, False),
    ("FOLDERID_UsersFiles", "{F3CE0F7C-4901-4ACC-8648-D5D44B04EF8F}",
     "The user's full name", KnownFolderType.VIRTUAL, None, (), None,
     False, False),
    ("FOLDERID_UsersLibraries",
     "{A302545D-DEFF-464B-ABE8-61C8648D939B}",
     "Libraries", KnownFolderType.VIRTUAL, None, (), None, False, False),
    ("FOLDERID_Videos", "{18989B1D-99B5-455B-841C-AB7C74E4DDFC}",
     "Videos", KnownFolderType.PERUSER, r"%USERPROFILE%\Videos",
     (Csidl.MYVIDEO,), None, False, False),
    ("FOLDERID_VideosLibrary",
     "{491E922F-5643-4AF4-A7EB-4E7A138D8174}",
     "Videos", KnownFolderType.PERUSER,
     r"%APPDATA%\Microsoft\Windows\Libraries\Videos.library-ms", (), None,
     False, False),
    ("FOLDERID_Windows", "{F38BF404-1D43-42F2-9305-67DE0B28FC23}",
     "Windows", KnownFolderType.FIXED, r"%windir%", (Csidl.WINDOWS,), None,
     False, False),
)


def _build_known_folders() -> Dict[str, KnownFolder]:
    out: Dict[str, KnownFolder] = {}
    for (name, guid, display, ftype, path, csidls, legacy,
         deprecated, x64_only) in _SPECS:
        out[name] = KnownFolder(
            name=name,
            guid=guid,
            display_name=display,
            folder_type=ftype,
            default_path=path,
            csidl_equivalent=csidls,
            legacy_default_path=legacy,
            deprecated=deprecated,
            x64_only=x64_only,
        )
    return out


#: All known folders, keyed by constant name (``FOLDERID_Desktop`` ...).
KNOWN_FOLDERS: Dict[str, KnownFolder] = _build_known_folders()

#: All known folders, keyed by canonical GUID.
KNOWN_FOLDERS_BY_GUID: Dict[str, KnownFolder] = {
    f.guid: f for f in KNOWN_FOLDERS.values()
}

#: CSIDL -> the KNOWNFOLDERID constant that replaced it.
CSIDL_TO_KNOWN_FOLDER: Dict[Csidl, str] = {}
for _kf in KNOWN_FOLDERS.values():
    for _c in _kf.csidl_equivalent:
        CSIDL_TO_KNOWN_FOLDER.setdefault(_c, _kf.name)


# ---------------------------------------------------------------------------
# CSIDL path templates
# ---------------------------------------------------------------------------

#: Default path template for every CSIDL that has a real file-system
#: location.  Virtual folders are absent -- they are resolved through
#: their KNOWNFOLDERID shell namespace path instead.
CSIDL_TEMPLATES: Dict[Csidl, str] = {
    Csidl.PROGRAMS: r"%APPDATA%\Microsoft\Windows\Start Menu\Programs",
    Csidl.PERSONAL: r"%USERPROFILE%\Documents",
    Csidl.FAVORITES: r"%USERPROFILE%\Favorites",
    Csidl.STARTUP: r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup",
    Csidl.RECENT: r"%APPDATA%\Microsoft\Windows\Recent",
    Csidl.SENDTO: r"%APPDATA%\Microsoft\Windows\SendTo",
    Csidl.STARTMENU: r"%APPDATA%\Microsoft\Windows\Start Menu",
    Csidl.MYMUSIC: r"%USERPROFILE%\Music",
    Csidl.MYVIDEO: r"%USERPROFILE%\Videos",
    Csidl.DESKTOPDIRECTORY: r"%USERPROFILE%\Desktop",
    Csidl.NETHOOD: r"%APPDATA%\Microsoft\Windows\Network Shortcuts",
    Csidl.FONTS: r"%windir%\Fonts",
    Csidl.TEMPLATES: r"%APPDATA%\Microsoft\Windows\Templates",
    Csidl.COMMON_STARTMENU: r"%ALLUSERSPROFILE%\Microsoft\Windows\Start Menu",
    Csidl.COMMON_PROGRAMS:
        r"%ALLUSERSPROFILE%\Microsoft\Windows\Start Menu\Programs",
    Csidl.COMMON_STARTUP:
        r"%ALLUSERSPROFILE%\Microsoft\Windows\Start Menu\Programs\Startup",
    Csidl.COMMON_DESKTOPDIRECTORY: r"%PUBLIC%\Desktop",
    Csidl.APPDATA: r"%APPDATA%",
    Csidl.PRINTHOOD: r"%APPDATA%\Microsoft\Windows\Printer Shortcuts",
    Csidl.LOCAL_APPDATA: r"%LOCALAPPDATA%",
    Csidl.ALTSTARTUP:
        r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\StartUp",
    Csidl.COMMON_ALTSTARTUP:
        r"%ALLUSERSPROFILE%\Microsoft\Windows\Start Menu\Programs\StartUp",
    Csidl.COMMON_FAVORITES: r"%PUBLIC%\Favorites",
    Csidl.INTERNET_CACHE:
        r"%LOCALAPPDATA%\Microsoft\Windows\Temporary Internet Files",
    Csidl.COOKIES: r"%APPDATA%\Microsoft\Windows\Cookies",
    Csidl.HISTORY: r"%LOCALAPPDATA%\Microsoft\Windows\History",
    Csidl.COMMON_APPDATA: r"%ProgramData%",
    Csidl.WINDOWS: r"%windir%",
    Csidl.SYSTEM: r"%windir%\system32",
    Csidl.PROGRAM_FILES: r"%ProgramFiles%",
    Csidl.MYPICTURES: r"%USERPROFILE%\Pictures",
    Csidl.PROFILE: r"%USERPROFILE%",
    Csidl.SYSTEMX86: r"%windir%\syswow64",
    Csidl.PROGRAM_FILESX86: r"%ProgramFiles(x86)%",
    Csidl.PROGRAM_FILES_COMMON: r"%ProgramFiles%\Common Files",
    Csidl.PROGRAM_FILES_COMMONX86: r"%ProgramFiles(x86)%\Common Files",
    Csidl.COMMON_TEMPLATES: r"%ALLUSERSPROFILE%\Microsoft\Windows\Templates",
    Csidl.COMMON_DOCUMENTS: r"%PUBLIC%\Documents",
    Csidl.COMMON_ADMINTOOLS:
        r"%ALLUSERSPROFILE%\Microsoft\Windows\Start Menu\Programs\Administrative Tools",
    Csidl.ADMINTOOLS:
        r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Administrative Tools",
    Csidl.COMMON_MUSIC: r"%PUBLIC%\Music",
    Csidl.COMMON_PICTURES: r"%PUBLIC%\Pictures",
    Csidl.COMMON_VIDEO: r"%PUBLIC%\Videos",
    Csidl.RESOURCES: r"%windir%\Resources",
    Csidl.RESOURCES_LOCALIZED: r"%windir%\resources\0409",
    Csidl.COMMON_OEM_LINKS: r"%ALLUSERSPROFILE%\OEM Links",
    Csidl.CDBURN_AREA: r"%LOCALAPPDATA%\Microsoft\Windows\Burn\Burn",
}

#: The CSIDLs that identify a *shell namespace* object rather than an
#: ordinary directory.  They are routed through the KNOWNFOLDERID
#: catalogue; whether the result is a ``::{GUID}`` namespace path or a
#: real directory depends on the folder they map to -- ``CSIDL_DESKTOP``
#: maps to ``FOLDERID_Desktop``, which *is* the physical Desktop folder,
#: while ``CSIDL_BITBUCKET`` maps to the virtual Recycle Bin.
SHELL_NAMESPACE_CSIDLS = frozenset({
    Csidl.DESKTOP, Csidl.INTERNET, Csidl.CONTROLS, Csidl.PRINTERS,
    Csidl.BITBUCKET, Csidl.DRIVES, Csidl.NETWORK, Csidl.CONNECTIONS,
    Csidl.COMPUTERSNEARME,
})


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def _expand(template: str, block=None) -> str:
    """Expand a ``%VAR%`` path template against an environment block."""
    if not template:
        return template
    from .environment import ExpandEnvironmentStringsA   # local: avoid cycle
    return ExpandEnvironmentStringsA(template, block)


def _known_folder(name: str) -> KnownFolder:
    """Look a folder up by constant name or GUID (case-insensitive)."""
    if name in KNOWN_FOLDERS:
        return KNOWN_FOLDERS[name]
    upper = name.upper()
    for kf in KNOWN_FOLDERS.values():
        if kf.name.upper() == upper:
            return kf
    bare = upper.strip("{}")
    for kf in KNOWN_FOLDERS.values():
        if kf.guid.strip("{}").upper() == bare:
            return kf
    raise KeyError(f"unknown known folder: {name!r}")


def known_folder(name: str) -> KnownFolder:
    """Public wrapper: resolve a constant name or GUID to a record."""
    return _known_folder(name)


def list_known_folders(folder_type: Optional[KnownFolderType] = None
                       ) -> List[KnownFolder]:
    """Return every known folder, optionally filtered by category."""
    items = list(KNOWN_FOLDERS.values())
    if folder_type is not None:
        items = [k for k in items if k.folder_type is folder_type]
    return sorted(items, key=lambda k: k.name)


def _program_files_template(app_is_32bit: bool, os_is_64bit: bool) -> str:
    """``FOLDERID_ProgramFiles`` default path per the redirection matrix."""
    if os_is_64bit and app_is_32bit:
        return r"%SystemDrive%\Program Files (x86)"
    return r"%SystemDrive%\Program Files"


def _program_files_common_template(app_is_32bit: bool,
                                   os_is_64bit: bool) -> str:
    """``FOLDERID_ProgramFilesCommon`` default path."""
    if os_is_64bit and app_is_32bit:
        return r"%ProgramFiles(x86)%\Common Files"
    return r"%ProgramFiles%\Common Files"


def resolve_known_folder(name: str,
                         *,
                         app_is_32bit: bool = False,
                         os_is_64bit: bool = True,
                         block=None) -> str:
    """Resolve a ``KNOWNFOLDERID`` to its path.

    Parameters
    ----------
    name:
        The constant name (``FOLDERID_Desktop``) or the GUID string.
    app_is_32bit:
        ``True`` when the calling process is a 32-bit application.  This
        is what selects ``Program Files (x86)`` on a 64-bit OS.
    os_is_64bit:
        ``True`` on a 64-bit Windows installation.
    block:
        Optional environment block used to expand the path template.

    Returns
    -------
    str
        The folder path, or the ``::{GUID}`` shell namespace path for
        virtual folders.

    Raises
    ------
    KeyError
        If the folder name/GUID is unknown.
    ValueError
        If the folder is x64-only but the caller/OS combination cannot
        support it (``FOLDERID_ProgramFilesX64``).
    """
    kf = _known_folder(name)

    if kf.x64_only and not (os_is_64bit and not app_is_32bit):
        raise ValueError(
            f"{kf.name} is not supported for a "
            f"{'32-bit' if app_is_32bit else '64-bit'} application on a "
            f"{'32-bit' if not os_is_64bit else '64-bit'} OS"
        )

    if kf.is_virtual:
        return kf.shell_path

    template = kf.default_path or ""
    if kf.name == "FOLDERID_ProgramFiles":
        template = _program_files_template(app_is_32bit, os_is_64bit)
    elif kf.name == "FOLDERID_ProgramFilesX86":
        template = (r"%SystemDrive%\Program Files (x86)" if os_is_64bit
                    else r"%SystemDrive%\Program Files")
    elif kf.name == "FOLDERID_ProgramFilesCommon":
        template = _program_files_common_template(app_is_32bit, os_is_64bit)
    elif kf.name == "FOLDERID_ProgramFilesCommonX86":
        template = (r"%ProgramFiles(x86)%\Common Files" if os_is_64bit
                    else r"%ProgramFiles%\Common Files")
    elif kf.name == "FOLDERID_System":
        template = r"%windir%\system32"
    elif kf.name == "FOLDERID_SystemX86":
        template = (r"%windir%\syswow64" if os_is_64bit
                    else r"%windir%\system32")

    return _expand(template, block)


def resolve_csidl(csidl: int,
                  *,
                  app_is_32bit: bool = False,
                  os_is_64bit: bool = True,
                  block=None) -> str:
    """Resolve a legacy ``CSIDL`` value to its path.

    Virtual CSIDLs resolve through their KNOWNFOLDERID shell namespace
    path; physical ones through the CSIDL default-path template.
    """
    try:
        value = Csidl(int(csidl) & 0xFFFF)
    except ValueError as exc:
        raise KeyError(f"unknown CSIDL: {csidl!r}") from exc

    if value in SHELL_NAMESPACE_CSIDLS:
        kf_name = CSIDL_TO_KNOWN_FOLDER.get(value)
        if kf_name:
            return resolve_known_folder(kf_name, app_is_32bit=app_is_32bit,
                                        os_is_64bit=os_is_64bit, block=block)

    template = CSIDL_TEMPLATES.get(value)
    if template is None:
        raise KeyError(f"CSIDL {value.name} has no resolvable path")
    if value is Csidl.SYSTEMX86 and not os_is_64bit:
        template = r"%windir%\system32"
    elif value is Csidl.PROGRAM_FILESX86 and not os_is_64bit:
        template = r"%ProgramFiles%"
    elif value is Csidl.PROGRAM_FILES_COMMONX86 and not os_is_64bit:
        template = r"%ProgramFiles%\Common Files"
    return _expand(template, block)


def csidl_to_known_folder(csidl: int) -> Optional[str]:
    """Return the KNOWNFOLDERID constant name that replaced ``csidl``."""
    try:
        value = Csidl(int(csidl) & 0xFFFF)
    except ValueError:
        return None
    return CSIDL_TO_KNOWN_FOLDER.get(value)


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    # 1. Every CSIDL value is unique apart from the documented alias.
    names = [c.name for c in Csidl]
    if len(names) != len(set(names)):
        return False

    # 2. The catalogue is complete and internally consistent.
    if len(KNOWN_FOLDERS) < 100:
        log.debug("known folder catalogue is short: %d", len(KNOWN_FOLDERS))
        return False
    for kf in KNOWN_FOLDERS.values():
        if not kf.guid.startswith("{") or not kf.guid.endswith("}"):
            return False
        if kf.folder_type is KnownFolderType.VIRTUAL and kf.default_path:
            return False
        if kf.folder_type is not KnownFolderType.VIRTUAL and not kf.default_path:
            return False

    # 3. GUID index round-trips.
    desktop = KNOWN_FOLDERS["FOLDERID_Desktop"]
    if KNOWN_FOLDERS_BY_GUID[desktop.guid] is not desktop:
        return False

    # 4. CSIDL -> KNOWNFOLDERID mapping.
    if csidl_to_known_folder(Csidl.APPDATA) != "FOLDERID_RoamingAppData":
        return False
    if csidl_to_known_folder(Csidl.PERSONAL) != "FOLDERID_Documents":
        return False

    # 5. Physical folder resolution expands the template.
    path = resolve_known_folder("FOLDERID_Desktop")
    if not path.lower().endswith(r"\desktop"):
        log.debug("desktop path = %r", path)
        return False

    # 6. Virtual folder resolves to a shell namespace path.
    virt = resolve_known_folder("FOLDERID_RecycleBinFolder")
    if not virt.startswith("::{") or not virt.endswith("}"):
        return False

    # 7. The 32/64 redirection matrix.
    p64 = resolve_known_folder("FOLDERID_ProgramFiles", app_is_32bit=False,
                               os_is_64bit=True)
    p32 = resolve_known_folder("FOLDERID_ProgramFiles", app_is_32bit=True,
                               os_is_64bit=True)
    if "Program Files (x86)" not in p32:
        log.debug("32-bit Program Files = %r", p32)
        return False
    if "(x86)" in p64:
        log.debug("64-bit Program Files = %r", p64)
        return False
    sys32 = resolve_known_folder("FOLDERID_SystemX86", app_is_32bit=False,
                                 os_is_64bit=True)
    if not sys32.lower().endswith(r"\syswow64"):
        log.debug("SystemX86 = %r", sys32)
        return False

    # 8. x64-only folders reject invalid callers.
    try:
        resolve_known_folder("FOLDERID_ProgramFilesX64", app_is_32bit=True,
                             os_is_64bit=True)
    except ValueError:
        pass
    else:
        return False

    # 9. Legacy CSIDL resolution.
    prof = resolve_csidl(Csidl.PROFILE)
    if not prof:
        return False
    bin = resolve_csidl(Csidl.BITBUCKET)
    if not bin.startswith("::"):
        return False

    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
