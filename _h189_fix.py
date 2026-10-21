"""H189 - OptPackage must not hardcode /etc/opt and /var/opt.

opt/manager.py already honours `etc_opt_root`/`var_opt_root` overrides, but the
values never reach the package layer: `OptPackage.__init__` builds them from
fixed literals, and `PackageOptManager` (opt/package.py's own "OptManager") has
no override at all.  A temp-root demo/test therefore still resolves the
package's etc/var trees to the real system directories.
"""
from pathlib import Path
import ast

ROOT = Path("F:/Pension Person Details/UmerOS")
PKG = ROOT / "opt/package.py"
MGR = ROOT / "opt/manager.py"
DEMO = ROOT / "opt/test_opt.py"


def read(p: Path) -> str:
    return p.read_bytes().decode("utf-8")


def write(p: Path, text: str) -> None:
    norm = text.replace("\r\n", "\n")
    ast.parse(norm)
    crlf = read(p).count("\r\n") > 0
    p.write_bytes((norm.replace("\n", "\r\n") if crlf else norm).encode("utf-8"))
    print(f"  wrote {p.name}")


def sub(p: Path, old: str, new: str, count: int = 1, guard: str = "") -> None:
    text = read(p).replace("\r\n", "\n")
    if guard and guard in text:
        print(f"  {p.name}: skipped ({guard!r} present)")
        return
    n = text.count(old)
    assert n == count, f"{p.name}: want {count} of {old[:70]!r}, got {n}"
    write(p, text.replace(old, new))


# ───────────────────────────── opt/package.py ─────────────────────────────

# 1. OptPackage.__init__ signature + stored roots
sub(
    PKG,
    '    def __init__(self, name: str, provider: str = "", opt_root: str = "/opt"):\n',
    "\n".join([
        "    def __init__(",
        '        self,',
        '        name: str,',
        '        provider: str = "",',
        '        opt_root: str = "/opt",',
        '        etc_opt_root: str = "/etc/opt",',
        '        var_opt_root: str = "/var/opt",',
        "    ):",
    ]) + "\n",
    guard='        etc_opt_root: str = "/etc/opt",',
)
sub(
    PKG,
    "        self.opt_root = Path(opt_root)\n        self._ensure_root()\n        self._setup_paths()\n",
    "        self.opt_root = Path(opt_root)\n"
    "        # [FIX H189] the etc/var roots are constructor-injectable so a\n"
    "        # temp-root run cannot resolve them to the real system dirs.\n"
    "        self.etc_opt_root = Path(etc_opt_root)\n"
    "        self.var_opt_root = Path(var_opt_root)\n"
    "        self._ensure_root()\n"
    "        self._setup_paths()\n",
    guard="self.etc_opt_root = Path(etc_opt_root)",
)

# 2. docstring params for BOTH __init__s in package.py (positional: 1st OptPackage,
#    2nd PackageOptManager) - the line itself is identical in both docstrings.
text = read(PKG).replace("\r\n", "\n")
MARK = "            opt_root: Root directory for opt packages\n"
assert text.count(MARK) == 2, f"expected the docstring line twice, got {text.count(MARK)}"
if "etc_opt_root: Root directory for opt configurations" not in text:
    first = text.index(MARK)
    after = text[first + len(MARK):]
    assert after.lstrip().startswith('"""'), "1st occurrence is not OptPackage.__init__"
    ins = (
        "            etc_opt_root: Root directory for opt configurations\n"
        "            var_opt_root: Root directory for opt variable data\n"
    )
    second = text.index(MARK, first + len(MARK))
    after2 = text[second + len(MARK): second + len(MARK) + 40]
    assert '"""' in after2 and "self.opt_root" in after2, "2nd occurrence is not PackageOptManager"
    text = (
        text[: first + len(MARK)]
        + ins
        + text[first + len(MARK): second + len(MARK)]
        + ins
        + text[second + len(MARK):]
    )
    write(PKG, text)

# 3. _setup_paths: derive etc/var from the injected roots
sub(
    PKG,
    "\n".join([
        "        if self.provider:",
        '            etc_root = safe_child(Path("/etc/opt"), self.provider)',
        '            var_root = safe_child(Path("/var/opt"), self.provider)',
        "        else:",
        '            etc_root = Path("/etc/opt")',
        '            var_root = Path("/var/opt")',
    ]) + "\n",
    "\n".join([
        "        # [FIX H189] contained against provider/name *and* honouring the",
        "        # constructor overrides, so a temp-root run cannot resolve the",
        "        # package's etc/var trees to the real system directories.",
        "        if self.provider:",
        "            etc_root = safe_child(self.etc_opt_root, self.provider)",
        "            var_root = safe_child(self.var_opt_root, self.provider)",
        "        else:",
        "            etc_root = Path(self.etc_opt_root)",
        "            var_root = Path(self.var_opt_root)",
    ]) + "\n",
    guard="safe_child(self.etc_opt_root, self.provider)",
)

