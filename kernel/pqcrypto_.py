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

#Implementation Example: Key Encapsulation (ML-KEM / Kyber)
#Because standard libraries like the core cryptography package depend on native OpenSSL support (which handles PQC primarily for TLS transport layers rather than raw primitives), developers use specialized wrappers for individual application logic.
#The following snippet demonstrates how to generate a key pair and establish a shared secret using the popular pqcrypto interface



# Installation: pip install pqcrypto
from pqcrypto.kem import kyber1024

# 1. Alice generates her public and private keys
public_key, private_key = kyber1024.generate_keypair()

# 2. Bob uses Alice's public key to generate a shared secret and ciphertext
# (Bob sends this ciphertext back to Alice over the network)
ciphertext, bob_shared_secret = kyber1024.encrypt(public_key)

# 3. Alice decrypts the ciphertext using her private key to get the same secret
alice_shared_secret = kyber1024.decrypt(private_key, ciphertext)

# Verify both secrets match
assert alice_shared_secret == bob_shared_secret
print("Secure post-quantum key exchange successful!")
