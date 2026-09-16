# UmerOS /compatibility

A **pure-Python** Windows compatibility layer for UmerOS.

Inspired by ReactOS and Wine, the `compatibility` package can parse PE
binaries from Windows NT 4 through Windows 11, decode the Windows
registry, stub the most commonly-used Win32 / NT APIs, and audit / load
PE images into a sandboxed UmerOS process — all without compiling a
single line of C, and without depending on Wine.

```
┌──────────────────────────────────────────────────────────────────┐
│  application.exe (NT 4 → Win11, x86 / x64 / ARM)                 │
└──────────────────────────────────────────────────────────────────┘
                            │ Win32 imports
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│  wine_shim.WineShim      (high-level launcher)                   │
│  dll_loader.DllLoader    (IAT resolver)                          │
└──────────────────────────────────────────────────────────────────┘
                            │
   ┌────────────────────────┼───────────────────────────────┐
   ▼                        ▼                               ▼
PE parser              Registry                Win32 / NT API stubs
mz_loader              registry_hive           win_kernel32
ne_loader              registry_view           win_user32
pe_loader              registry_paths          win_gdi32
pe_imports                                      win_advapi32
pe_exports                                      win_ntdll
pe_relocations                                  service_manager
pe_tls                                          environment
pe_resources                                    com_support
                                                file_attrs
                            │
                            ▼
                   Foundation helpers
                   winerror  ntstatus  win_guid
                   win_sid   win_strings  win_path
```

The package is intentionally conservative: the goal is to *satisfy the
loader* and *audit the IAT*, not to run arbitrary x86 code on a non-x86
host. Every public surface is also exposed as a CLI for scripting.

---

## Table of contents

