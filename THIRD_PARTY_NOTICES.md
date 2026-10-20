# Third-Party Notices

UmerOS itself is licensed under **GPL-3.0** (see `LICENSE`). This file records
the third-party components vendored into the tree together with their own
license terms. Vendored components keep **their original licenses** and are
*not* relicensed to GPL-3.0.

## liboqs — Open Quantum Safe C library

| Field | Value |
| --- | --- |
| Upstream | https://github.com/open-quantum-safe/liboqs |
| Vendored path | `liboqs/` |
| Pinned revision | tag `0.16.0` — commit `5a1a854b0dc9f2141bdc771c555ee60c37950183` |
| License | MIT (see `liboqs/LICENSE.txt`) |
| Declaration | `.gitmodules` (`git submodule update --init --recursive`) |

liboqs is an open-source C library of quantum-safe cryptographic algorithms used
as the optional post-quantum backend of the UmerOS `quantum/` package
(`quantum/crypto_pqc.py` imports the `liboqs-python` bindings and falls back to
classical AES-256-GCM/ECDSA when they are unavailable).

**License compatibility.** MIT is a permissive, GPL-3.0-compatible license, so
vendoring liboqs alongside GPL-3.0 UmerOS code is permitted provided the MIT
terms and copyright notice are retained in full. liboqs is therefore
intentionally **excluded** from the GPL-3.0 header audit in `legal/licenses.py`
(its sources are not required to carry the UmerOS GPL-3.0 header), and its
license is **not** rewritten to GPL-3.0.

## Adding a vendored component

When vendoring a new third-party component, add an entry here recording its
upstream URL, the pinned revision, its path, and its license, and declare it in
`.gitmodules` when it is pulled in as a git submodule.
