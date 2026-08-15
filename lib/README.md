# Umer OS /lib

The package is split into 21 specialised modules
that each model one slice of the FHS spec, plus a unified CLI and
a one-shot summary module.

## What is in here

```
lib/
├── __init__.py            # public re-exports for every manager
├── __main__.py            # python -m lib CLI
├── libinfo.py             # one-shot /lib summary (NEW)
├── arch.py                # /lib/<machine-architecture> layout
├── dynamic_linker.py      # ld.so.conf + ld.so.cache (binary format)
├── elf_parser.py          # real ELF parser (NEEDED + SONAME)
├── essential_libs.py      # libc / ld / libm / libpthread / ...
├── fhs.py                 # TLDP/FHS audit + bootstrap
├── firmware.py            # /lib/firmware blobs
├── iconv.py               # /usr/lib/gconv character set modules
├── iptables_libs.py       # /lib/iptables extensions
├── kbd.py                 # /lib/kbd keymaps / fonts
├── kernel_modules.py     # /lib/modules/<ver> + depmod + modprobe
├── ldd.py                 # ldd-style dependency tree
├── library_manager.py     # LibraryManager + symlink maintenance
├── multiarch.py           # /lib<qual> (32 / 64 / x32 / sframe) policy
├── oss.py                 # /lib/oss Open Sound System drivers
├── security.py            # /lib/security PAM modules
├── ssl_libs.py            # SSL/TLS library stubs
├── tmpfiles.py            # /usr/lib/tmpfiles.d configuration
├── usr_include.py         # /usr/include header catalogue
├── usr_lib.py             # /usr/lib (gconv, charmap, libexec)
├── var_lib.py             # /var/lib (alternatives, per-app state)
└── README.md              # this file
```

## TLDP coverage map

| TLDP requirement | Module | Class / function |
|---|---|---|
| Shared libraries needed by /bin and /sbin | `essential_libs.py` | `EssentialLibraryManager`, `ESSENTIAL_LIBRARIES` |
| `libc.so.*` and `ld*` patterns (optional) | `essential_libs.py` | `EssentialLibraryManager.get_required_libs()` |
| `/lib/cpp` reference | `dynamic_linker.py` | `LibQualifierManager.ensure_cpp_reference()` |
| `ldconfig` (binary cache writer) | `dynamic_linker.py` | `LdSoCache`, `DynamicLinkerManager.ldconfig()` |
| `/etc/ld.so.conf` parser (incl. `include`, `trust`, `hwcap`, `exclude`) | `dynamic_linker.py` | `LdSoConfParser` |
| `/etc/ld.so.cache` writer/reader | `dynamic_linker.py` | `LdSoCache.to_bytes`, `LdSoCache.from_file` |
| `/lib<qual>` (32 / 64 / x32 / sframe) | `multiarch.py` | `MultiarchManager`, `LibQualifierManager` |
| `/lib/'machine-architecture'` | `arch.py` | `ArchLibraryManager`, `ARCHITECTURES` |
| `/lib/iptables` | `iptables_libs.py` | `IptablesLibraryManager` |
| `/lib/kbd` | `kbd.py` | `KbdManager` |
| `/lib/modules/'kernel-version'` | `kernel_modules.py` | `KernelModuleManager` |
| `modules.dep` (built by depmod) | `kernel_modules.py` | `KernelModuleManager.depmod()` |
| `modules.alias` | `kernel_modules.py` | `ModuleDependency.aliases` |
| `modules.softdep` | `kernel_modules.py` | `ModuleDependency.soft` |
| `modules.symbols` | `kernel_modules.py` | `ModuleDependency.symbols` |
| `isapnpmap.dep` | `kernel_modules.py` + `fhs.py` | `KernelModuleManager.ensure_isapnpmap()` |
| `pcimap` | `kernel_modules.py` | `KernelModuleManager.ensure_pcimap()` |
| `usbmap` | `kernel_modules.py` | `KernelModuleManager.ensure_usbmap()` |
| `kernel/build` symlink to `/usr/src/<ver>` | `kernel_modules.py` | `KernelModuleManager.ensure_build_symlink()` |
| `/lib/oss` | `oss.py` | `OssManager` |
| `/lib/security` (PAM) | `security.py` | `PamLibraryManager` |
| `ldd` (library dependency tracer) | `ldd.py` | `Ldd` |
| `/var/lib` (per-host state) | `var_lib.py` | `VarLibManager` |
| `/var/lib/alternatives` | `var_lib.py` | `AlternativesManager` |
| `/usr/lib` (gconv, charmap, libexec) | `usr_lib.py` | `UsrLibManager`, `GconvManager`, `CharmapManager`, `LibexecManager` |
| `/usr/include` | `usr_include.py` | `UsrIncludeManager` |

## CLI

```powershell
python -m lib selftest                # run every module's self-test
python -m lib info                    # one-shot /lib summary
python -m lib info F:\lib            # same, for a custom path
python -m lib audit                   # run the FHS audit
python -m lib ldd <elf>               # trace shared library deps
python -m lib ldconfig                # rebuild /etc/ld.so.cache
python -m lib depmod                  # regenerate modules.dep
python -m lib modprobe <name>         # load a kernel module
python -m lib modprobe <name> -r      # remove a kernel module
python -m lib lsmod                   # list loaded modules
python -m lib cpplink                 # ensure /lib/cpp references cpp
python -m lib list                    # list all essential libraries
python -m lib help                    # help text
```

## Programmatic use

```python
import lib
from lib.libinfo import lib_summary

# The headline numbers in a one-liner.
info = lib_summary(lib_path="/lib")
print(info.render_table())

# Run the FHS audit.
mgr = lib.LibHierarchyManager(root="/")
report = mgr.audit()
if not report.ok:
    for issue in report.errors:
        print(issue.to_dict())

# Inspect an ELF binary.
from lib.elf_parser import ElfParser
info = ElfParser().parse("/bin/ls")
print(f"  {info.soname}  ({info.bit_width}-bit {info.machine_name})")
print(f"  NEEDED: {info.needed}")

# Trace its dependencies like ldd(1) does.
from lib.ldd import Ldd
tree = Ldd().trace("/bin/ls")
print(Ldd().format_tree(tree))

# Bootstrap a brand-new FHS-compliant /lib tree.
mgr = lib.LibHierarchyManager(root="/var/empty-fs")
stats = mgr.bootstrap(prefer_symlink=True)
print(stats)        # {"essential_libraries": 17, "module_maps": 4, ...}
```

## What's new in this pass

* **`libinfo.py`** - one-shot `lib_summary()` that returns a
  `LibSummary` dataclass with everything the kernel/operator
  needs at a glance.
* **`__main__.py`** - `python -m lib` CLI with 11 sub-commands.
* **`_selftest()` helpers** in `library_manager.py`,
  `essential_libs.py`, `dynamic_linker.py`, `elf_parser.py`,
  `ldd.py`, and `libinfo.py` so the unified `python -m lib
  selftest` covers every layer.
* **`tests/test_lib_cli.py`** - 26 unit tests covering the
  new module, the new CLI, and the new selftests.
* **`tests/run_lib_tests.py`** - a one-shot runner that picks
  up both `test_lib_cli.py` and the pre-existing
  `test_lib_fhs.py`.

## License

Apache 2.0 - same as the rest of Umer OS.