1. [Quick start](#quick-start)
2. [CLI](#cli)
3. [Module reference](#module-reference)
   * [PE parsers](#pe-parsers)
   * [Registry](#registry)
   * [Foundation helpers](#foundation-helpers)
   * [Win32 / NT stubs](#win32--nt-stubs)
   * [Higher-level helpers](#higher-level-helpers)
   * [Loader / shim](#loader--shim)
   * [Stop-gap containers](#stop-gap-containers)
4. [Conventions](#conventions)
5. [Testing](#testing)
6. [Compatibility matrix](#compatibility-matrix)
7. [References](#references)
8. [Licence](#licence)

---

## Quick start

```python
from compatibility import wine_shim, PeFile

shim = wine_shim.WineShim()
result = shim.launch("path/to/Program.exe")

print(f"machine:    {hex(result.pe.machine)}")
print(f"subsystem:  {result.pe.subsystem_name}")
print(f"is_loadable:{result.is_loadable}")
print(f"missing:    {[f'{m.dll_name}!{m.symbol}'
                   for m in result.loaded.missing_imports()]}")
```

Audit a single binary without invoking the loader:

```python
from compatibility.pe_loader import PeFile
pe = PeFile.from_path("C:/Windows/System32/notepad.exe")
print(pe.entry_point_rva, pe.image_base, len(pe.sections))
```

---

## CLI

```text
python -m compatibility selftest   # run every module's _selftest()
python -m compatibility info       # package version + public API surface
python -m compatibility audit <path-to.exe>
python -m compatibility run  <path-to.exe> [--dry-run]
```

| Command   | Purpose                                                   |
| --------- | --------------------------------------------------------- |
| `selftest`| Run every sub-module's `_selftest()`. Exit 0 = pass.      |
| `info`    | Print the package version and the list of public names.   |
| `audit`   | Read `path` as PE/NE/MZ and emit a JSON summary.          |
| `run`     | Launch via `WineShim`. Audit-only by default (no x86 exec).|

The `audit` command prints a JSON object shaped like:

```json
{
  "path": "notepad.exe",
  "machine": "0x14c",
  "entry_rva": "0x1000",
  "subsystem": "WINDOWS_CUI",
  "image_base": "0x400000",
  "n_imports": 0,
  "n_resolved": 0,
  "missing": [],
  "is_loadable": true
}
```

---

## Module reference

### PE parsers

`compatibility.pe_loader` is the entry point. It returns a `PeFile`
dataclass with header, optional-header, sections, data-directories and
subsystem lookup. The other parsers (`pe_imports`, `pe_exports`,
`pe_relocations`, `pe_tls`, `pe_resources`) are designed to be called
with a `PeFile` so they can re-use the `rva_to_offset` table.

```python
from compatibility.pe_loader import PeFile
from compatibility.pe_imports import parse_imports

pe = PeFile.from_path("app.exe")
for entry in parse_imports(pe):
    print(entry.dll_name, [f.name for f in entry.functions])
```

`mz_loader.parse_mz_header` parses the legacy DOS stub, `ne_loader`
parses 16-bit NE binaries (Windows 3.x), `pe_loader` parses PE32 / PE32+
(Windows NT 4 → 11).

### Registry

* `registry_hive.RegType` — REG_SZ, REG_DWORD, REG_BINARY, REG_MULTI_SZ,
  REG_EXPAND_SZ.
* `registry_hive.RegistryHive` — read a real REGF hive from disk.
* `registry_view.InMemoryRegistry` — Python-only in-memory registry,
  used by `wine_shim` and the loader's audit step.
* `registry_paths` — maps the well-known hive paths
  (`HKLM\SOFTWARE`, `HKCU\Control Panel\Desktop`, …) onto POSIX paths
  under a `/compat` root.

### Foundation helpers

| Module        | What it provides                                           |
| ------------- | ---------------------------------------------------------- |
| `winerror`    | Win32 error codes + HRESULT formatting.                    |
| `ntstatus`    | NTSTATUS codes, severity bits, NTSTATUS → Win32 mapping.    |
| `win_guid`    | 128-bit GUID with mixed-endian bridge to `uuid.UUID`.      |
| `win_sid`     | Security Identifier codec + well-known SID database.       |
| `win_strings` | `UNICODE_STRING` (length + max + buffer) + UTF-16LE codec. |
| `win_path`    | DOS → POSIX mapper (drive letter, UNC, drive-relative).    |

### Win32 / NT stubs

The `EXPORTS` dict on every `win_<name>.py` module is the contract used
by `dll_loader.HOST_LIBRARIES` to resolve IAT entries:

```python
from compatibility.dll_loader import HOST_LIBRARIES
from compatibility.win_kernel32 import GetTickCount
assert HOST_LIBRARIES["KERNEL32.DLL"]["GetTickCount"] is GetTickCount
```

The most commonly-resolved exports are:

* `KERNEL32.DLL` — file I/O, process/thread, error, modules.
* `USER32.DLL`   — message pump, window class, dispatch.
* `GDI32.DLL`    — DC, pen, brush, region.
* `ADVAPI32.DLL` — registry client, SCM (re-exports
  `service_manager.EXPORTS`), event log stub.
* `NTDLL.DLL`    — `NtCreateFile`, `NtClose`, NTSTATUS returns.

### Higher-level helpers

* `service_manager` — OpenSCManager, CreateService, StartService,
  ControlService, DeleteService, EnumServicesStatus, QueryServiceStatus
  — all backed by an in-memory service database. Useful for installers.
* `environment` — case-insensitive `EnvironmentBlock`, registry-backed
  user/system env, `ExpandEnvironmentStringsA`, double-null-terminated
  serialisation.
* `com_support` — `CoInitializeEx`, `CoUninitialize`, `CoCreateInstance`,
  refcounted `ComObjectBase`, `IUnknown` / `IDispatch` IIDs,
  `ClassFactory` registry. No marshaling.
* `file_attrs` — `GetFileAttributesA`, `SetFileAttributesA`,
  `GetFileAttributesExA`. Bits that have no POSIX meaning
  (`HIDDEN`, `SYSTEM`, `ENCRYPTED`, `NOT_CONTENT_INDEXED`) are kept in a
  sidecar `<name>.attr` file so they round-trip across calls.

### Loader / shim

* `dll_loader.DllLoader.resolve(pe)` — pure-Python IAT resolver. Walks
  every import descriptor, looks the symbol up in `HOST_LIBRARIES`, and
  groups the result into a `ResolvedImport` list.
* `wine_shim.WineShim.launch(path)` — opens the file, parses the PE,
  asks the loader to resolve imports, and returns a `LaunchResult`
  detailing what the host could satisfy.

The loader **does not** map sections into memory, fix up relocations or
actually execute x86 instructions. Its purpose is to *audit* an image
and report what's missing.

### Stop-gap containers

These predate the current scope but remain in the package:

* `container.ZeroTrustContainer` — fail-closed sandbox (H51).
* `container_engine.ContainerEngine` — launch sandboxed binaries.
* `syscall_shim.SyscallShim` — intercept and redirect host syscalls.

They are unchanged from earlier revisions and continue to be the
Linux / Android side of the compatibility story.

---

## Conventions

* **Pure Python only.** No C extensions, no `ctypes`, no native code.
* **Cross-platform.** The package runs on Windows and POSIX; POSIX-only
  imports are guarded with `if TYPE_CHECKING`.
* **Apache-2.0 / GPL-3.0 headers.** Every module starts with a license
  block referencing `LICENSE` and `README`.
* **`_selftest()` everywhere.** Each module ships with a `_selftest()`
  that exercises its public API; `compatibility.selftest()` runs them
  all and is wired into `__main__.py`.
* **`dataclass` + `Enum` + type hints.** Public types use
  `dataclass(frozen=True, order=True)` where appropriate; numeric
  enumerations use `IntEnum` so they compare against their int values
  (matters for IAT auditors).
* **Forward-slash output.** All path-mapping results are normalised to
  `/` so the package is portable across `\` and `/` hosts.

---

## Testing

The package ships with `tests/test_compatibility.py` (34 cases). Run it
with stdlib `unittest`:

```powershell
python -m unittest tests.test_compatibility -v
```

Each case targets one module:

| Test class                  | What it covers                                          |
| --------------------------- | ------------------------------------------------------- |
| `TestMzHeader`              | MZ stub parsing.                                         |
| `TestNeHeader`              | NE header parsing.                                      |
| `TestPeFile`                | PE32/PE32+ loading, section lookup, RVA→offset.         |
| `TestPeDirectoryParsers`    | Empty directories on a no-op image.                      |
| `TestErrorCodes`            | Win32 error / HRESULT / NTSTATUS formatting.             |
| `TestGuid`                  | Round-trip, mixed-endian, uuid bridge.                   |
| `TestSid`                   | Round-trip + well-known SID database.                    |
| `TestDosPath`               | Drive, UNC, drive-relative path mapping.                 |
| `TestUnicodeString`         | UTF-16LE codec + UNICODE_STRING dataclass.               |
| `TestRegistry`              | In-memory registry + hive paths.                         |
| `TestKernel32`              | Last error + file I/O round-trip.                        |
| `TestUser32`                | Window class + message pump.                             |
| `TestGdi32`                 | DC / pen object lifecycle.                               |
| `TestAdvApi32`              | Registry client stub.                                    |
| `TestNtdll`                 | NtCreateFile + NtClose.                                  |
| `TestDllLoader`             | IAT resolution + host library export table.              |
| `TestWineShim`              | High-level launcher on a synthetic PE.                   |

---

## Compatibility matrix

| Windows version | PE format | Parsed | Loaded | Notes                                    |
| --------------- | --------- | :----: | :----: | ---------------------------------------- |
| Windows 3.x     | NE        | ✅     | ⚠      | Header parsed; not loaded.               |
| Windows NT 4    | PE32      | ✅     | ✅     | Full IAT resolution.                     |
| Windows 2000    | PE32      | ✅     | ✅     | Uses PE32.                               |
| Windows XP      | PE32      | ✅     | ✅     |                                          |
| Windows Vista   | PE32      | ✅     | ✅     |                                          |
| Windows 7       | PE32/PE32+| ✅     | ✅     | PE32+ detected automatically.            |
| Windows 8       | PE32/PE32+| ✅     | ✅     |                                          |
| Windows 10      | PE32/PE32+| ✅     | ✅     |                                          |
| Windows 11      | PE32/PE32+| ✅     | ✅     |                                          |

| Architecture   | Parsed | Loaded | Notes                                  |
| -------------- | :----: | :----: | -------------------------------------- |
| i386 (x86)     | ✅     | ✅     | Default machine in the synthetic PE.   |
| AMD64 (x64)    | ✅     | ✅     |                                          |
| ARM             | ✅     | ✅     |                                          |
| ARM64           | ✅     | ✅     |                                          |
| IA-64           | ✅     | ⚠      | Headers parsed; thunk size differs.    |

---

## References

* **Microsoft Learn** — File Attribute Constants,
  Win32 Error Codes, NTSTATUS Values, Registry Element Size Limits.
* **PE / COFF Specification** — `Microsoft PE/COFF v8.3` (revision 8.3
  contains the most authoritative description of the optional header
  data directories used here).

---

## Licence

GPL-3.0.  See `LICENSE` for the full text.
