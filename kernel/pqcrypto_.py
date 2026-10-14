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
UmerOS /kernel — ML-KEM / Kyber key-encapsulation example  [FUTURE]
====================================================================
Reference snippet showing a post-quantum key exchange through the ``pqcrypto``
interface (ML-KEM / Kyber1024).

.. note:: This is a documentation/reference example, NOT part of the kernel.
   It is guarded behind ``__main__`` so that ``pqcrypto`` is never imported and
   no key material is generated at import time.  The canonical post-quantum
   crypto lives under ``liboqs/`` and ``security/``.
"""

from __future__ import annotations

import logging

log = logging.getLogger("UmerOS.Kernel.PQCryptoExample")


def demo() -> None:
    """Run the ML-KEM key-exchange example (requires ``pip install pqcrypto``)."""
    from pqcrypto.kem import kyber1024

    # 1. Alice generates her public and private keys.
    public_key, private_key = kyber1024.generate_keypair()
    # 2. Bob uses Alice's public key to produce a shared secret + ciphertext
    #    (Bob sends this ciphertext back to Alice over the network).
    ciphertext, bob_shared_secret = kyber1024.encrypt(public_key)
    # 3. Alice decrypts the ciphertext using her private key.
    alice_shared_secret = kyber1024.decrypt(private_key, ciphertext)
    assert alice_shared_secret == bob_shared_secret
    log.info("Secure post-quantum key exchange successful!")


if __name__ == "__main__":
    demo()
