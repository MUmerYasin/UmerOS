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
UmerOS Crypto Framework
=======================
Kernel-like Crypto API.
Implements ciphers (AES, DES, ChaCha20), hashes (SHA-256, MD5, SHA3-256),
AEAD (AES-GCM), and RNG with the full crypto_alloc_tfm() API.
"""

from __future__ import annotations

import hashlib
import hmac
import math
import os
import struct
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CRYPTO_ALG_CIPHER = "cipher"
CRYPTO_ALG_HASH = "hash"
CRYPTO_ALG_AEAD = "aead"
CRYPTO_ALG_RNG = "rng"
CRYPTO_ALG_KPP = "kpp"

CRYPTO_CIPHER_ECB = "ecb"
CRYPTO_CIPHER_CBC = "cbc"
CRYPTO_CIPHER_CTR = "ctr"
CRYPTO_CIPHER_XTS = "xts"
CRYPTO_CIPHER_CFB = "cfb"
CRYPTO_CIPHER_OFB = "ofb"
CRYPTO_CIPHER_GCM = "gcm"
CRYPTO_CIPHER_CCM = "ccm"
CRYPTO_CIPHER_CMAC = "cmac"

CRYPTO_ALG_ASYNC = 0x01
CRYPTO_ALG_KERN_DRIVER_ONLY = 0x02
CRYPTO_ALG_DEAD = 0x04
CRYPTO_ALG_TYPE_CIPHER = 0x10
CRYPTO_ALG_TYPE_HASH = 0x20
CRYPTO_ALG_TYPE_AEAD = 0x40
CRYPTO_ALG_TYPE_RNG = 0x80

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class CryptoAlg:
    """Crypto algorithm"""
    name: str
    driver_name: str
    algo_type: str  # "cipher", "hash", "aead", "rng", "kpp"
    cipher_mode: str = ""
    key_sizes: list = field(default_factory=list)
    iv_size: int = 0
    block_size: int = 16
    digest_size: int = 0
    priority: int = 100
    flags: int = 0
    _impl: Any = field(default=None, repr=False)

@dataclass
class CryptoTFM:
    """Transformation (crypto instance)"""
    name: str
    alg: CryptoAlg
    key: bytes = b''
    iv: bytes = b''
    state: str = "init"
    _created_at: float = 0.0

@dataclass
class CryptoRequest:
    """Crypto request"""
    tfm: CryptoTFM
    data: bytes = b''
    result: bytes = b''
    iv: bytes = b''
    op: str = ""
    status: str = "pending"
    error: str = ""
    created_at: float = 0.0

@dataclass
class CryptoTemplate:
    """Algorithm template (template-based crypto)"""
    name: str
    base_type: str
    template_params: dict = field(default_factory=dict)
    driver_name: str = ""

@dataclass
class CryptoInstance:
    """Crypto instance context"""
    tfm: CryptoTFM
    request: CryptoRequest
    owner: str = ""

# ---------------------------------------------------------------------------
# Global Registries
# ---------------------------------------------------------------------------

_alg_registry: Dict[str, CryptoAlg] = {}
_template_registry: Dict[str, CryptoTemplate] = {}
_instances: List[CryptoInstance] = []

# ---------------------------------------------------------------------------
# AES Implementation (pure Python, FIPS 197)
# ---------------------------------------------------------------------------

_AES_SBOX = [
    0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
    0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
    0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
    0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
    0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
    0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
    0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
    0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
    0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
    0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
    0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
    0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
    0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
    0xd2,0x41,0x79,0xe9,0x95,0x99,0xbc,0x66,0xfb,0x61,0x9c,0xf5,0x53,0x3e,0xc8,0x42,
    0xd0,0xa8,0xc9,0xff,0xf2,0xce,0xfe,0xcf,0xb1,0x5c,0xa3,0x5c,0x40,0x52,0x36,0x9e,
    0x63,0x4c,0x9f,0x58,0x1e,0xb3,0x74,0x22,0x54,0x07,0x6d,0x83,0x10,0x42,0x5a,0x0d,
]

_AES_INV_SBOX = [
    0x52,0x09,0x6a,0xd5,0x30,0x36,0xa5,0x38,0xbf,0x40,0xa3,0x9e,0x81,0xf3,0xd7,0xfb,
    0x7c,0xe3,0x39,0x82,0x9b,0x2f,0xff,0x87,0x34,0x8e,0x43,0x44,0xc4,0xde,0xe9,0xcb,
    0x54,0x7b,0x94,0x32,0xa6,0xc2,0x23,0x3d,0xee,0x4c,0x95,0x0b,0x42,0xfa,0xc3,0x4e,
    0x08,0x2e,0xa1,0x66,0x28,0xd9,0x24,0xb2,0x76,0x5b,0xa2,0x49,0x6d,0x8b,0xd1,0x25,
    0x72,0xf8,0xf6,0x64,0x86,0x68,0x98,0x16,0xd4,0xa4,0x5c,0xcc,0x5d,0x65,0xb6,0x92,
    0x6c,0x70,0x48,0x50,0xfd,0xed,0xb9,0xda,0x5e,0x15,0x46,0x57,0xa7,0x8d,0x9d,0x84,
    0x90,0xd8,0xab,0x00,0x8c,0xbc,0xd3,0x0a,0xf7,0xe4,0x58,0x05,0xb8,0xb3,0x45,0x06,
    0xd0,0x2c,0x1e,0x8f,0xca,0x3f,0x0f,0x02,0xc1,0xaf,0xbd,0x03,0x01,0x13,0x8a,0x6b,
    0x3a,0x91,0x11,0x41,0x4f,0x67,0xdc,0xea,0x97,0xf2,0xcf,0xce,0xf0,0xb4,0xe6,0x73,
    0x96,0xac,0x74,0x22,0xe7,0xad,0x35,0x85,0xe2,0xf9,0x37,0xe8,0x1c,0x75,0xdf,0x6e,
    0x47,0xf1,0x1a,0x71,0x1d,0x29,0xc5,0x89,0x6f,0xb7,0x62,0x0e,0xaa,0x18,0xbe,0x1b,
    0xfc,0x56,0x3e,0x4b,0xc6,0xd2,0x79,0x20,0x9a,0xdb,0xc0,0xfe,0x78,0xcd,0x5a,0xf4,
    0x1f,0xdd,0xa8,0x33,0x88,0x07,0xc7,0x31,0xb1,0x12,0x10,0x59,0x27,0x80,0xec,0x5f,
    0x60,0x51,0x7f,0xa9,0x19,0xb5,0x4a,0x0d,0x2d,0xe5,0x7a,0x9f,0x93,0xc9,0x9c,0xef,
    0xa0,0xe0,0x3b,0x4d,0xae,0x2a,0xf5,0xb0,0xc8,0xeb,0xbb,0x3c,0x83,0x53,0x99,0x61,
    0x17,0x2b,0x04,0x7e,0xba,0x77,0xd6,0x26,0xe1,0x69,0x14,0x63,0x55,0x21,0x0c,0x7d,
]

_AES_RCON = [0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80,0x1b,0x36]


def _aes_xtime(a: int) -> int:
    return ((a << 1) ^ 0x11b) & 0xff if a & 0x80 else (a << 1) & 0xff


def _aes_mul(a: int, b: int) -> int:
    p = 0
    for _ in range(8):
        if b & 1:
            p ^= a
        hi = a & 0x80
        a = (a << 1) & 0xff
        if hi:
            a ^= 0x1b
        b >>= 1
    return p


def _aes_key_expansion(key: bytes) -> List[List[int]]:
    nk = len(key) // 4
    nr = nk + 6
    w: List[List[int]] = []

    for i in range(nk):
        w.append([key[4*i], key[4*i+1], key[4*i+2], key[4*i+3]])

    for i in range(nk, 4 * (nr + 1)):
        temp = list(w[i - 1])
        if i % nk == 0:
            temp = [_AES_SBOX[b] for b in [temp[1], temp[2], temp[3], temp[0]]]
            temp[0] ^= _AES_RCON[i // nk - 1]
        elif nk > 6 and i % nk == 4:
            temp = [_AES_SBOX[b] for b in temp]
        w.append([w[i - nk][j] ^ temp[j] for j in range(4)])

    round_keys: List[List[int]] = []
    for r in range(nr + 1):
        rk: List[int] = []
        for c in range(4):
            rk.extend(w[4 * r + c])
        round_keys.append(rk)
    return round_keys


def _aes_sub_bytes(state: List[List[int]]) -> List[List[int]]:
    return [[_AES_SBOX[state[r][c]] for c in range(4)] for r in range(4)]


def _aes_inv_sub_bytes(state: List[List[int]]) -> List[List[int]]:
    return [[_AES_INV_SBOX[state[r][c]] for c in range(4)] for r in range(4)]


def _aes_shift_rows(state: List[List[int]]) -> List[List[int]]:
    s = [row[:] for row in state]
    s[0][1], s[1][1], s[2][1], s[3][1] = s[1][1], s[2][1], s[3][1], s[0][1]
    s[0][2], s[1][2], s[2][2], s[3][2] = s[2][2], s[3][2], s[0][2], s[1][2]
    s[0][3], s[1][3], s[2][3], s[3][3] = s[3][3], s[0][3], s[1][3], s[2][3]
    return s


def _aes_inv_shift_rows(state: List[List[int]]) -> List[List[int]]:
    s = [row[:] for row in state]
    s[1][1], s[2][1], s[3][1], s[0][1] = s[0][1], s[1][1], s[2][1], s[3][1]
    s[2][2], s[3][2], s[0][2], s[1][2] = s[0][2], s[1][2], s[2][2], s[3][2]
    s[3][3], s[0][3], s[1][3], s[2][3] = s[0][3], s[1][3], s[2][3], s[3][3]
    return s


def _aes_mix_columns(state: List[List[int]]) -> List[List[int]]:
    result = [[0]*4 for _ in range(4)]
    for c in range(4):
        result[0][c] = _aes_mul(2, state[0][c]) ^ _aes_mul(3, state[1][c]) ^ state[2][c] ^ state[3][c]
        result[1][c] = state[0][c] ^ _aes_mul(2, state[1][c]) ^ _aes_mul(3, state[2][c]) ^ state[3][c]
        result[2][c] = state[0][c] ^ state[1][c] ^ _aes_mul(2, state[2][c]) ^ _aes_mul(3, state[3][c])
        result[3][c] = _aes_mul(3, state[0][c]) ^ state[1][c] ^ state[2][c] ^ _aes_mul(2, state[3][c])
    return result


def _aes_inv_mix_columns(state: List[List[int]]) -> List[List[int]]:
    result = [[0]*4 for _ in range(4)]
    for c in range(4):
        result[0][c] = _aes_mul(14, state[0][c]) ^ _aes_mul(11, state[1][c]) ^ _aes_mul(13, state[2][c]) ^ _aes_mul(9, state[3][c])
        result[1][c] = _aes_mul(9, state[0][c]) ^ _aes_mul(14, state[1][c]) ^ _aes_mul(11, state[2][c]) ^ _aes_mul(13, state[3][c])
        result[2][c] = _aes_mul(13, state[0][c]) ^ _aes_mul(9, state[1][c]) ^ _aes_mul(14, state[2][c]) ^ _aes_mul(11, state[3][c])
        result[3][c] = _aes_mul(11, state[0][c]) ^ _aes_mul(13, state[1][c]) ^ _aes_mul(9, state[2][c]) ^ _aes_mul(14, state[3][c])
    return result


def _aes_add_round_key(state: List[List[int]], rk: List[int]) -> List[List[int]]:
    result = [[0]*4 for _ in range(4)]
    for c in range(4):
        for r in range(4):
            result[r][c] = state[r][c] ^ rk[4*c + r]
    return result


def _aes_bytes_to_state(data: bytes) -> List[List[int]]:
    state = [[0]*4 for _ in range(4)]
    for c in range(4):
        for r in range(4):
            state[r][c] = data[4*c + r]
    return state


def _aes_state_to_bytes(state: List[List[int]]) -> bytes:
    result = bytearray(16)
    for c in range(4):
        for r in range(4):
            result[4*c + r] = state[r][c]
    return bytes(result)


class AesCryptoCipher:
    """AES cipher (FIPS 197)"""
    block_size: int = 16
    key_sizes: list = [16, 24, 32]
    modes: list = ["ecb", "cbc", "ctr", "xts"]

    def __init__(self) -> None:
        self._round_keys: Optional[List[List[int]]] = None
        self._nr: int = 0

    def _setup(self, key: bytes) -> None:
        self._round_keys = _aes_key_expansion(key)
        self._nr = len(key) // 4 + 6

    def _encrypt_block(self, block: bytes) -> bytes:
        assert self._round_keys is not None
        state = _aes_bytes_to_state(block)
        state = _aes_add_round_key(state, self._round_keys[0])
        for rnd in range(1, self._nr):
            state = _aes_sub_bytes(state)
            state = _aes_shift_rows(state)
            state = _aes_mix_columns(state)
            state = _aes_add_round_key(state, self._round_keys[rnd])
        state = _aes_sub_bytes(state)
        state = _aes_shift_rows(state)
        state = _aes_add_round_key(state, self._round_keys[self._nr])
        return _aes_state_to_bytes(state)

    def _decrypt_block(self, block: bytes) -> bytes:
        assert self._round_keys is not None
        state = _aes_bytes_to_state(block)
        state = _aes_add_round_key(state, self._round_keys[self._nr])
        for rnd in range(self._nr - 1, 0, -1):
            state = _aes_inv_shift_rows(state)
            state = _aes_inv_sub_bytes(state)
            state = _aes_add_round_key(state, self._round_keys[rnd])
            state = _aes_inv_mix_columns(state)
        state = _aes_inv_shift_rows(state)
        state = _aes_inv_sub_bytes(state)
        state = _aes_add_round_key(state, self._round_keys[0])
        return _aes_state_to_bytes(state)

    def encrypt(self, key: bytes, plaintext: bytes) -> bytes:
        self._setup(key)
        assert len(plaintext) % 16 == 0, "Plaintext must be block-aligned"
        out = bytearray()
        for i in range(0, len(plaintext), 16):
            out.extend(self._encrypt_block(plaintext[i:i+16]))
        return bytes(out)

    def decrypt(self, key: bytes, ciphertext: bytes) -> bytes:
        self._setup(key)
        assert len(ciphertext) % 16 == 0, "Ciphertext must be block-aligned"
        out = bytearray()
        for i in range(0, len(ciphertext), 16):
            out.extend(self._decrypt_block(ciphertext[i:i+16]))
        return bytes(out)


# ---------------------------------------------------------------------------
# DES Implementation (FIPS 46-3) – simplified for brevity, functional
# ---------------------------------------------------------------------------

class DesCryptoCipher:
    """DES cipher (FIPS 46-3)"""
    block_size: int = 8
    key_sizes: list = [8]
    modes: list = ["ecb", "cbc"]

    _IP = [58,50,42,34,26,18,10,2,60,52,44,36,28,20,12,4,
           62,54,46,38,30,22,14,6,64,56,48,40,32,24,16,8,
           57,49,41,33,25,17,9,1,59,51,43,35,27,19,11,3,
           61,53,45,37,29,21,13,5,63,55,47,39,31,23,15,7]

    _FP = [40,8,48,16,56,24,64,32,39,7,47,15,55,23,63,31,
           38,6,46,14,54,22,62,30,37,5,45,13,53,21,61,29,
           36,4,44,12,52,20,60,28,35,3,43,11,51,19,59,27,
           34,2,42,10,50,18,58,26,33,1,41,9,49,17,57,25]

    _E = [32,1,2,3,4,5,4,5,6,7,8,9,8,9,10,11,12,13,
          12,13,14,15,16,17,16,17,18,19,20,21,20,21,22,23,24,25,
          24,25,26,27,28,29,28,29,30,31,32,1]

    _P = [16,7,20,21,29,12,28,17,1,15,23,26,5,18,31,10,
          2,8,24,14,32,27,3,9,19,13,30,6,22,11,4,25]

    _SBOX = [
        [[14,4,13,1,2,15,11,8,3,10,6,12,5,9,0,7],[0,15,7,4,14,2,13,1,10,6,12,11,9,5,3,8],[4,1,14,8,13,6,2,11,15,12,9,7,3,10,5,0],[15,12,8,2,4,9,1,7,5,11,3,14,10,0,6,13]],
        [[15,1,8,14,6,11,3,4,9,7,2,13,12,0,5,10],[3,13,4,7,15,2,8,14,12,0,1,10,6,9,11,5],[0,14,7,11,10,4,13,1,5,8,12,6,9,3,2,15],[13,8,10,1,3,15,4,2,11,6,7,12,0,5,14,9]],
        [[10,0,9,14,6,3,15,5,1,13,12,7,11,4,2,8],[13,7,0,9,3,4,6,10,2,8,5,14,12,11,15,1],[13,6,4,9,8,15,3,0,11,1,2,12,5,10,14,7],[1,10,13,0,6,9,8,7,4,15,14,3,11,5,2,12]],
        [[7,13,14,3,0,6,9,10,1,2,8,5,11,12,4,15],[13,8,11,5,6,15,0,3,4,7,2,12,1,10,14,9],[10,6,9,0,12,11,7,13,15,1,3,14,5,2,8,4],[3,15,0,6,10,1,13,8,9,4,5,11,12,7,2,14]],
        [[2,12,4,1,7,10,11,6,8,5,3,15,13,0,14,9],[14,11,2,12,4,7,13,1,5,0,15,10,3,9,8,6],[4,2,1,11,10,13,7,8,15,9,12,5,6,3,0,14],[11,8,12,7,1,14,2,13,6,15,0,9,10,4,5,3]],
        [[12,1,10,15,9,2,6,8,0,13,3,4,14,7,5,11],[10,15,4,2,7,12,9,5,6,1,13,14,0,11,3,8],[9,14,15,5,2,8,12,3,7,0,4,10,1,13,11,6],[4,3,2,12,9,5,15,10,11,14,1,7,6,0,8,13]],
        [[4,11,2,14,15,0,8,13,3,12,9,7,5,10,6,1],[13,0,11,7,4,9,1,10,14,3,5,12,2,15,8,6],[1,4,11,13,12,3,7,14,10,15,6,8,0,5,9,2],[6,11,13,8,1,4,10,7,9,5,0,15,14,2,3,12]],
        [[13,2,8,4,6,15,11,1,10,9,3,14,5,0,12,7],[1,15,13,8,10,3,7,4,12,5,6,11,0,14,9,2],[7,11,4,1,9,12,14,2,0,6,10,13,15,3,5,8],[2,1,14,7,4,10,8,13,15,12,9,0,3,5,6,11]],
    ]

    _PC1 = [57,49,41,33,25,17,9,1,58,50,42,34,26,18,10,2,59,51,43,35,27,19,11,3,60,52,44,36,63,55,47,39,31,23,15,7,62,54,46,38,30,22,14,6,61,53,45,37,29,21,13,5,28,20,12,4]

    _PC2 = [14,17,11,24,1,5,3,28,15,6,21,10,23,19,12,4,26,8,16,7,27,20,13,2,41,52,31,37,47,55,30,40,51,45,33,48,44,49,39,56,34,53,46,42,50,36,29,32]

    _SHIFTS = [1,1,2,2,2,2,2,2,1,2,2,2,2,2,2,1]

    def _permute(self, data: bytes, table: list, nbits: int) -> int:
        result = 0
        for pos in table:
            byte_idx = (pos - 1) // 8
            bit_idx = (pos - 1) % 8
            bit = (data[byte_idx] >> (7 - bit_idx)) & 1
            result = (result << 1) | bit
        return result

    def _bytes_to_bits(self, data: bytes) -> list:
        bits = []
        for byte in data:
            for i in range(7, -1, -1):
                bits.append((byte >> i) & 1)
        return bits

    def _bits_to_bytes(self, bits: list) -> bytes:
        result = bytearray()
        for i in range(0, len(bits), 8):
            byte = 0
            for j in range(8):
                if i + j < len(bits):
                    byte = (byte << 1) | bits[i + j]
                else:
                    byte <<= 1
            result.append(byte)
        return bytes(result)

    def _generate_subkeys(self, key: bytes) -> list:
        key_int = int.from_bytes(key, 'big')
        pc1 = 0
        for pos in self._PC1:
            pc1 = (pc1 << 1) | ((key_int >> (64 - pos)) & 1)

        c = (pc1 >> 28) & 0x0FFFFFFF
        d = pc1 & 0x0FFFFFFF

        subkeys = []
        for round_num in range(16):
            shift = self._SHIFTS[round_num]
            c = ((c << shift) & 0x0FFFFFFF) | (c >> (28 - shift))
            d = ((d << shift) & 0x0FFFFFFF) | (d >> (28 - shift))

            cd = (c << 28) | d
            subkey = 0
            for pos in self._PC2:
                subkey = (subkey << 1) | ((cd >> (56 - pos)) & 1)
            subkeys.append(subkey)
        return subkeys

    def _feistel(self, right: int, subkey: int) -> int:
        expanded = 0
        for pos in self._E:
            expanded = (expanded << 1) | ((right >> (32 - pos)) & 1)

        xored = expanded ^ subkey
        result = 0
        for i in range(8):
            chunk = (xored >> (42 - 6*i)) & 0x3F
            row = ((chunk >> 5) & 1) * 2 + (chunk & 1)
            col = (chunk >> 1) & 0xF
            val = self._SBOX[i][row][col]
            result = (result << 4) | val

        permuted = 0
        for pos in self._P:
            permuted = (permuted << 1) | ((result >> (32 - pos)) & 1)
        return permuted

    def _des_block(self, block: bytes, subkeys: list, decrypt: bool = False) -> bytes:
        block_int = int.from_bytes(block, 'big')
        permuted = 0
        for pos in self._IP:
            permuted = (permuted << 1) | ((block_int >> (64 - pos)) & 1)

        left = (permuted >> 32) & 0xFFFFFFFF
        right = permuted & 0xFFFFFFFF

        keys = list(reversed(subkeys)) if decrypt else subkeys

        for i in range(16):
            new_right = left ^ self._feistel(right, keys[i])
            left = right
            right = new_right

        combined = (right << 32) | left
        result = 0
        for pos in self._FP:
            result = (result << 1) | ((combined >> (64 - pos)) & 1)

        return result.to_bytes(8, 'big')

    def encrypt(self, key: bytes, plaintext: bytes) -> bytes:
        subkeys = self._generate_subkeys(key)
        out = bytearray()
        for i in range(0, len(plaintext), 8):
            block = plaintext[i:i+8]
            if len(block) < 8:
                block = block + b'\x00' * (8 - len(block))
            out.extend(self._des_block(block, subkeys, decrypt=False))
        return bytes(out)

    def decrypt(self, key: bytes, ciphertext: bytes) -> bytes:
        subkeys = self._generate_subkeys(key)
        out = bytearray()
        for i in range(0, len(ciphertext), 8):
            out.extend(self._des_block(ciphertext[i:i+8], subkeys, decrypt=True))
        return bytes(out)


# ---------------------------------------------------------------------------
# ChaCha20 Implementation (RFC 8439)
# ---------------------------------------------------------------------------

class Chacha20CryptoCipher:
    """ChaCha20 stream cipher (RFC 8439)"""
    block_size: int = 1
    key_sizes: list = [16, 32]
    modes: list = ["stream"]

    @staticmethod
    def _quarter_round(state: list, a: int, b: int, c: int, d: int) -> None:
        state[a] = (state[a] + state[b]) & 0xFFFFFFFF
        state[d] ^= state[a]
        state[d] = ((state[d] << 16) | (state[d] >> 16)) & 0xFFFFFFFF

        state[c] = (state[c] + state[d]) & 0xFFFFFFFF
        state[b] ^= state[c]
        state[b] = ((state[b] << 12) | (state[b] >> 20)) & 0xFFFFFFFF

        state[a] = (state[a] + state[b]) & 0xFFFFFFFF
        state[d] ^= state[a]
        state[d] = ((state[d] << 8) | (state[d] >> 24)) & 0xFFFFFFFF

        state[c] = (state[c] + state[d]) & 0xFFFFFFFF
        state[b] ^= state[c]
        state[b] = ((state[b] << 7) | (state[b] >> 25)) & 0xFFFFFFFF

    @staticmethod
    def _chacha20_block(key: bytes, counter: int, nonce: bytes) -> bytes:
        if len(key) == 16:
            k = key + key
        else:
            k = key

        constants = [0x61707865, 0x3320646e, 0x79622d32, 0x6b206574]
        state = constants + list(struct.unpack('<4I', k)) + [counter] + list(struct.unpack('<3I', nonce))

        working = list(state)
        for _ in range(10):
            Chacha20CryptoCipher._quarter_round(working, 0, 4, 8, 12)
            Chacha20CryptoCipher._quarter_round(working, 1, 5, 9, 13)
            Chacha20CryptoCipher._quarter_round(working, 2, 6, 10, 14)
            Chacha20CryptoCipher._quarter_round(working, 3, 7, 11, 15)
            Chacha20CryptoCipher._quarter_round(working, 0, 5, 10, 15)
            Chacha20CryptoCipher._quarter_round(working, 1, 6, 11, 12)
            Chacha20CryptoCipher._quarter_round(working, 2, 7, 8, 13)
            Chacha20CryptoCipher._quarter_round(working, 3, 4, 9, 14)

        result = [(working[i] + state[i]) & 0xFFFFFFFF for i in range(16)]
        return struct.pack('<16I', *result)

    def encrypt(self, key: bytes, plaintext: bytes) -> bytes:
        nonce = os.urandom(12)
        counter = 1
        out = bytearray()
        for i in range(0, len(plaintext), 64):
            keystream = Chacha20CryptoCipher._chacha20_block(key, counter, nonce)
            block = plaintext[i:i+64]
            for j in range(len(block)):
                out.append(block[j] ^ keystream[j])
            counter += 1
        return nonce + bytes(out)

    def decrypt(self, key: bytes, ciphertext: bytes) -> bytes:
        nonce = ciphertext[:12]
        data = ciphertext[12:]
        counter = 1
        out = bytearray()
        for i in range(0, len(data), 64):
            keystream = Chacha20CryptoCipher._chacha20_block(key, counter, nonce)
            block = data[i:i+64]
            for j in range(len(block)):
                out.append(block[j] ^ keystream[j])
            counter += 1
        return bytes(out)


# ---------------------------------------------------------------------------
# SHA-256 Implementation (FIPS 180-4)
# ---------------------------------------------------------------------------

class Sha256Hash:
    """SHA-256 hash (FIPS 180-4)"""
    digest_size: int = 32
    block_size: int = 64

    _K = [
        0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
        0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
        0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
        0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
        0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
        0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
        0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
        0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2,
    ]

    def __init__(self) -> None:
        self.init()

    def init(self) -> None:
        self._h = [
            0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,
            0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19,
        ]
        self._buffer = b''
        self._length = 0

    def _pad(self) -> bytes:
        msg = self._buffer
        msg_len = len(msg)
        msg += b'\x80'
        msg += b'\x00' * ((55 - msg_len) % 64)
        msg += struct.pack('>Q', self._length * 8)
        return msg

    def _process_block(self, block: bytes) -> None:
        w = list(struct.unpack('>16I', block))
        for i in range(16, 64):
            s0 = ((w[i-15] >> 7) | (w[i-15] << 25)) ^ ((w[i-15] >> 18) | (w[i-15] << 14)) ^ (w[i-15] >> 3)
            s1 = ((w[i-2] >> 17) | (w[i-2] << 15)) ^ ((w[i-2] >> 19) | (w[i-2] << 13)) ^ (w[i-2] >> 10)
            w.append((w[i-16] + s0 + w[i-7] + s1) & 0xFFFFFFFF)

        a, b, c, d, e, f, g, h = self._h

        for i in range(64):
            S1 = ((e >> 6) | (e << 26)) ^ ((e >> 11) | (e << 21)) ^ ((e >> 25) | (e << 7))
            ch = (e & f) ^ (~e & g) & 0xFFFFFFFF
            temp1 = (h + S1 + ch + self._K[i] + w[i]) & 0xFFFFFFFF
            S0 = ((a >> 2) | (a << 30)) ^ ((a >> 13) | (a << 19)) ^ ((a >> 22) | (a << 10))
            maj = (a & b) ^ (a & c) ^ (b & c)
            temp2 = (S0 + maj) & 0xFFFFFFFF

            h = g
            g = f
            f = e
            e = (d + temp1) & 0xFFFFFFFF
            d = c
            c = b
            b = a
            a = (temp1 + temp2) & 0xFFFFFFFF

        self._h = [(self._h[i] + val) & 0xFFFFFFFF for i, val in enumerate([a, b, c, d, e, f, g, h])]

    def update(self, data: bytes) -> None:
        self._length += len(data)
        self._buffer += data
        while len(self._buffer) >= 64:
            self._process_block(self._buffer[:64])
            self._buffer = self._buffer[64:]

    def final(self) -> bytes:
        padded = self._pad()
        for i in range(0, len(padded), 64):
            self._process_block(padded[i:i+64])
        return struct.pack('>8I', *self._h)


# ---------------------------------------------------------------------------
# MD5 Implementation (RFC 1321)
# ---------------------------------------------------------------------------

class Md5Hash:
    """MD5 hash (RFC 1321)"""
    digest_size: int = 16
    block_size: int = 64

    _S = [
        7,12,17,22,7,12,17,22,7,12,17,22,7,12,17,22,
        5,9,14,20,5,9,14,20,5,9,14,20,5,9,14,20,
        4,11,16,23,4,11,16,23,4,11,16,23,4,11,16,23,
        6,10,15,21,6,10,15,21,6,10,15,21,6,10,15,21,
    ]

    _K = [
        0xd76aa478,0xe8c7b756,0x242070db,0xc1bdceee,
        0xf57c0faf,0x4787c62a,0xa8304613,0xfd469501,
        0x698098d8,0x8b44f7af,0xffff5bb1,0x895cd7be,
        0x6b901122,0xfd987193,0xa679438e,0x49b40821,
        0xf61e2562,0xc040b340,0x265e5a51,0xe9b6c7aa,
        0xd62f105d,0x02441453,0xd8a1e681,0xe7d3fbc8,
        0x21e1cde6,0xc33707d6,0xf4d50d87,0x455a14ed,
        0xa9e3e905,0xfcefa3f8,0x676f02d9,0x8d2a4c8a,
        0xfffa3942,0x8771f681,0x6d9d6122,0xfde5380c,
        0xa4beea44,0x4bdecfa9,0xf6bb4b60,0xbebfbc70,
        0x289b7ec6,0xeaa127fa,0xd4ef3085,0x04881d05,
        0xd9d4d039,0xe6db99e5,0x1fa27cf8,0xc4ac5665,
        0xf4292244,0x432aff97,0xab9423a7,0xfc93a039,
        0x655b59c3,0x8f0ccc92,0xffeff47d,0x85845dd1,
        0x6fa87e4f,0xfe2ce6e0,0xa3014314,0x4e0811a1,
        0xf7537e82,0xbd3af235,0x2ad7d2bb,0xeb86d391,
    ]

    def __init__(self) -> None:
        self.init()

    def init(self) -> None:
        self._h = [0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476]
        self._buffer = b''
        self._length = 0

    def _pad(self) -> bytes:
        msg = self._buffer
        msg_len = len(msg)
        msg += b'\x80'
        msg += b'\x00' * ((55 - msg_len) % 64)
        msg += struct.pack('<Q', self._length * 8)
        return msg

    def _process_block(self, block: bytes) -> None:
        M = list(struct.unpack('<16I', block))
        a, b, c, d = self._h

        for i in range(64):
            if i < 16:
                f = (b & c) | (~b & d) & 0xFFFFFFFF
                g = i
            elif i < 32:
                f = (d & b) | (~d & c) & 0xFFFFFFFF
                g = (5*i + 1) % 16
            elif i < 48:
                f = b ^ c ^ d
                g = (3*i + 5) % 16
            else:
                f = c ^ (b | ~d) & 0xFFFFFFFF
                g = (7*i) % 16

            temp = (a + f + self._K[i] + M[g]) & 0xFFFFFFFF
            temp = ((temp << self._S[i]) | (temp >> (32 - self._S[i]))) & 0xFFFFFFFF
            temp = (temp + b) & 0xFFFFFFFF
            a, b, c, d = d, temp, b, c

        self._h = [(self._h[0] + a) & 0xFFFFFFFF, (self._h[1] + b) & 0xFFFFFFFF,
                    (self._h[2] + c) & 0xFFFFFFFF, (self._h[3] + d) & 0xFFFFFFFF]

    def update(self, data: bytes) -> None:
        self._length += len(data)
        self._buffer += data
        while len(self._buffer) >= 64:
            self._process_block(self._buffer[:64])
            self._buffer = self._buffer[64:]

    def final(self) -> bytes:
        padded = self._pad()
        for i in range(0, len(padded), 64):
            self._process_block(padded[i:i+64])
        return struct.pack('<4I', *self._h)


# ---------------------------------------------------------------------------
# SHA3-256 Implementation (FIPS 202)
# ---------------------------------------------------------------------------

class Sha3_256Hash:
    """SHA3-256 hash (FIPS 202)"""
    digest_size: int = 32
    block_size: int = 136

    _RC = [
        0x0000000000000001,0x0000000000008082,0x800000000000808a,
        0x8000000080008000,0x000000000000808b,0x0000000080000001,
        0x8000000080008081,0x8000000000008009,0x000000000000008a,
        0x0000000000000088,0x0000000080008009,0x000000008000000a,
        0x000000008000808b,0x800000000000008b,0x8000000000008089,
        0x8000000000008003,0x8000000000008002,0x8000000000000080,
        0x000000000000800a,0x800000008000000a,0x8000000080008081,
        0x8000000000008080,0x0000000080000001,0x8000000080008008,
    ]

    _ROT = [
        [0,1,62,28,27],[36,44,6,55,20],[3,10,43,25,39],
        [41,45,15,21,8],[18,2,61,56,14],
    ]

    def __init__(self) -> None:
        self.init()

    def init(self) -> None:
        self._state = [[[0]*5 for _ in range(5)] for _ in range(5)]
        self._buffer = b''
        self._length = 0

    def _to_lanes(self, data: bytes) -> list:
        lanes = []
        for i in range(25):
            val = int.from_bytes(data[8*i:8*i+8], 'little')
            lanes.append(val)
        return lanes

    def _from_lanes(self, lanes: list) -> bytes:
        result = bytearray()
        for v in lanes:
            result.extend(v.to_bytes(8, 'little'))
        return bytes(result)

    def _keccak_f(self, A: list) -> list:
        state = list(A)
        for round_idx in range(24):
            C = [0]*5
            for x in range(5):
                C[x] = state[x] ^ state[x+5] ^ state[x+10] ^ state[x+15] ^ state[x+20]

            D = [0]*5
            for x in range(5):
                D[x] = C[(x-1) % 5] ^ ((C[(x+1) % 5] << 1) | (C[(x+1) % 5] >> 63))

            for y in range(5):
                for x in range(5):
                    state[y*5+x] ^= D[x]

            B = [0]*25
            for y in range(5):
                for x in range(5):
                    idx = y*5+x
                    rot = self._ROT[y][x]
                    B[y*5+x] = ((state[y*5+x] << rot) | (state[y*5+x] >> (64-rot))) & 0xFFFFFFFFFFFFFFFF

            for y in range(5):
                for x in range(5):
                    state[y*5+x] = B[y*5+x] ^ (~B[y*5+((x+1)%5)] & B[y*5+((x+2)%5)])

            state[0] ^= self._RC[round_idx]

        return state

    def _process_block(self, block: bytes) -> None:
        lanes = self._to_lanes(block)
        for i in range(25):
            self._state[i//5][i%5] ^= lanes[i]
        flat = [self._state[i//5][i%5] for i in range(25)]
        flat = self._keccak_f(flat)
        for i in range(25):
            self._state[i//5][i%5] = flat[i]

    def update(self, data: bytes) -> None:
        self._length += len(data)
        self._buffer += data
        while len(self._buffer) >= self.block_size:
            self._process_block(self._buffer[:self.block_size])
            self._buffer = self._buffer[self.block_size:]

    def final(self) -> bytes:
        msg = self._buffer
        msg += b'\x06'  # SHA3-256 domain separator
        msg += b'\x00' * ((self.block_size - 1 - len(msg)) % self.block_size)
        msg = msg[:-1] + bytes([msg[-1] | 0x80])
        self._process_block(msg)

        out = bytearray()
        while len(out) < self.digest_size:
            flat = [self._state[i//5][i%5] for i in range(25)]
            out.extend(self._from_lanes(flat))
        return bytes(out[:self.digest_size])


# ---------------------------------------------------------------------------
# AES-GCM Implementation (NIST SP 800-38D)
# ---------------------------------------------------------------------------

class AesGcmAead:
    """AES-GCM AEAD (NIST SP 800-38D)"""
    key_sizes: list = [16, 24, 32]
    iv_size: int = 12
    tag_size: int = 16

    @staticmethod
    def _ghash(H: bytes, data: bytes) -> bytes:
        def _gf_mult(a: int, b: int) -> int:
            p = 0
            for _ in range(128):
                if b & 1:
                    p ^= a
                hi = a & 1
                a >>= 1
                if hi:
                    a ^= 0xe1000000000000000000000000000000
                b >>= 1
            return p

        X = 0
        H_int = int.from_bytes(H, 'big')
        for i in range(0, len(data), 16):
            block = data[i:i+16]
            if len(block) < 16:
                block = block + b'\x00' * (16 - len(block))
            X ^= int.from_bytes(block, 'big')
            X = _gf_mult(X, H_int)
        return X.to_bytes(16, 'big')

    def _inc32(self, IV: bytes) -> bytes:
        val = int.from_bytes(IV, 'big') + 1
        return val.to_bytes(16, 'big')

    def _get_counter(self, J0: bytes, counter: int) -> bytes:
        val = int.from_bytes(J0, 'big')
        val = (val & 0xFFFFFFFF00000000) | ((val & 0xFFFFFFFF) + counter)
        return val.to_bytes(16, 'big')

    def _gctr(self, key: bytes, ICB: bytes, data: bytes) -> bytes:
        if not data:
            return b''
        aes = AesCryptoCipher()
        aes._setup(key)
        out = bytearray()
        CB = ICB
        for i in range(0, len(data), 16):
            block = data[i:i+16]
            enc = aes._encrypt_block(CB)
            for j in range(len(block)):
                out.append(block[j] ^ enc[j])
            CB = self._inc32(CB)
        return bytes(out)

    def encrypt(self, key: bytes, plaintext: bytes, aad: bytes, iv: bytes) -> Tuple[bytes, bytes]:
        aes = AesCryptoCipher()
        aes._setup(key)
        H = aes._encrypt_block(b'\x00' * 16)

        if len(iv) == 12:
            J0 = iv + b'\x00\x00\x00\x01'
        else:
            J0 = self._ghash(H, iv + b'\x00' * (16 - len(iv) % 16 if len(iv) % 16 else 0))
            J0 = self._ghash(H, iv)

        C = self._gctr(key, self._inc32(J0), plaintext)

        u = (128 * math.ceil(len(C) / 128)) - len(C) * 8 if C else 0
        v = (128 * math.ceil(len(aad) / 128)) - len(aad) * 8 if aad else 0

        aad_padded = aad + b'\x00' * (u // 8)
        C_padded = C + b'\x00' * (v // 8)

        len_block = len(aad).to_bytes(8, 'big') + len(C).to_bytes(8, 'big')
        S = self._ghash(H, aad_padded + C_padded + len_block)

        tag = self._gctr(key, J0, S)
        return C, tag[:16]

    def decrypt(self, key: bytes, ciphertext: bytes, aad: bytes, iv: bytes, tag: bytes) -> bytes:
        aes = AesCryptoCipher()
        aes._setup(key)
        H = aes._encrypt_block(b'\x00' * 16)

        if len(iv) == 12:
            J0 = iv + b'\x00\x00\x00\x01'
        else:
            J0 = self._ghash(H, iv)

        P = self._gctr(key, self._inc32(J0), ciphertext)

        u = (128 * math.ceil(len(P) / 128)) - len(P) * 8 if P else 0
        v = (128 * math.ceil(len(aad) / 128)) - len(aad) * 8 if aad else 0

        aad_padded = aad + b'\x00' * (u // 8)
        P_padded = P + b'\x00' * (v // 8)

        len_block = len(aad).to_bytes(8, 'big') + len(ciphertext).to_bytes(8, 'big')
        S = self._ghash(H, aad_padded + P_padded + len_block)

        expected_tag = self._gctr(key, J0, S)[:16]
        if tag != expected_tag:
            raise ValueError("GCM authentication tag mismatch")
        return P


# ---------------------------------------------------------------------------
# RNG Implementations
# ---------------------------------------------------------------------------

class ChaCha20Rng:
    """ChaCha20-based RNG"""
    def __init__(self) -> None:
        self._key = os.urandom(32)
        self._counter = 0
        self._nonce = os.urandom(12)

    def generate(self, size: int) -> bytes:
        out = bytearray()
        while len(out) < size:
            block = Chacha20CryptoCipher._chacha20_block(self._key, self._counter, self._nonce)
            out.extend(block)
            self._counter += 1
        return bytes(out[:size])

    def seed(self, seed_bytes: bytes) -> None:
        self._key = hashlib.sha256(seed_bytes + self._key).digest()
        self._counter = 0
        self._nonce = os.urandom(12)


class MrdRandom:
    """MRD (Modified Random Device) RNG – deterministic PRNG seeded from OS entropy"""
    def __init__(self) -> None:
        self._state = bytearray(os.urandom(64))
        self._pos = 0

    def _step(self) -> None:
        for i in range(64):
            self._state[i] = (self._state[i] * 13 + 7) & 0xFF
        h = hashlib.sha256(bytes(self._state)).digest()
        self._state = bytearray(h + self._state[:32])

    def generate(self, size: int) -> bytes:
        out = bytearray()
        while len(out) < size:
            if self._pos >= len(self._state):
                self._step()
                self._pos = 0
            out.append(self._state[self._pos])
            self._pos += 1
        return bytes(out[:size])

    def seed(self, seed_bytes: bytes) -> None:
        self._state = bytearray(hashlib.sha512(seed_bytes).digest())
        self._pos = 0


# ---------------------------------------------------------------------------
# Algorithm Registration
# ---------------------------------------------------------------------------

def crypto_register_alg(alg: CryptoAlg) -> bool:
    """Register crypto algorithm"""
    if alg.name in _alg_registry:
        return False
    _alg_registry[alg.name] = alg
    return True


def crypto_unregister_alg(name: str) -> bool:
    """Unregister crypto algorithm"""
    if name not in _alg_registry:
        return False
    del _alg_registry[name]
    return True


def crypto_get_alg(name: str) -> Optional[CryptoAlg]:
    """Get algorithm by name"""
    return _alg_registry.get(name)


def crypto_list_algs() -> List[CryptoAlg]:
    """List registered algorithms"""
    return list(_alg_registry.values())


# ---------------------------------------------------------------------------
# TFM Operations
# ---------------------------------------------------------------------------

def crypto_alloc_tfm(alg_name: str, tfm_type: str = "cipher") -> CryptoTFM:
    """Allocate transformation - like crypto_alloc_tfm()"""
    alg = crypto_get_alg(alg_name)
    if alg is None:
        raise ValueError(f"Algorithm '{alg_name}' not registered")
    return CryptoTFM(
        name=alg_name,
        alg=alg,
        state="init",
        _created_at=time.time(),
    )


def crypto_free_tfm(tfm: CryptoTFM) -> None:
    """Free transformation"""
    tfm.state = "final"
    tfm.key = b''
    tfm.iv = b''


def crypto_set_key(tfm: CryptoTFM, key: bytes) -> None:
    """Set key for cipher TFM"""
    if tfm.alg.key_sizes and len(key) not in tfm.alg.key_sizes:
        raise ValueError(f"Invalid key size {len(key)} for {tfm.name}")
    tfm.key = key
    tfm.state = "ready"


def crypto_set_iv(tfm: CryptoTFM, iv: bytes) -> None:
    """Set IV for cipher TFM"""
    if tfm.alg.iv_size and len(iv) != tfm.alg.iv_size:
        raise ValueError(f"Invalid IV size {len(iv)} for {tfm.name}")
    tfm.iv = iv


# ---------------------------------------------------------------------------
# Cipher Operations
# ---------------------------------------------------------------------------

def crypto_encrypt(tfm: CryptoTFM, plaintext: bytes) -> bytes:
    """Encrypt data - like crypto_cipher_encrypt_one()"""
    if tfm.state != "ready":
        raise ValueError(f"TFM not ready (state={tfm.state})")
    impl = tfm.alg._impl
    if impl is None:
        raise ValueError(f"No implementation for {tfm.name}")

    mode = tfm.alg.cipher_mode

    if isinstance(impl, Chacha20CryptoCipher):
        return impl.encrypt(tfm.key, plaintext)

    if isinstance(impl, DesCryptoCipher):
        if mode == CRYPTO_CIPHER_CBC:
            return _cbc_encrypt(impl, tfm.key, plaintext, tfm.iv)
        return impl.encrypt(tfm.key, plaintext)

    if isinstance(impl, AesCryptoCipher):
        if mode == CRYPTO_CIPHER_CBC:
            return _cbc_encrypt(impl, tfm.key, plaintext, tfm.iv)
        elif mode == CRYPTO_CIPHER_CTR:
            return _ctr_crypt(impl, tfm.key, plaintext, tfm.iv)
        elif mode == CRYPTO_CIPHER_XTS:
            return _xts_crypt(impl, tfm.key, plaintext, tfm.iv, encrypt=True)
        return impl.encrypt(tfm.key, plaintext)

    return impl.encrypt(tfm.key, plaintext)


def crypto_decrypt(tfm: CryptoTFM, ciphertext: bytes) -> bytes:
    """Decrypt data - like crypto_cipher_decrypt_one()"""
    if tfm.state != "ready":
        raise ValueError(f"TFM not ready (state={tfm.state})")
    impl = tfm.alg._impl
    if impl is None:
        raise ValueError(f"No implementation for {tfm.name}")

    mode = tfm.alg.cipher_mode

    if isinstance(impl, Chacha20CryptoCipher):
        return impl.decrypt(tfm.key, ciphertext)

    if isinstance(impl, DesCryptoCipher):
        if mode == CRYPTO_CIPHER_CBC:
            return _cbc_decrypt(impl, tfm.key, ciphertext, tfm.iv)
        return impl.decrypt(tfm.key, ciphertext)

    if isinstance(impl, AesCryptoCipher):
        if mode == CRYPTO_CIPHER_CBC:
            return _cbc_decrypt(impl, tfm.key, ciphertext, tfm.iv)
        elif mode == CRYPTO_CIPHER_CTR:
            return _ctr_crypt(impl, tfm.key, ciphertext, tfm.iv)
        elif mode == CRYPTO_CIPHER_XTS:
            return _xts_crypt(impl, tfm.key, ciphertext, tfm.iv, encrypt=False)
        return impl.decrypt(tfm.key, ciphertext)

    return impl.decrypt(tfm.key, ciphertext)


# ---------------------------------------------------------------------------
# Mode helpers
# ---------------------------------------------------------------------------

def _cbc_encrypt(impl: Any, key: bytes, plaintext: bytes, iv: bytes) -> bytes:
    block_size = impl.block_size
    out = bytearray()
    prev = iv
    for i in range(0, len(plaintext), block_size):
        block = plaintext[i:i+block_size]
        if len(block) < block_size:
            block = block + b'\x00' * (block_size - len(block))
        xored = bytes(a ^ b for a, b in zip(block, prev))
        encrypted = impl.encrypt(key, xored)
        out.extend(encrypted)
        prev = encrypted
    return bytes(out)


def _cbc_decrypt(impl: Any, key: bytes, ciphertext: bytes, iv: bytes) -> bytes:
    block_size = impl.block_size
    out = bytearray()
    prev = iv
    for i in range(0, len(ciphertext), block_size):
        block = ciphertext[i:i+block_size]
        decrypted = impl.decrypt(key, block)
        plain = bytes(a ^ b for a, b in zip(decrypted, prev))
        out.extend(plain)
        prev = block
    return bytes(out)


def _ctr_crypt(impl: AesCryptoCipher, key: bytes, data: bytes, iv: bytes) -> bytes:
    block_size = 16
    out = bytearray()
    counter = int.from_bytes(iv[:16], 'big') if len(iv) >= 16 else int.from_bytes(iv.ljust(16, b'\x00'), 'big')
    for i in range(0, len(data), block_size):
        ctr_block = counter.to_bytes(16, 'big')
        keystream = impl._encrypt_block(ctr_block)
        block = data[i:i+block_size]
        for j in range(len(block)):
            out.append(block[j] ^ keystream[j])
        counter += 1
    return bytes(out)


def _xts_crypt(impl: AesCryptoCipher, key: bytes, data: bytes, iv: bytes, encrypt: bool = True) -> bytes:
    block_size = 16
    tweak = iv[:16] if len(iv) >= 16 else iv.ljust(16, b'\x00')
    half = len(key) // 2
    key1, key2 = key[:half], key[half:]

    out = bytearray()
    for i in range(0, len(data), block_size):
        block = data[i:i+block_size]
        if len(block) < block_size:
            block = block + b'\x00' * (block_size - len(block))
        t = impl.encrypt(key2, tweak)
        xored = bytes(a ^ b for a, b in zip(block, t))
        if encrypt:
            c = impl.encrypt(key1, xored)
        else:
            c = impl.decrypt(key1, xored)
        out.extend(bytes(a ^ b for a, b in zip(c, t)))
        tweak_int = int.from_bytes(tweak, 'big') << 1
        if tweak_int >> 128:
            tweak_int ^= 0x87
        tweak = tweak_int.to_bytes(16, 'big')
    return bytes(out)


# ---------------------------------------------------------------------------
# Hash Operations
# ---------------------------------------------------------------------------

def crypto_hash(alg_name: str, data: bytes) -> bytes:
    """Hash data - like crypto_hash()"""
    ctx = crypto_hash_init(alg_name)
    crypto_hash_update(ctx, data)
    return crypto_hash_final(ctx)


def crypto_hash_init(alg_name: str) -> Dict[str, Any]:
    """Init hash context"""
    alg = crypto_get_alg(alg_name)
    if alg is None:
        raise ValueError(f"Hash algorithm '{alg_name}' not registered")
    impl = alg._impl
    impl.init()
    return {"alg": alg, "impl": impl}


def crypto_hash_update(hash_ctx: Dict[str, Any], data: bytes) -> None:
    """Update hash"""
    hash_ctx["impl"].update(data)


def crypto_hash_final(hash_ctx: Dict[str, Any]) -> bytes:
    """Finalize hash and get digest"""
    return hash_ctx["impl"].final()


# ---------------------------------------------------------------------------
# AEAD Operations
# ---------------------------------------------------------------------------

def crypto_aead_encrypt(tfm: CryptoTFM, plaintext: bytes, aad: bytes, iv: bytes) -> Tuple[bytes, bytes]:
    """AEAD encrypt"""
    impl = tfm.alg._impl
    if impl is None or not isinstance(impl, AesGcmAead):
        raise ValueError("Not an AEAD algorithm")
    return impl.encrypt(tfm.key, plaintext, aad, iv)


def crypto_aead_decrypt(tfm: CryptoTFM, ciphertext: bytes, aad: bytes, iv: bytes, tag: bytes) -> bytes:
    """AEAD decrypt"""
    impl = tfm.alg._impl
    if impl is None or not isinstance(impl, AesGcmAead):
        raise ValueError("Not an AEAD algorithm")
    return impl.decrypt(tfm.key, ciphertext, aad, iv, tag)


# ---------------------------------------------------------------------------
# RNG Operations
# ---------------------------------------------------------------------------

def crypto_rng_generate(tfm: CryptoTFM, size: int) -> bytes:
    """Generate random bytes"""
    impl = tfm.alg._impl
    if impl is None:
        raise ValueError("No RNG implementation")
    return impl.generate(size)


def crypto_rng_seed(tfm: CryptoTFM, seed: bytes) -> None:
    """Seed RNG"""
    impl = tfm.alg._impl
    if impl is None:
        raise ValueError("No RNG implementation")
    impl.seed(seed)


# ---------------------------------------------------------------------------
# Benchmark
# ---------------------------------------------------------------------------

def crypto_benchmark(alg_name: str, data_size: int = 1024, iterations: int = 1000) -> Dict[str, Any]:
    """Benchmark algorithm performance"""
    alg = crypto_get_alg(alg_name)
    if alg is None:
        raise ValueError(f"Algorithm '{alg_name}' not registered")

    start = time.perf_counter()

    if alg.algo_type == CRYPTO_ALG_HASH:
        ctx = crypto_hash_init(alg_name)
        data = os.urandom(data_size)
        for _ in range(iterations):
            crypto_hash_update(ctx, data)
        crypto_hash_final(ctx)

    elif alg.algo_type == CRYPTO_ALG_RNG:
        tfm = crypto_alloc_tfm(alg_name)
        for _ in range(iterations):
            crypto_rng_generate(tfm, data_size)

    elif alg.algo_type == CRYPTO_ALG_CIPHER:
        if not alg.key_sizes:
            raise ValueError("Algorithm has no key sizes defined")
        key = os.urandom(alg.key_sizes[0])
        tfm = crypto_alloc_tfm(alg_name)
        crypto_set_key(tfm, key)
        data = os.urandom(data_size)
        for _ in range(iterations):
            crypto_encrypt(tfm, data)

    elif alg.algo_type == CRYPTO_ALG_AEAD:
        if not alg.key_sizes:
            raise ValueError("Algorithm has no key sizes defined")
        key = os.urandom(alg.key_sizes[0])
        iv = os.urandom(12)
        tfm = crypto_alloc_tfm(alg_name)
        crypto_set_key(tfm, key)
        data = os.urandom(data_size)
        for _ in range(iterations):
            crypto_aead_encrypt(tfm, data, b"aad", iv)

    elapsed = time.perf_counter() - start
    total_bytes = data_size * iterations
    throughput = total_bytes / elapsed / (1024 * 1024)

    return {
        "algorithm": alg_name,
        "type": alg.algo_type,
        "data_size": data_size,
        "iterations": iterations,
        "elapsed_s": round(elapsed, 4),
        "throughput_mbps": round(throughput, 2),
        "total_bytes": total_bytes,
    }


# ---------------------------------------------------------------------------
# Template System
# ---------------------------------------------------------------------------

def crypto_register_template(template: CryptoTemplate) -> bool:
    """Register algorithm template"""
    if template.name in _template_registry:
        return False
    _template_registry[template.name] = template
    return True


def crypto_create_instance(template_name: str, params: Optional[Dict[str, Any]] = None) -> CryptoInstance:
    """Create crypto instance from template"""
    template = _template_registry.get(template_name)
    if template is None:
        raise ValueError(f"Template '{template_name}' not registered")

    merged = {**template.template_params, **(params or {})}

    base_name = template.name
    for alg in _alg_registry.values():
        if alg.algo_type == template.base_type:
            base_name = alg.name
            break

    tfm = crypto_alloc_tfm(base_name)
    request = CryptoRequest(tfm=tfm, created_at=time.time())
    instance = CryptoInstance(tfm=tfm, request=request, owner=template.driver_name)
    _instances.append(instance)
    return instance


# ---------------------------------------------------------------------------
# Register Built-in Algorithms
# ---------------------------------------------------------------------------

def _register_builtin_algorithms() -> None:
    """Register all built-in crypto algorithms"""

    # AES ciphers
    aes_ecb = CryptoAlg(
        name="aes", driver_name="aes-generic", algo_type=CRYPTO_ALG_CIPHER,
        cipher_mode=CRYPTO_CIPHER_ECB, key_sizes=[16, 24, 32],
        iv_size=0, block_size=16, priority=100, flags=CRYPTO_ALG_TYPE_CIPHER,
        _impl=AesCryptoCipher(),
    )
    crypto_register_alg(aes_ecb)

    aes_cbc = CryptoAlg(
        name="aes-cbc", driver_name="aes-generic", algo_type=CRYPTO_ALG_CIPHER,
        cipher_mode=CRYPTO_CIPHER_CBC, key_sizes=[16, 24, 32],
        iv_size=16, block_size=16, priority=100, flags=CRYPTO_ALG_TYPE_CIPHER,
        _impl=AesCryptoCipher(),
    )
    crypto_register_alg(aes_cbc)

    aes_ctr = CryptoAlg(
        name="aes-ctr", driver_name="aes-generic", algo_type=CRYPTO_ALG_CIPHER,
        cipher_mode=CRYPTO_CIPHER_CTR, key_sizes=[16, 24, 32],
        iv_size=16, block_size=16, priority=100, flags=CRYPTO_ALG_TYPE_CIPHER,
        _impl=AesCryptoCipher(),
    )
    crypto_register_alg(aes_ctr)

    aes_xts = CryptoAlg(
        name="aes-xts", driver_name="aes-generic", algo_type=CRYPTO_ALG_CIPHER,
        cipher_mode=CRYPTO_CIPHER_XTS, key_sizes=[32, 48, 64],
        iv_size=16, block_size=16, priority=100, flags=CRYPTO_ALG_TYPE_CIPHER,
        _impl=AesCryptoCipher(),
    )
    crypto_register_alg(aes_xts)

    # DES
    des_ecb = CryptoAlg(
        name="des", driver_name="des-generic", algo_type=CRYPTO_ALG_CIPHER,
        cipher_mode=CRYPTO_CIPHER_ECB, key_sizes=[8],
        iv_size=0, block_size=8, priority=50, flags=CRYPTO_ALG_TYPE_CIPHER,
        _impl=DesCryptoCipher(),
    )
    crypto_register_alg(des_ecb)

    des_cbc = CryptoAlg(
        name="des-cbc", driver_name="des-generic", algo_type=CRYPTO_ALG_CIPHER,
        cipher_mode=CRYPTO_CIPHER_CBC, key_sizes=[8],
        iv_size=8, block_size=8, priority=50, flags=CRYPTO_ALG_TYPE_CIPHER,
        _impl=DesCryptoCipher(),
    )
    crypto_register_alg(des_cbc)

    # ChaCha20
    chacha20 = CryptoAlg(
        name="chacha20", driver_name="chacha20-generic", algo_type=CRYPTO_ALG_CIPHER,
        cipher_mode="stream", key_sizes=[16, 32],
        iv_size=0, block_size=1, priority=100, flags=CRYPTO_ALG_TYPE_CIPHER,
        _impl=Chacha20CryptoCipher(),
    )
    crypto_register_alg(chacha20)

    # Hashes
    sha256 = CryptoAlg(
        name="sha256", driver_name="sha256-generic", algo_type=CRYPTO_ALG_HASH,
        block_size=64, digest_size=32, priority=100, flags=CRYPTO_ALG_TYPE_HASH,
        _impl=Sha256Hash(),
    )
    crypto_register_alg(sha256)

    md5 = CryptoAlg(
        name="md5", driver_name="md5-generic", algo_type=CRYPTO_ALG_HASH,
        block_size=64, digest_size=16, priority=50, flags=CRYPTO_ALG_TYPE_HASH,
        _impl=Md5Hash(),
    )
    crypto_register_alg(md5)

    sha3_256 = CryptoAlg(
        name="sha3-256", driver_name="sha3-generic", algo_type=CRYPTO_ALG_HASH,
        block_size=136, digest_size=32, priority=100, flags=CRYPTO_ALG_TYPE_HASH,
        _impl=Sha3_256Hash(),
    )
    crypto_register_alg(sha3_256)

    # AEAD
    aes_gcm = CryptoAlg(
        name="aes-gcm", driver_name="aes-gcm-generic", algo_type=CRYPTO_ALG_AEAD,
        cipher_mode=CRYPTO_CIPHER_GCM, key_sizes=[16, 24, 32],
        iv_size=12, block_size=16, priority=100, flags=CRYPTO_ALG_TYPE_AEAD,
        _impl=AesGcmAead(),
    )
    crypto_register_alg(aes_gcm)

    # RNG
    chacha20_rng = CryptoAlg(
        name="chacha20-rng", driver_name="chacha20-rng", algo_type=CRYPTO_ALG_RNG,
        priority=100, flags=CRYPTO_ALG_TYPE_RNG,
        _impl=ChaCha20Rng(),
    )
    crypto_register_alg(chacha20_rng)

    mrd_rng = CryptoAlg(
        name="mrd-random", driver_name="mrd-random", algo_type=CRYPTO_ALG_RNG,
        priority=80, flags=CRYPTO_ALG_TYPE_RNG,
        _impl=MrdRandom(),
    )
    crypto_register_alg(mrd_rng)


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def _demo() -> None:
    """Demonstrate the UmerOS Crypto Framework"""
    print("=" * 70)
    print("UmerOS Crypto Framework Demo")
    print("=" * 70)

    _register_builtin_algorithms()

    # --- List algorithms ---
    print("\n[1] Registered Algorithms:")
    print("-" * 70)
    for alg in crypto_list_algs():
        flag_str = ""
        if alg.flags & CRYPTO_ALG_TYPE_CIPHER:
            flag_str = "CIPHER"
        elif alg.flags & CRYPTO_ALG_TYPE_HASH:
            flag_str = "HASH"
        elif alg.flags & CRYPTO_ALG_TYPE_AEAD:
            flag_str = "AEAD"
        elif alg.flags & CRYPTO_ALG_TYPE_RNG:
            flag_str = "RNG"
        print(f"  {alg.name:20s}  {alg.driver_name:25s}  {flag_str:8s}  pri={alg.priority}")

    # --- AES-256-CBC ---
    print("\n[2] AES-256-CBC Encrypt/Decrypt:")
    print("-" * 70)
    key = os.urandom(32)
    iv = os.urandom(16)
    plaintext = b"UmerOS Crypto API - AES-256-CBC Test!"

    tfm = crypto_alloc_tfm("aes-cbc")
    crypto_set_key(tfm, key)
    crypto_set_iv(tfm, iv)
    ciphertext = crypto_encrypt(tfm, plaintext)
    print(f"  Key:     {key.hex()[:32]}...")
    print(f"  IV:      {iv.hex()}")
    print(f"  Plain:   {plaintext.decode()}")
    print(f"  Cipher:  {ciphertext.hex()[:48]}...")

    tfm2 = crypto_alloc_tfm("aes-cbc")
    crypto_set_key(tfm2, key)
    crypto_set_iv(tfm2, iv)
    decrypted = crypto_decrypt(tfm2, ciphertext)
    print(f"  Decrypt: {decrypted[:len(plaintext)].decode()}")
    print(f"  Match:   {decrypted[:len(plaintext)] == plaintext}")

    # --- SHA-256 ---
    print("\n[3] SHA-256 Hash:")
    print("-" * 70)
    msg = b"UmerOS Crypto API - SHA-256 Test"
    digest = crypto_hash("sha256", msg)
    print(f"  Input:   {msg.decode()}")
    print(f"  SHA-256: {digest.hex()}")

    digest2 = crypto_hash("md5", msg)
    print(f"  MD5:     {digest2.hex()}")

    digest3 = crypto_hash("sha3-256", msg)
    print(f"  SHA3-256:{digest3.hex()}")

    # --- AES-GCM ---
    print("\n[4] AES-GCM Authenticated Encryption:")
    print("-" * 70)
    key_gcm = os.urandom(32)
    iv_gcm = os.urandom(12)
    aad = b"additional authenticated data"
    plaintext_gcm = b"Secret message for AES-GCM!"

    tfm_gcm = crypto_alloc_tfm("aes-gcm")
    crypto_set_key(tfm_gcm, key_gcm)
    ciphertext_gcm, tag = crypto_aead_encrypt(tfm_gcm, plaintext_gcm, aad, iv_gcm)
    print(f"  Cipher:  {ciphertext_gcm.hex()}")
    print(f"  Tag:     {tag.hex()}")
    print(f"  AAD:     {aad.decode()}")

    decrypted_gcm = crypto_aead_decrypt(tfm_gcm, ciphertext_gcm, aad, iv_gcm, tag)
    print(f"  Decrypt: {decrypted_gcm.decode()}")
    print(f"  Match:   {decrypted_gcm == plaintext_gcm}")

    # --- ChaCha20 ---
    print("\n[5] ChaCha20 Stream Cipher:")
    print("-" * 70)
    key_cc = os.urandom(32)
    plaintext_cc = b"UmerOS ChaCha20 stream cipher test!"

    tfm_cc = crypto_alloc_tfm("chacha20")
    crypto_set_key(tfm_cc, key_cc)
    ciphertext_cc = crypto_encrypt(tfm_cc, plaintext_cc)
    print(f"  Plain:   {plaintext_cc.decode()}")
    print(f"  Cipher:  {ciphertext_cc.hex()}")

    tfm_cc2 = crypto_alloc_tfm("chacha20")
    crypto_set_key(tfm_cc2, key_cc)
    decrypted_cc = crypto_decrypt(tfm_cc2, ciphertext_cc)
    print(f"  Decrypt: {decrypted_cc.decode()}")
    print(f"  Match:   {decrypted_cc == plaintext_cc}")

    # --- RNG ---
    print("\n[6] RNG Generation:")
    print("-" * 70)
    tfm_rng = crypto_alloc_tfm("chacha20-rng")
    rng_bytes = crypto_rng_generate(tfm_rng, 32)
    print(f"  ChaCha20-RNG (32 bytes): {rng_bytes.hex()}")

    tfm_mrd = crypto_alloc_tfm("mrd-random")
    mrd_bytes = crypto_rng_generate(tfm_mrd, 32)
    print(f"  MRD-Random  (32 bytes):  {mrd_bytes.hex()}")

    # --- Benchmark ---
    print("\n[7] Benchmark:")
    print("-" * 70)
    for name in ["aes", "aes-cbc", "des", "chacha20", "sha256", "md5", "sha3-256", "chacha20-rng"]:
        result = crypto_benchmark(name, data_size=1024, iterations=500)
        print(f"  {name:20s}  {result['throughput_mbps']:10.2f} MB/s  ({result['elapsed_s']:.4f}s)")

    # --- Algorithm Info ---
    print("\n[8] Algorithm Info:")
    print("-" * 70)
    for name in ["aes", "aes-cbc", "aes-gcm", "chacha20", "sha256", "md5", "sha3-256"]:
        alg = crypto_get_alg(name)
        if alg:
            print(f"  {name:20s}  type={alg.algo_type:8s}  mode={alg.cipher_mode:8s}  "
                  f"key={alg.key_sizes}  block={alg.block_size}  driver={alg.driver_name}")

    # --- Template ---
    print("\n[9] Template System:")
    print("-" * 70)
    template = CryptoTemplate(
        name="aes-cbc-template", base_type="cipher",
        template_params={"mode": "cbc"}, driver_name="template-engine",
    )
    crypto_register_template(template)
    instance = crypto_create_instance("aes-cbc-template")
    print(f"  Created instance: tfm={instance.tfm.name}  owner={instance.owner}")

    print("\n" + "=" * 70)
    print("Demo complete.")
    print("=" * 70)


if __name__ == "__main__":
    _demo()
