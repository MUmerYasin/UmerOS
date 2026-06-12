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
