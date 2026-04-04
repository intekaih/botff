"""
Account Info Checker - BOT FF
Hỗ trợ: Game JWT / Garena OAuth token / MSDK authToken
"""
import base64
import json
import struct
import sys
import requests
import warnings

warnings.filterwarnings("ignore")

AES_KEY = bytes([89,103,38,116,99,37,68,69,117,104,54,37,90,99,94,56])
AES_IV  = bytes([54,111,121,90,68,114,50,50,69,51,121,99,104,106,77,37])

EXTERNAL_TYPES = {
    1: "Garena account",
    2: "Facebook",
    3: "VK",
    4: "Google",
    5: "Apple",
    6: "Twitter",
    7: "Huawei",
}

REGIONS = {
    "VN": ("https://clientbp.ggblueshark.com", "https://loginbp.ggblueshark.com"),
    "IND": ("https://clientbp.ggblueshark.com", "https://loginbp.ggblueshark.com"),
    "ID": ("https://clientbp.ggblueshark.com", "https://loginbp.ggblueshark.com"),
    "TH": ("https://clientbp.ggblueshark.com", "https://loginbp.ggblueshark.com"),
    "SG": ("https://clientbp.ggblueshark.com", "https://loginbp.ggblueshark.com"),
    "BR": ("https://clientbp.common.ggbluefox.com", "https://loginbp.common.ggbluefox.com"),
    "US": ("https://clientbp.common.ggbluefox.com", "https://loginbp.common.ggbluefox.com"),
    "SAC": ("https://clientbp.common.ggbluefox.com", "https://loginbp.common.ggbluefox.com"),
}


def _aes_encrypt(raw: bytes) -> bytes:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    return cipher.encrypt(pad(raw, AES.block_size))


def _aes_decrypt(enc: bytes) -> bytes:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    return unpad(cipher.decrypt(enc), AES.block_size)


def _varint(n: int) -> bytes:
    out = []
    while True:
        b = n & 0x7F; n >>= 7
        if n: b |= 0x80
        out.append(b)
        if not n: break
    return bytes(out)


def _field(f, v): return _varint((f << 3) | 0) + _varint(v)
def _field_bytes(f, v): return _varint((f << 3) | 2) + _varint(len(v)) + v


def decode_jwt_claims(jwt_token: str) -> dict | None:
    """Decode JWT payload (không verify signature)."""
    try:
        parts = jwt_token.split('.')
        if len(parts) != 3:
            return None
        payload = parts[1]
        payload += '=' * (4 - len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload).decode('utf-8', errors='replace'))
    except Exception:
        return None


def detect_token_type(token: str) -> str:
    """Phân loại token."""
    if token.startswith('eyJ'):
        return 'game_jwt'
    if len(token) == 64 and all(c in '0123456789abcdefABCDEF' for c in token):
        return 'msdk_auth_token'
    if len(token) > 100:
        return 'garena_oauth'
    return 'unknown'


def build_personal_show_payload(uid: int) -> bytes:
    return _field(1, uid) + _field(2, 1) + _field(3, 1)


def get_player_personal_show(jwt_token: str, target_uid: int, region: str = "VN", log_q=None) -> dict | None:
    """Gọi GetPlayerPersonalShow với game JWT → trả về thông tin người chơi."""
    def log(m):
        if log_q: log_q.put(m)

    client_url = REGIONS.get(region, REGIONS["VN"])[0]
    url = f"{client_url}/GetPlayerPersonalShow"

    headers = {
        "Authorization":   f"Bearer {jwt_token}",
        "Content-Type":    "application/x-www-form-urlencoded",
        "User-Agent":      "Dalvik/2.1.0 (Linux; U; Android 10; G011A Build/PI)",
        "X-Unity-Version": "2018.4.11f1",
        "X-GA":            "v1 1",
        "ReleaseVersion":  "OB52",
        "Connection":      "Keep-Alive",
        "Accept-Encoding": "gzip",
        "Expect":          "100-continue",
    }

    payload = _aes_encrypt(build_personal_show_payload(target_uid))
    log(f"[*] GetPlayerPersonalShow → {url}")
    try:
        r = requests.post(url, headers=headers, data=payload, verify=False, timeout=15)
        log(f"[*] HTTP {r.status_code}, {len(r.content)} bytes")
        if r.status_code == 200 and len(r.content) > 0:
            dec = _aes_decrypt(r.content)
            return {"raw_hex": dec.hex(), "raw_bytes": dec}
        return None
    except Exception as e:
        log(f"[-] GetPlayerPersonalShow lỗi: {e}")
        return None


def parse_personal_show_proto(data: bytes) -> dict:
    """Parse protobuf response từ GetPlayerPersonalShow (basic manual parsing)."""
    result = {}
    try:
        import blackboxprotobuf
        val, _ = blackboxprotobuf.decode_message(data)
        result["proto"] = val
        # Tìm các field phổ biến
        for k, v in val.items():
            if isinstance(v, (str, bytes)):
                key = str(k)
                result[key] = v.decode('utf-8', errors='replace') if isinstance(v, bytes) else v
            elif isinstance(v, int):
                result[str(k)] = v
        return result
    except Exception:
        pass

    # Manual basic protobuf parse
    i = 0
    while i < len(data):
        try:
            tag_byte = data[i]; i += 1
            field_num = tag_byte >> 3
            wire_type = tag_byte & 0x07
            if wire_type == 0:  # varint
                val = 0; shift = 0
                while True:
                    b = data[i]; i += 1
                    val |= (b & 0x7F) << shift; shift += 7
                    if not (b & 0x80): break
                result[f"f{field_num}"] = val
            elif wire_type == 2:  # length-delimited
                length = 0; shift = 0
                while True:
                    b = data[i]; i += 1
                    length |= (b & 0x7F) << shift; shift += 7
                    if not (b & 0x80): break
                raw = data[i:i+length]; i += length
                try:
                    result[f"f{field_num}_str"] = raw.decode('utf-8')
                except Exception:
                    result[f"f{field_num}_hex"] = raw.hex()
            else:
                break
        except Exception:
            break
    return result