# 4. PackageOptManager: accept + forward the overrides
sub(
    PKG,
    '    def __init__(self, opt_root: str = "/opt"):\n',
    "\n".join([
        "    def __init__(",
        '        self,',
        '        opt_root: str = "/opt",',
        '        etc_opt_root: str = "/etc/opt",',
        '        var_opt_root: str = "/var/opt",',
        "    ):",
    ]) + "\n",
    guard='        etc_opt_root: str = "/etc/opt",\n        var_opt_root: str = "/var/opt",\n    ):\n        """',
)
sub(
    PKG,
    "        self.opt_root = Path(opt_root)\n        self._ensure_root()\n",
    "        self.opt_root = Path(opt_root)\n"
    "        # [FIX H189] forward the overrides so every OptPackage this manager\n"
    "        # builds stays inside the caller's roots.\n"
    "        self.etc_opt_root = Path(etc_opt_root)\n"
    "        self.var_opt_root = Path(var_opt_root)\n"
    "        self._ensure_root()\n",
    guard="        self.etc_opt_root = Path(etc_opt_root)\n        self.var_opt_root = Path(var_opt_root)\n        self._ensure_root()",
)
sub(
    PKG,
    "        package = OptPackage(name, provider, str(self.opt_root))\n",
    "        package = OptPackage(\n"
    "            name, provider, str(self.opt_root), str(self.etc_opt_root), str(self.var_opt_root)\n"
    "        )\n",
    guard="str(self.etc_opt_root), str(self.var_opt_root)\n        )",
)
sub(
    PKG,
    "        return OptPackage(name, provider, str(self.opt_root))\n",
    "        return OptPackage(\n"
    "            name, provider, str(self.opt_root), str(self.etc_opt_root), str(self.var_opt_root)\n"
    "        )\n",
    guard="str(self.etc_opt_root), str(self.var_opt_root)\n        )",
)
sub(
    PKG,
    "                            package = OptPackage(subitem.name, item.name, str(self.opt_root))\n",
    "                            package = OptPackage(\n"
    "                                subitem.name,\n"
    "                                item.name,\n"
    "                                str(self.opt_root),\n"
    "                                str(self.etc_opt_root),\n"
    "                                str(self.var_opt_root),\n"
    "                            )\n",
    guard="str(self.etc_opt_root),\n                                str(self.var_opt_root),",
)
sub(
    PKG,
    '                    package = OptPackage(item.name, "", str(self.opt_root))\n',
    "                    package = OptPackage(\n"
    '                        item.name,\n'
    '                        "",\n'
    "                        str(self.opt_root),\n"
    "                        str(self.etc_opt_root),\n"
    "                        str(self.var_opt_root),\n"
    "                    )\n",
    guard='                        item.name,\n                        "",\n                        str(self.opt_root),',
)

# ───────────────────────────── opt/manager.py ──────────────────────────────

sub(
    MGR,
    "        self.package_manager = PackageOptManager(str(opt_root))\n",
    "        # [FIX H189] forward the etc/var overrides into the package layer,\n"
    "        # whose OptPackage used to hardcode /etc/opt and /var/opt.\n"
    "        self.package_manager = PackageOptManager(\n"
    "            str(opt_root), str(etc_opt_root), str(var_opt_root)\n"
    "        )\n",
    guard="self.package_manager = PackageOptManager(\n",
)
sub(
    MGR,
    "            package = OptPackage(name, provider, str(self.opt_root))\n",
    "            package = OptPackage(\n"
    "                name,\n"
    "                provider,\n"
    "                str(self.opt_root),\n"
    "                str(self.etc_opt_root),\n"
    "                str(self.var_opt_root),\n"
    "            )\n",
    guard="str(self.etc_opt_root),\n                str(self.var_opt_root),",
)

# ───────────────────────── opt/test_opt.py (in-package demo) ───────────────

sub(
    DEMO,
    '            package = OptPackage("testapp", opt_root=str(opt_root))\n',
    "            # [FIX H189] keep the demo inside its temp root\n"
    "            package = OptPackage(\n"
    '                "testapp",\n'
    "                opt_root=str(opt_root),\n"
    "                etc_opt_root=str(Path(tmpdir) / \"etc\" / \"opt\"),\n"
    "                var_opt_root=str(Path(tmpdir) / \"var\" / \"opt\"),\n"
    "            )\n",
    guard="etc_opt_root=str(Path(tmpdir) / \"etc\" / \"opt\")",
)

print("\nH189 edits complete")
