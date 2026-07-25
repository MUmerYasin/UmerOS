"""
Umer OS Task Credentials
========================
Inspired by Linux ``kernel/cred.c`` (David Howells, 2008).

A **credential** bundles the identity of a task: its user id, group id,
supplementary groups, and the capability set it may use.  Credentials are
**refcounted** and shared between tasks (fork inherits the parent's cred,
``exec`` may install a new one).  This mirrors Linux's copy-on-write
credential model:

    struct cred {
        atomic_t        usage;       /* refcount               */
        kuid_t          uid;         /* real UID               */
        kgid_t          gid;         /* real GID               */
        kuid_t          euid;        /* effective UID          */
        kgid_t          egid;        /* effective GID          */
        kuid_t          suid; sgid;  /* saved UID/GID          */
        kernel_cap_t    cap_*;       /* permitted / effective  */
        struct group_info *group_info;
    };

In the Python simulation every value is a plain int (uid/gid) or a
``frozenset`` (capability set), and refcounting is done with a simple
counter so we can detect leaks in tests.

Linux semantics preserved:
  * ``prepare_creds()``     – snapshot current cred for modification.
  * ``commit_creds()``      – atomically install a new cred on a task.
  * ``abort_creds()``       – discard a prepared cred (drop refcount).
  * ``override_creds()``    – temporarily push a cred (for kernel work).
  * ``revert_creds()``      – restore the previous cred.
  * Capabilities are tracked separately from the ``CapabilityManager``
    (which enforces *checks*); cred carries the *set* the task owns.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from typing import Any, FrozenSet, Iterable, Optional, Set

log = logging.getLogger("UmerOS.Cred")

# Root identity (uid 0) bypasses capability checks — mirrors Linux ROOT.
ROOT_UID = 0
NOBODY_UID = 65534  # "nobody" — unprivileged sentinel

# Default capability set granted to root credentials.
DEFAULT_ROOT_CAPS: FrozenSet[str] = frozenset({
    "fs.read", "fs.write", "fs.admin",
    "net.send", "net.recv", "net.admin",
    "proc.spawn", "proc.kill",
    "ai.inference", "ai.train",
})

# Caps granted to an ordinary unprivileged user.
DEFAULT_USER_CAPS: FrozenSet[str] = frozenset({
    "fs.read", "fs.write",
    "net.send", "net.recv",
})


@dataclass
class Credentials:
    """A refcounted bundle of task identity.

    Use :meth:`get` / :meth:`put` to manage references; the object is
    immutable otherwise.  Mutating operations return a *new* snapshot
    (copy-on-write) rather than mutating in place.

    Attributes:
        uid:      Real user id (0 = root).
        euid:     Effective user id (used for permission checks).
        suid:     Saved user id (for setuid binaries).
        gid:      Real group id.
        egid:     Effective group id.
        groups:   Supplementary group ids.
        caps:     Capability strings this cred is permitted to use.
        usage:    Live reference count (managed by get/put).
    """
    uid: int = ROOT_UID
    euid: int = ROOT_UID
    suid: int = ROOT_UID
    gid: int = ROOT_UID
    egid: int = ROOT_UID
    sgid: int = ROOT_UID
    groups: FrozenSet[int] = field(default_factory=frozenset)
    caps: FrozenSet[str] = field(default_factory=lambda: DEFAULT_ROOT_CAPS)
    # Refcount — deliberately mutable even though the rest is immutable.
    usage: int = field(default=1, repr=False)

    # ── Refcount management ───────────────────────────────────────────────

    def get(self) -> "Credentials":
        """Take a reference to this credential (returns self).

        Mirrors Linux ``get_cred()``: increments the refcount.
        """
        self.usage += 1
        return self

    def put(self) -> None:
        """Release a reference.  Logs a warning if usage goes negative.

        Mirrors Linux ``put_cred()``: decrements the refcount.  When it
        reaches zero the credential is logically freed.
        """
        if self.usage <= 0:
            log.warning("put() on credential with usage=%d (double free?)", self.usage)
            self.usage = 0
            return
        self.usage -= 1

    # ── Identity predicates ──────────────────────────────────────────────

    def is_root(self) -> bool:
        """True if the *effective* uid is 0 (root bypass)."""
        return self.euid == ROOT_UID

    def in_group(self, gid: int) -> bool:
        """True if ``gid`` matches the real gid or any supplementary group."""
        return gid == self.gid or gid in self.groups

    def has_cap(self, cap: str) -> bool:
        """True if the capability set contains ``cap`` (or euid is root)."""
        return self.is_root() or cap in self.caps

    # ── Copy-on-write helpers ────────────────────────────────────────────

    def copy(self) -> "Credentials":
        """Return a new refcount=1 snapshot with the same fields.

        Mirrors Linux ``prepare_creds()``.  The caller owns the new
        reference and must ``commit_creds()`` or ``put()`` it.
        """
        return replace(
            self,
            groups=frozenset(self.groups),
            caps=frozenset(self.caps),
            usage=1,
        )

    def with_capabilities(self, caps: Iterable[str]) -> "Credentials":
        """Return a copy with a new capability set (refcount=1)."""
        snap = self.copy()
        snap.caps = frozenset(caps)
        return snap

    def with_euid(self, euid: int) -> "Credentials":
        """Return a copy with a new effective uid (refcount=1)."""
        snap = self.copy()
        snap.euid = euid
        return snap

    def __del__(self):
        # Best-effort leak detection: a cred still referenced at GC time
        # indicates a missing put().
        if getattr(self, "usage", 0) > 1:
            log.debug("Credentials GC'd with usage=%d (possible leak)", self.usage)


# ── Credential managers ──────────────────────────────────────────────────

class CredentialStore:
    """Per-task credential registry with override stack support.

    Tracks the *real* credential (the identity the task was born with)
    and the *active* credential (what permission checks use).  The active
    cred can be temporarily overridden for kernel-initiated work, then
    restored — mirrors Linux ``override_creds()`` / ``revert_creds()``.
    """

    def __init__(self) -> None:
        # pid -> {"real": Credentials, "active": Credentials, "override": [stack]}
        self._tasks: dict[int, dict[str, Any]] = {}
        # Shared credential pool: cache identical creds to share refcounts.
        self._root_cred: Credentials = Credentials()

    # ── Task lifecycle ──────────────────────────────────────────────────

    def register(self, pid: int, cred: Optional[Credentials] = None) -> Credentials:
        """Install a credential for ``pid``.

        If ``cred`` is None a fresh root cred is shared (refcount++).
        Returns the active credential for the task.
        """
        if cred is None:
            cred = self._root_cred.get()
        elif cred.usage <= 0:
            cred.usage = 1
        self._tasks[pid] = {
            "real": cred.get(),
            "active": cred.get(),
            "override": [],
        }
        log.debug("Registered credentials for PID %d (uid=%d)", pid, cred.uid)
        return cred

    def unregister(self, pid: int) -> None:
        """Drop all references held for ``pid`` (mirrors ``exit_creds()``)."""
        rec = self._tasks.pop(pid, None)
        if rec is None:
            return
        # Discard any unreverted overrides first.
        while rec["override"]:
            rec["override"].pop().put()
        rec["active"].put()
        rec["real"].put()
        log.debug("Released credentials for PID %d", pid)

    # ── Query / mutation ────────────────────────────────────────────────

    def get(self, pid: int) -> Optional[Credentials]:
        """Return the *active* credential for ``pid`` (or None)."""
        rec = self._tasks.get(pid)
        return rec["active"] if rec else None

    def get_real(self, pid: int) -> Optional[Credentials]:
        """Return the *real* (born-with) credential for ``pid``."""
        rec = self._tasks.get(pid)
        return rec["real"] if rec else None

    def prepare(self, pid: int) -> Optional[Credentials]:
        """Snapshot the active cred for modification (``prepare_creds``)."""
        cred = self.get(pid)
        return cred.copy() if cred else None

    def commit(self, pid: int, new_cred: Credentials) -> bool:
        """Install ``new_cred`` as the active cred (``commit_creds``).

        The previous active cred's reference is released.  Returns False
        if ``pid`` is unknown.
        """
        rec = self._tasks.get(pid)
        if rec is None:
            new_cred.put()
            return False
        old = rec["active"]
        rec["active"] = new_cred
        old.put()
        log.info("PID %d committed new cred (euid=%d, caps=%d)",
                 pid, new_cred.euid, len(new_cred.caps))
        return True

    def abort(self, new_cred: Credentials) -> None:
        """Discard a prepared cred (``abort_creds``)."""
        new_cred.put()

    # ── Override / revert ───────────────────────────────────────────────

    def override(self, pid: int, override_cred: Credentials) -> bool:
        """Push ``override_cred`` as the new active cred, saving the old.

        Mirrors Linux ``override_creds()``.  Must be balanced by
        :meth:`revert`.  Returns False if ``pid`` is unknown.
        """
        rec = self._tasks.get(pid)
        if rec is None:
            return False
        rec["override"].append(rec["active"])
        rec["active"] = override_cred.get()
        return True

    def revert(self, pid: int) -> bool:
        """Pop the last override and restore the previous cred.

        Mirrors Linux ``revert_creds()``.  Returns False if there is no
        override to revert or the pid is unknown.
        """
        rec = self._tasks.get(pid)
        if rec is None or not rec["override"]:
            return False
        current = rec["active"]
        rec["active"] = rec["override"].pop()
        current.put()
        return True

    # ── Convenience constructors ────────────────────────────────────────

    @staticmethod
    def root() -> Credentials:
        """A fresh root credential (euid=0, all default caps)."""
        return Credentials()

    @staticmethod
    def user(uid: int, gid: int = 0, *,
             groups: Iterable[int] = (),
             caps: Iterable[str] = DEFAULT_USER_CAPS) -> Credentials:
        """A fresh unprivileged-user credential."""
        return Credentials(
            uid=uid, euid=uid, suid=uid,
            gid=gid, egid=gid, sgid=gid,
            groups=frozenset(groups),
            caps=frozenset(caps),
        )


__all__ = [
    "Credentials",
    "CredentialStore",
    "ROOT_UID",
    "NOBODY_UID",
    "DEFAULT_ROOT_CAPS",
    "DEFAULT_USER_CAPS",
]
