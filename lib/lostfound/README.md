# UmerOS `lib/lostfound` —  `/lost+found` & fsck Simulation

A faithful   `/lost+found` directory and the
`fsck` (filesystem check) recovery pipeline used by ext2/ext3/ext4.


## What /lost+found 

| Linux concept | Implementation here |
|---|---|
| `mkfs.ext4` creates `/lost+found` at partition root | `FilesystemPartition.mkfs()` |
| `mklost+found` preallocates blocks inside it | `LostFoundManager.mklost_found()` |
| fsck scans for **orphaned inodes** (allocated, no dirent reference) | `FilesystemChecker._phase3_orphans()` |
| fsck links orphans into lost+found named `#<inode>` | `LostFoundManager.recover()` |
| Name collisions get a letter suffix (`#42a`, `#42b`) | `LostFoundManager._make_name()` |
| Preallocated blocks let fsck store files **without allocating** on a damaged FS | reserved-slot accounting in `_next_slot()` |
| Every partition has its own isolated lost+found | one `LostFoundManager` per `FilesystemPartition` |
| fsck recreates lost+found if deleted — but **without** preallocated blocks | `recreate_without_prealloc()` |
| Corrupted inodes **cannot** be recovered | `Inode.corrupted` → `OrphanedInode.is_recoverable == False` |
| Sysadmin later moves recovered files out (`mv /lost+found/#42 /etc/fstab`) | `claim()` + `purge()` |
| `fsck -f` forces a check on a clean filesystem | `check(force=True)` |
| Superblock mount-count / dirty state decides whether to check | `SuperBlock.needs_check()` |

## Module layout

```
lib/lostfound/
├── __init__.py    Public API re-exports
├── inode.py       Inode, InodeType (ext4-style inode table entries)
├── superblock.py  SuperBlock, FsState (geometry, mount count, fs state)
├── orphan.py      OrphanedInode (why an inode was flagged)
├── manager.py     LostFoundManager, LostFoundEntry (the directory itself)
├── fsck.py        FilesystemChecker (5-phase check), FsckReport
└── partition.py   FilesystemPartition (inode table + superblock + lost+found)
```

## fsck phases (matching e2fsprogs ordering)

1. **Phase 1** — Superblock & inode bitmap consistency.
2. **Phase 2** — Directory structure & link-count (`nlinks`) verification.
3. **Phase 3** — Orphan scan (allocated inode with no directory reference).
4. **Phase 4** — lost+found verification (recreate if missing; warn if no
   preallocated blocks).
5. **Phase 5** — Recovery: link orphans into lost+found as `#<ino>`.

## Quick start

```python
from lib.lostfound import FilesystemPartition, FilesystemChecker

# 1. "mkfs" a partition — creates /lost+found with preallocated slots
p = FilesystemPartition(name="sda1", mount_point="/")
p.mkfs()
p.create_directory("/etc")
f = p.create_file("/etc/fstab", data=b"UUID=abc / ext4 defaults 0 1\n")

# 2. Simulate a crash — inode has data but no directory entry
p.orphan_inode(f.ino)

# 3. Run fsck (force, like `fsck -f`)
report = FilesystemChecker(p, auto_repair=True).check(force=True)
print(report.summary())
# fsck: filesystem clean (0 errors, 0 fixed, 1 orphans, 1 recovered ...)

# 4. The file now lives in lost+found, named by inode number
entry = p.lost_found.find_by_ino(f.ino)   # -> #4

# 5. Sysadmin claims it back and purges
p.lost_found.claim(entry.name, "/etc/fstab")
p.lost_found.purge_claimed()
```

## Kernel integration

`kernel/umer_kernel.py` wires this in during boot:

* `UmerKernel.__init__` creates `self.root_partition`
  (`FilesystemPartition(name="qfs_root", mount_point="/")`) and
  `self.lost_found` (its manager).
* During `boot()`, after `qfs.mount("/")`, the kernel runs
  `root_partition.mkfs()`, calls `superblock.on_mount()`, and if
  `needs_check()` is true runs a full `FilesystemChecker` pass —
  printing any recovered `#<ino>` names — then exposes `/lost+found`
  in the VFS tree.

## Tests

```bash
python -m unittest tests.test_lostfound         # 62 unit tests
python -m unittest tests.test_lostfound_kernel  # 6 integration tests
```
