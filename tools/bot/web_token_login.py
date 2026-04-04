"""
Lấy JWT Token Free Fire từ Garena Web Login (không cần MITM, không cần điện thoại)
Luồng: Garena session_key + open_id  →  MajorLogin  →  JWT Token game
"""

import base64
import codecs
import hashlib
import hmac
import json
import os
import time
import requests
import urllib3

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Hằng số ────────────────────────────────────────────────
AES_KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
AES_IV  = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])

REGION_URLS = {
    "VN":  "https://clientbp.ggblueshark.com/",
    "IND": "https://client.ind.freefiremobile.com",
    "ID":  "https://clientbp.ggblueshark.com/",
    "SG":  "https://clientbp.ggblueshark.com/",
    "TH":  "https://clientbp.common.ggbluefox.com/",
    "ME":  "https://clientbp.common.ggbluefox.com/",
    "EU":  "https://clientbp.ggblueshark.com/",
    "NA":  "https://client.us.freefiremobile.com/",
    "BR":  "https://client.us.freefiremobile.com/",
    "SAC": "https://client.us.freefiremobile.com/",
}

REGION_LANG = {
    "VN": "vi", "IND": "hi", "ID": "id", "SG": "en",
    "TH": "th", "ME": "ar", "EU": "en", "NA": "en",
    "BR": "pt", "SAC": "es", "CIS": "ru", "TW": "zh",
}

LOGIN_URL_SHARK = "https://loginbp.ggblueshark.com/MajorLogin"
LOGIN_URL_FOX   = "https://loginbp.common.ggbluefox.com/MajorLogin"



# ── Helpers ─────────────────────────────────────────────────
def _enc_varint(n):
    out = []
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            b |= 0x80
        out.append(b)
        if not n:
            break
    return bytes(out)


def _proto_varint(field, val):
    return _enc_varint((field << 3) | 0) + _enc_varint(val)


def _proto_bytes(field, val):
    if isinstance(val, str):
        val = val.encode()
    return _enc_varint((field << 3) | 2) + _enc_varint(len(val)) + val


def build_proto(fields: dict) -> bytes:
    out = bytearray()
    for f, v in fields.items():
        if isinstance(v, dict):
            nested = build_proto(v)
            out += _proto_bytes(f, nested)
        elif isinstance(v, int):
            out += _proto_varint(f, v)
        else:
            out += _proto_bytes(f, v)
    return bytes(out)


def aes_encrypt(data_hex: str) -> bytes:
    raw = bytes.fromhex(data_hex)
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    return cipher.encrypt(pad(raw, AES.block_size))


def encode_open_id(open_id: str) -> bytes:
    keystream = [0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,
                 0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,
                 0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30]
    encoded = "".join(chr(ord(c) ^ keystream[i % len(keystream)])
                      for i, c in enumerate(open_id))
    unicode_esc = "".join(c if 32 <= ord(c) <= 126 else f"\\u{ord(c):04x}"
                          for c in encoded)
    return codecs.decode(unicode_esc, "unicode_escape").encode("latin1")


def decode_jwt(token: str) -> dict:
    try:
        part = token.split(".")[1]
        part += "=" * ((4 - len(part) % 4) % 4)
        return json.loads(base64.urlsafe_b64decode(part))
    except Exception:
        return {}