def get_garena_user_info(token: str, open_id: str, log_q=None) -> dict:
    """Thử lấy thông tin từ Garena Connect API."""
    def log(m):
        if log_q: log_q.put(m)

    headers = {
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_I005DA Build/PI) GarenaMSDK/4.0.19P8",
        "Authorization": f"Bearer {token}",
    }
    endpoints = [
        f"https://100067.connect.garena.com/oauth/user/info?access_token={token}&open_id={open_id}",
        f"https://account.garena.com/api/account/profile?access_token={token}&open_id={open_id}",
        f"https://auth.garena.com/api/user/info?access_token={token}&open_id={open_id}",
    ]
    for url in endpoints:
        try:
            r = requests.get(url, headers=headers, timeout=8, verify=False)
            log(f"[*] {url[:65]} → HTTP {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                log(f"[+] Garena API response: {json.dumps(data)[:200]}")
                return data
        except Exception as e:
            log(f"[-] {url[:50]}: {e}")
    return {}


def check_account_info(token: str, open_id: str, region: str = "VN", log_q=None) -> dict:
    """
    Entry point chính:
    - Nhận token (bất kỳ loại), open_id, region
    - Trả về dict với tất cả thông tin tìm được
    """
    def log(m):
        if log_q: log_q.put(m)

    token_type = detect_token_type(token)
    log(f"[*] Token type: {token_type}")
    log(f"[*] Token length: {len(token)} chars")

    result = {
        "token_type": token_type,
        "open_id_raw": open_id,
        "region": region,
        "jwt_claims": None,
        "garena_info": {},
        "player_info": None,
        "summary": {}
    }

    if token_type == 'game_jwt':
        # ── Đây là JWT game, decode ngay ──
        log("\n[+] Phát hiện Game JWT — đang decode...")
        claims = decode_jwt_claims(token)
        if claims:
            result["jwt_claims"] = claims
            ext_type = claims.get("external_type", 0)
            ext_name = EXTERNAL_TYPES.get(ext_type, f"Unknown({ext_type})")

            log(f"\n{'='*45}")
            log(f"[+] UID game (account_id): {claims.get('account_id', 'N/A')}")
            log(f"[+] Nickname: {claims.get('nickname', 'N/A')}")
            log(f"[+] Region: {claims.get('noti_region', 'N/A')}")
            log(f"[+] Loại tài khoản liên kết: {ext_name}")
            log(f"[+] External ID: {claims.get('external_id', 'N/A')}")
            log(f"[+] Token hết hạn (exp): {claims.get('exp', 'N/A')}")
            log(f"{'='*45}")

            result["summary"] = {
                "uid": claims.get("account_id"),
                "nickname": claims.get("nickname"),
                "region": claims.get("noti_region"),
                "linked_type": ext_name,
                "external_id": claims.get("external_id"),
            }

            # Gọi GetPlayerPersonalShow để lấy thêm thông tin
            uid = claims.get("account_id")
            if uid:
                log(f"\n[*] Đang gọi GetPlayerPersonalShow cho UID {uid}...")
                ps = get_player_personal_show(token, uid, region, log_q)
                if ps:
                    parsed = parse_personal_show_proto(ps["raw_bytes"])
                    log(f"[+] Player info raw: {json.dumps(parsed, default=str)[:400]}")
                    result["player_info"] = parsed

    elif token_type == 'msdk_auth_token':
        # ── MSDK authToken (hex 64 chars) ──
        log("\n[!] Đây là MSDK authToken (GarenaSDK internal)")
        log("[!] Token này KHÔNG phải Garena OAuth access_token")
        log("[!] Không thể dùng trực tiếp với MajorLogin / GetPlayerPersonalShow")
        log("\n[*] Thông tin về token:")
        log(f"    authToken: {token}")
        log(f"    openId:    {open_id}")
        log(f"    openId dạng UUID: {open_id[:8]}-{open_id[8:12]}-{open_id[12:16]}-{open_id[16:20]}-{open_id[20:]}")
        log("\n[*] Đang thử Garena Connect API...")
        info = get_garena_user_info(token, open_id, log_q)
        result["garena_info"] = info

        log("\n[!] Giải thích: ADB script tìm được authToken/openId từ")
        log("    GarenaSDK preferences — đây là layer xác thực phụ.")
        log("    Cần tìm 'access_token' (chuỗi dài >100 ký tự) từ file XML khác.")
        log("\n[→] Gợi ý: Chạy lệnh sau để tìm OAuth token:")
        log('    adb shell su -c "find /data/data/com.dts.freefireth/shared_prefs -name \'*.xml\' | xargs grep -h \'value=\\\"\' | grep -v \'true\\|false\\|[0-9]\\{1,5\\}\\\"\\|empty\' | sort -t\'\\"\' -k2 -rn | head -20"')

    else:
        # ── Thử như OAuth token ──
        log(f"\n[*] Token type unknown/OAuth — thử Garena Connect API...")
        info = get_garena_user_info(token, open_id, log_q)
        result["garena_info"] = info

    log("\n[✓] Kiểm tra hoàn tất.")
    return result
