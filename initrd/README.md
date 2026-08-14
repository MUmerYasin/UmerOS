# Umer OS /initrd

A pure-Python implementation of `/initrd` runtime, builder and tools,
designed for the Umer OS prototype.  It follows the eight-phase boot recipe
adds UmerOS-specific extras (AI-driven module suggestions, scenario-based
recovery, post-quantum ready hooks, scenario runner).

## What is in here

```
initrd/
├── __init__.py        # public re-exports
├── __main__.py        # python -m initrd <cmd>
├── archivers.py       # gzip / xz / lz4 / zstd / raw
├── cpio.py            # CPIO "newc" reader + writer
├── vfs_ops.py         # in-memory VFS for the initrd
├── ramdisk.py         # RamDisk lifecycle (PROBED → … → RELEASED)
├── hooks.py           # initramfs-tools-style hook manager
├── phase_machine.py   # the eight TLDP boot phases
├── pivot_root.py      # pivot_root semantics over the VFS
├── module_resolver.py # autoprobe / user / hybrid module selection
├── scenarios.py       # install / live / recovery / rescue / per_machine
├── ai_helper.py       # optional AI / QRNG augmentation
├── builder.py         # cpio image builder (real, bootable images)
├── linuxrc.py         # the /init / /linuxrc orchestrator
├── linuxrc_main.py    # standalone entry point
└── README.md          # this file
```

## Eight-phase boot

The phase machine models the exact sequence from the TLDP reference:

1. **Load** — bootloader hands the kernel + initial RAM disk to userspace.
2. **Convert** — kernel unpacks the cpio archive into a tmpfs and frees initrd memory.
3. **Mount root** — the tmpfs is mounted read-write at `/`.
4. **Linuxrc** — `/init` (this package) runs as PID 1.
5. **Mount real root** — modules are loaded, the real root FS is mounted at `/newroot`.
6. **pivot_root** — `/newroot` becomes `/`, the old initrd moves to `/newroot/initrd`.
7. **exec init** — control is transferred to `/sbin/init` on the real root.
8. **Teardown** — initrd memory is released.

Each phase is an enum value on `BootPhase` and each transition is recorded in
`PhaseMachine.history` for post-mortem analysis.

## CLI

```powershell
python -m initrd selftest                 # run every module's self-test
python -m initrd build out.img.gz normal  # build a default NORMAL initramfs
python -m initrd inspect out.img.gz       # list the entries inside an image
python -m initrd run out.img.gz           # run the /init runtime over the image
python -m initrd scenarios                # list the five built-in scenarios
python -m initrd archivers                # list the registered archivers
python -m initrd plan 6.6.0-umeros        # show the build plan for a kernel
```

## Programmatic use

```python
from initrd.builder import BuildRequest, InitrdBuilder, OutputFormat
from initrd.scenarios import ScenarioId
from initrd.linuxrc import BootContext, run

request = BuildRequest(
    kernel_version="6.6.0-umeros",
    scenario=ScenarioId.NORMAL,
    output_format=OutputFormat.CPIO_XZ,
    output_path="initramfs-6.6.0-umeros.img.xz",
    extra_files={"/etc/umeros/greeting": b"hi from user\n"},
    extra_directories=["/data"],
)
result = InitrdBuilder().build(request)
print(result.as_dict())

# Boot the runtime on a freshly built image.
from initrd.archivers import detect_archiver
blob = detect_archiver(open(result.output_path, "rb").read()).decompress(
    open(result.output_path, "rb").read()
)
ctx = BootContext.from_request(request, blob=blob, host_root=os.getcwd())
exit_code = run(ctx)
```

## Scenarios

| ID            | Title                     | Notes                                          |
|---------------|---------------------------|------------------------------------------------|
| `normal`      | Normal boot               | Default two-phase boot.                        |
| `install`     | First-boot installation   | Interactive, autoprobes media.                 |
| `recovery`    | Recovery shell            | Drops to an interactive shell if root is bad.  |
| `live`        | Live CD / USB             | Stays in the initrd; no pivot_root.            |
| `rescue`      | Rescue shell              | No real root, just a shell.                    |
| `per_machine` | Per-machine config layer  | Reads `/etc/umeros/initrd.local.conf`.         |

## Hook points

| Hook point             | When it fires                              |
|------------------------|--------------------------------------------|
| `pre_load`             | before phase 1                             |
| `post_load`            | after phase 1                              |
| `pre_extract`          | before phase 2                             |
| `post_extract`         | after phase 2                              |
| `pre_module_probe`     | before phase 5 module resolution           |
| `post_module_probe`    | after phase 5 module resolution            |
| `pre_mount_real_root`  | before phase 5 mount                       |
| `post_mount_real_root` | after phase 5 mount                        |
| `pre_pivot_root`       | before phase 6                             |
| `post_pivot_root`      | after phase 6                              |
| `pre_init`             | before phase 7                             |
| `cleanup`              | at teardown                                |

Use the manager:

```python
from initrd.hooks import HookManager, HookPoint
mgr = HookManager()
mgr.add(HookPoint.PRE_PIVOT_ROOT, my_callback, tag="lvm")
mgr.add(HookPoint.POST_EXTRACT, my_async_callback)
mgr.run(HookPoint.PRE_PIVOT_ROOT, {"ctx": ctx})
```

## Integration with `boot.initrd_manager`

`boot/initrd_manager.py` already manages the image inventory
(registration, hashing, format detection, kernel-version parsing).
`initrd/` adds the *runtime* side that the inventory side never
covered:

* a real cpio builder (`initrd.builder`) instead of the
  placeholder-text stub in `initrd_manager.create_initrd`;
* a state machine for the eight boot phases
  (`initrd.phase_machine.PhaseMachine`);
* the `/init` / `/linuxrc` orchestrator (`initrd.linuxrc`);
* a hook system (`initrd.hooks.HookManager`);
* scenarios (`initrd.scenarios`).

A future change to `boot/initrd_manager.py` can delegate the actual
image generation to `InitrdBuilder` and call `linuxrc.run` to
exercise the runtime during the integration tests.

## Testing

The package ships a `_selftest()` helper in every module.  The
fastest way to run them all is:

```powershell
python -m initrd selftest
```

Per-module, run the file directly:

```powershell
python initrd/cpio.py
python initrd/ramdisk.py
python initrd/linuxrc.py
```

## License

Apache 2.0 — same as the rest of Umer OS.