# ── Bước 1: Lấy Garena access_token từ session_key ─────────
def get_garena_token(session_key: str, open_id: str, log_q=None) -> dict | None:
    """
    Dùng session_key (cookie từ auth.garena.com) + open_id để lấy Garena access_token.
    """
    def log(msg):
        if log_q:
            log_q.put(msg)

    url = "https://100067.connect.garena.com/oauth/token/grant"
    headers = {
        "User-Agent": "GarenaMSDK/4.0.19P8(ASUS_Z01QD ;Android 12;en;US;)",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept-Encoding": "gzip",
        "Connection": "Keep-Alive",
    }
    data = {
        "session_key": session_key,
        "open_id": open_id,
        "app_id": "100067",
        "client_type": "2",
        "response_type": "token",
    }

    try:
        r = requests.post(url, headers=headers, data=data, verify=False, timeout=15)
        log(f"[*] Garena token API → HTTP {r.status_code}")
        if r.status_code == 200:
            js = r.json()
            if "access_token" in js:
                log(f"[+] Lấy được access_token Garena!")
                return js
            else:
                log(f"[-] Response: {r.text[:200]}")
        else:
            log(f"[-] Lỗi HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        log(f"[-] Lỗi kết nối Garena token API: {e}")

    return None


# ── Bước 2: MajorLogin → JWT game ───────────────────────────
def major_login(access_token: str, open_id: str, region: str = "VN",
                proxy=None, log_q=None) -> str | None:
    """
    Dùng Garena access_token + open_id để gọi MajorLogin và lấy JWT game.
    """
    def log(msg):
        if log_q:
            log_q.put(msg)

    lang = REGION_LANG.get(region.upper(), "vi")
    lang_b = lang.encode()
    field14 = encode_open_id(open_id)

    # Build payload (reuse từ reg.py)
    payload_template = (
        b'\x1a\x132025-08-30 05:19:21"\tfree fire(\x01:\x081.114.13B2Android OS 9 / API-28 (PI/rel.cjw.20220518.114133)J\x08HandheldR\nATM MobilsZ\x04WIFI`\xb6\nh\xee\x05r\x03300z\x1fARMv7 VFPv3 NEON VMH | 2400 | 2\x80\x01\xc9\x0f\x8a\x01\x0fAdreno (TM) 640\x92\x01\rOpenGL ES 3.2\x9a\x01+Google|dfa4ab4b-9dc4-454e-8065-e70c733fa53f\xa2\x01\x0e105.235.139.91\xaa\x01\x02'
        + lang_b
        + b'\xb2\x01 1d8ec0240ede109973f3321b9354b44d\xba\x01\x014\xc2\x01\x08Handheld\xca\x01\x10Asus ASUS_I005DA\xea\x01@afcfbf13334be42036e4f742c80b956344bed760ac91b3aff9b607a610ab4390\xf0\x01\x01\xca\x02\nATM Mobils\xd2\x02\x04WIFI\xca\x03 7428b253defc164018c604a1ebbfebdf\xe0\x03\xa8\x81\x02\xe8\x03\xf6\xe5\x01\xf0\x03\xaf\x13\xf8\x03\x84\x07\x80\x04\xe7\xf0\x01\x88\x04\xa8\x81\x02\x90\x04\xe7\xf0\x01\x98\x04\xa8\x81\x02\xc8\x04\x01\xd2\x04=/data/app/com.dts.freefireth-PdeDnOilCSFn37p1AH_FLg==/lib/arm\xe0\x04\x01\xea\x04_2087f61c19f57f2af4e7feff0b24d9d9|/data/app/com.dts.freefireth-PdeDnOilCSFn37p1AH_FLg==/base.apk\xf0\x04\x03\xf8\x04\x01\x8a\x05\x0232\x9a\x05\n2019118692\xb2\x05\tOpenGLES2\xb8\x05\xff\x7f\xc0\x05\x04\xe0\x05\xf3F\xea\x05\x07android\xf2\x05pKqsHT5ZLWrYljNb5Vqh//yFRlaPHSO9NWSQsVvOmdhEEn7W+VHNUK+Q+fduA3ptNrGB0Ll0LRz3WW0jOwesLj6aiU7sZ40p8BfUE/FI/jzSTwRe2\xf8\x05\xfb\xe4\x06\x88\x06\x01\x90\x06\x01\x9a\x06\x014\xa2\x06\x014\xb2\x06"GQ@O\x00\x0e^\x00D\x06UA\x0ePM\r\x13hZ\x07T\x06\x0cm\\V\x0ejYV;\x0bU5'
    )

    data = payload_template
    data = data.replace(
        b"afcfbf13334be42036e4f742c80b956344bed760ac91b3aff9b607a610ab4390",
        access_token.encode()
    )
    data = data.replace(b"1d8ec0240ede109973f3321b9354b44d", open_id.encode())

    encrypted = aes_encrypt(data.hex())
    url = LOGIN_URL_FOX if region.upper() == "ME" else LOGIN_URL_SHARK

    headers = {
        "Accept-Encoding": "gzip",
        "Authorization": "Bearer",
        "Connection": "Keep-Alive",
        "Content-Type": "application/x-www-form-urlencoded",
        "Expect": "100-continue",
        "Host": "loginbp.ggblueshark.com",
        "ReleaseVersion": "OB52",
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_I005DA Build/PI)",
        "X-GA": "v1 1",
        "X-Unity-Version": "2018.4.11f1",
    }

    try:
        log(f"[*] Gọi MajorLogin ({url.split('/')[2]})...")
        r = requests.post(url, headers=headers, data=encrypted,
                          proxies=proxy, verify=False, timeout=20)
        log(f"[*] MajorLogin → HTTP {r.status_code}")

        if r.status_code != 200 or len(r.text) < 10:
            log(f"[-] MajorLogin thất bại")
            return None

        # Tìm JWT trong response
        import re
        jwt_match = re.search(
            r"(eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)", r.text
        )
        if jwt_match:
            jwt = jwt_match.group(1)
            payload = decode_jwt(jwt)
            uid = payload.get("external_id", "?")
            log(f"[+] Lấy được JWT Token! UID game: {uid}")
            return jwt
        else:
            log(f"[-] Không tìm thấy JWT trong response")
            return None

    except Exception as e:
        log(f"[-] Lỗi MajorLogin: {e}")
        return None


# ── Hàm chính: Chạy toàn bộ luồng ──────────────────────────
def run_web_login(session_key: str, open_id: str, region: str,
                  data_dir: str, log_q=None) -> bool:
    """
    Toàn bộ flow: session_key + open_id → Garena token → JWT → lưu file
    """
    def log(msg):
        if log_q:
            log_q.put(msg)

    log("=" * 50)
    log(f"[*] Bắt đầu lấy token từ Garena Web")
    log(f"[*] Open ID : {open_id}")
    log(f"[*] Region  : {region}")
    log("=" * 50)

    # Bước 1: Lấy Garena access_token từ session_key
    log("\n[Bước 1] Đổi session_key → Garena access_token...")
    garena_data = get_garena_token(session_key, open_id, log_q)

    if not garena_data:
        log("\n[!] Thử phương án 2: dùng session_key trực tiếp làm access_token...")
        access_token = session_key
    else:
        access_token = garena_data.get("access_token", session_key)

    # Bước 2: Gọi MajorLogin
    log(f"\n[Bước 2] Gọi MajorLogin Free Fire (region={region})...")
    jwt = major_login(access_token, open_id, region, log_q=log_q)

    if not jwt:
        log("\n❌ Không lấy được JWT. Có thể session_key đã hết hạn hoặc sai.")
        return False

    # Lưu vào access_real.txt
    os.makedirs(data_dir, exist_ok=True)
    out_file = os.path.join(data_dir, "access_real.txt")
    with open(out_file, "a", encoding="utf-8") as f:
        f.write(jwt + "\n")

    log(f"\n✅ Đã lưu JWT vào access_real.txt")
    log(f"📋 JWT (60 ký tự đầu): {jwt[:60]}...")
    return True
