# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
build/sign_artifact.py — [FIX H42] mandatory post-build signing gate.

Zero-trust requires that every shipped binary is cryptographically signed
AND that the signature is verified before release. PyInstaller cannot sign
PE files on Windows (``codesign_identity`` is macOS-only), so this script
is the enforced post-build step:

    python build/sign_artifact.py dist/UmerOS-GUI.exe

Behaviour (fail-closed):
  * Windows: signs with signtool using UMEROS_SIGN_PFX (+ optional
    UMEROS_SIGN_PFX_PASSWORD) or a cert-store thumbprint
    (UMEROS_SIGN_THUMBPRINT), then VERIFIES with signtool /verify /pa.
  * macOS: verifies via codesign --verify --strict after codesigning with
    UMEROS_CODESIGN_IDENTITY (also usable as the spec's codesign_identity).
  * Any missing tool/cert/verification failure exits non-zero — unless
    UMEROS_ALLOW_UNSIGNED=1 is explicitly set for throwaway dev builds,
    in which case the script still warns loudly.

Exit codes: 0 signed+verified · 1 any failure · 2 usage error.
"""

from __future__ import annotations

import os
import subprocess
import sys


def _allow_unsigned() -> bool:
    return os.environ.get("UMEROS_ALLOW_UNSIGNED", "") == "1"


def _fail(msg: str) -> "NoReturn":  # type: ignore[name-defined]
    print(f"[sign_artifact] FAIL: {msg}", file=sys.stderr)
    if _allow_unsigned():
        print("[sign_artifact] UMEROS_ALLOW_UNSIGNED=1 -> continuing UNSIGNED "
              "(dev-only artifact, DO NOT SHIP).", file=sys.stderr)
        sys.exit(0)
    sys.exit(1)


def sign_windows(artifact: str) -> None:
    signtool = os.environ.get("UMEROS_SIGNSIGNTOOL", "signtool")
    pfx = os.environ.get("UMEROS_SIGN_PFX", "")
    pwd = os.environ.get("UMEROS_SIGN_PFX_PASSWORD", "")
    thumb = os.environ.get("UMEROS_SIGN_THUMBPRINT", "")

    if not pfx and not thumb:
        _fail("no certificate configured: set UMEROS_SIGN_PFX "
              "(+ UMEROS_SIGN_PFX_PASSWORD) or UMEROS_SIGN_THUMBPRINT")

    cmd = [signtool, "sign", "/fd", "SHA256", "/tr",
           "http://timestamp.digicert.com", "/td", "SHA256"]
    if pfx:
        cmd += ["/f", pfx]
        if pwd:
            cmd += ["/p", pwd]
    if thumb:
        cmd += ["/sha1", thumb]
    cmd.append(artifact)

    print("[sign_artifact] signing:", " ".join(cmd[:2]), "…")
    if subprocess.call(cmd) != 0:
        _fail("signtool sign returned non-zero")

    if subprocess.call([signtool, "verify", "/pa", "/all", artifact]) != 0:
        _fail("signtool verify FAILED — unsigned or broken signature")


def sign_darwin(artifact: str) -> None:
    identity = os.environ.get("UMEROS_CODESIGN_IDENTITY", "")
    if not identity:
        _fail("set UMEROS_CODESIGN_IDENTITY (Developer ID Application)")
    if subprocess.call(["codesign", "--force", "--options", "runtime",
                        "--sign", identity, artifact]) != 0:
        _fail("codesign failed")
    if subprocess.call(["codesign", "--verify", "--strict", artifact]) != 0:
        _fail("codesign verify failed")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    artifact = argv[1]
    if not os.path.isfile(artifact):
        _fail(f"artifact not found: {artifact}")

    if sys.platform == "win32":
        sign_windows(artifact)
    elif sys.platform == "darwin":
        sign_darwin(artifact)
    else:
        _fail(f"unsupported platform: {sys.platform}")

    print("[sign_artifact] OK:", artifact)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))