"""H189 follow-up: finish the PackageOptManager overrides the colliding
guards in _h189_fix.py left half-applied (signature + body + one call site)."""
from pathlib import Path
import ast

ROOT = Path("F:/Pension Person Details/UmerOS")
PKG = ROOT / "opt/package.py"


def read():
    return PKG.read_bytes().decode("utf-8")


text = read().replace("\r\n", "\n")

# 1. signature (currently `def __init__(self, opt_root: str = "/opt"):` at L403)
OLD_SIG = '    def __init__(self, opt_root: str = "/opt"):\n'
assert text.count(OLD_SIG) == 1, text.count(OLD_SIG)
text = text.replace(
    OLD_SIG,
    "\n".join([
        "    def __init__(",
        "        self,",
        '        opt_root: str = "/opt",',
        '        etc_opt_root: str = "/etc/opt",',
        '        var_opt_root: str = "/var/opt",',
        "    ):",
    ]) + "\n",
)

# 2. body: store the roots (anchor on the unique 2-line sequence)
OLD_BODY = (
    "            var_opt_root: Root directory for opt variable data\n"
    '        """\n'
    "        self.opt_root = Path(opt_root)\n"
    "        self._ensure_root()\n"
)
assert text.count(OLD_BODY) == 1, text.count(OLD_BODY)
text = text.replace(
    OLD_BODY,
    "            var_opt_root: Root directory for opt variable data\n"
    '        """\n'
    "        self.opt_root = Path(opt_root)\n"
    "        # [FIX H189] forward the overrides so every OptPackage this manager\n"
    "        # builds stays inside the caller's roots.\n"
    "        self.etc_opt_root = Path(etc_opt_root)\n"
    "        self.var_opt_root = Path(var_opt_root)\n"
    "        self._ensure_root()\n",
)

# 3. the last un-forwarded call site
OLD_CALL = "        return OptPackage(name, provider, str(self.opt_root))\n"
assert text.count(OLD_CALL) == 1, text.count(OLD_CALL)
text = text.replace(
    OLD_CALL,
    "        return OptPackage(\n"
    "            name, provider, str(self.opt_root), str(self.etc_opt_root), str(self.var_opt_root)\n"
    "        )\n",
)

ast.parse(text)
PKG.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))

# verify
t = read().replace("\r\n", "\n")
assert t.count("self.etc_opt_root = Path(etc_opt_root)") == 2
assert t.count("def __init__(\n        self,\n        opt_root: str = \"/opt\",") == 1
assert "return OptPackage(name, provider, str(self.opt_root))\n" not in t
assert t.count("OptPackage(\n            name, provider, str(self.opt_root), str(self.etc_opt_root)") == 2
print("PackageOptManager fully wired: signature, stored roots, all 4 call sites")
