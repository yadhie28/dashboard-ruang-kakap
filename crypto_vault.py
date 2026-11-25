"""
Pure-Python AES-256-CTR + HMAC-SHA256 (Encrypt-then-MAC) with PBKDF2-SHA256.
Zero external dependencies — 100% compatible with browser Web Crypto API (crypto.subtle).
Used to encrypt sensitive patient identity & clinical SBAR notes in dashboard_data.json.
"""

import os
import json
import hmac
import base64
import hashlib
import subprocess

# Standard FIPS-197 AES S-Box
_SBOX = [
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
    0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
    0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
    0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16,
]

_RCON = [0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36]


def _xtime(a: int) -> int:
    return ((a << 1) ^ 0x1b) & 0xff if (a & 0x80) else (a << 1)


def _expand_key_256(key: bytes):
    assert len(key) == 32
    w = [list(key[i:i + 4]) for i in range(0, 32, 4)]
    for i in range(8, 60):
        temp = list(w[i - 1])
        if i % 8 == 0:
            temp = [_SBOX[temp[1]] ^ _RCON[i // 8], _SBOX[temp[2]], _SBOX[temp[3]], _SBOX[temp[0]]]
        elif i % 8 == 4:
            temp = [_SBOX[b] for b in temp]
        w.append([w[i - 8][j] ^ temp[j] for j in range(4)])
    return [w[i:i + 4] for i in range(0, 60, 4)]


def _aes256_encrypt_block(block: bytes, round_keys) -> bytes:
    s = [[block[r + 4 * c] for c in range(4)] for r in range(4)]

    def add_rk(rk):
        for c in range(4):
            for r in range(4):
                s[r][c] ^= rk[c][r]

    add_rk(round_keys[0])
    for rnd in range(1, 15):
        # SubBytes
        for r in range(4):
            for c in range(4):
                s[r][c] = _SBOX[s[r][c]]
        # ShiftRows
        s[1] = s[1][1:] + s[1][:1]
        s[2] = s[2][2:] + s[2][:2]
        s[3] = s[3][3:] + s[3][:3]
        # MixColumns (all rounds except last)
        if rnd < 14:
            for c in range(4):
                a0, a1, a2, a3 = s[0][c], s[1][c], s[2][c], s[3][c]
                t = a0 ^ a1 ^ a2 ^ a3
                s[0][c] ^= t ^ _xtime(a0 ^ a1)
                s[1][c] ^= t ^ _xtime(a1 ^ a2)
                s[2][c] ^= t ^ _xtime(a2 ^ a3)
                s[3][c] ^= t ^ _xtime(a3 ^ a0)
        add_rk(round_keys[rnd])

    out = bytearray(16)
    for c in range(4):
        for r in range(4):
            out[r + 4 * c] = s[r][c]
    return bytes(out)


def _aes256_ctr_crypt(data: bytes, key: bytes, counter16: bytes) -> bytes:
    # Fast path: use system openssl (installed on macOS & GitHub Actions Ubuntu) — 1000x faster
    try:
        proc = subprocess.run(
            ["openssl", "enc", "-aes-256-ctr", "-K", key.hex(), "-iv", counter16.hex(), "-nosalt"],
            input=data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        if len(proc.stdout) == len(data):
            return proc.stdout
    except Exception:
        pass

    # Pure-Python fallback
    round_keys = _expand_key_256(key)
    out = bytearray(len(data))
    prefix = counter16[:8]
    ctr = int.from_bytes(counter16[8:], 'big')
    for offset in range(0, len(data), 16):
        ctr_block = prefix + (ctr & 0xffffffffffffffff).to_bytes(8, 'big')
        ks = _aes256_encrypt_block(ctr_block, round_keys)
        chunk = data[offset:offset + 16]
        for i in range(len(chunk)):
            out[offset + i] = chunk[i] ^ ks[i]
        ctr += 1
    return bytes(out)


def encrypt_clinical_vault(payload_obj: dict, pin: str, iterations: int = 100000) -> dict:
    """
    Encrypts a JSON-serializable object with AES-256-CTR + HMAC-SHA256 using PBKDF2-SHA256.
    Browser decrypts using Web Crypto API (PBKDF2 -> 64 bytes -> 32B AES-CTR + 32B HMAC-SHA256).
    """
    salt = os.urandom(16)
    counter = os.urandom(16)
    key_material = hashlib.pbkdf2_hmac('sha256', pin.encode('utf-8'), salt, iterations, dklen=64)
    enc_key = key_material[:32]
    mac_key = key_material[32:]

    plaintext = json.dumps(payload_obj, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    ciphertext = _aes256_ctr_crypt(plaintext, enc_key, counter)
    mac = hmac.new(mac_key, counter + ciphertext, hashlib.sha256).digest()

    return {
        "v": 1,
        "alg": "PBKDF2-SHA256+AES-256-CTR+HMAC-SHA256",
        "iter": iterations,
        "salt": base64.b64encode(salt).decode('ascii'),
        "iv": base64.b64encode(counter).decode('ascii'),
        "mac": base64.b64encode(mac).decode('ascii'),
        "ct": base64.b64encode(ciphertext).decode('ascii'),
    }
