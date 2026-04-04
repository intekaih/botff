"""
Google OAuth2 → Garena API → Free Fire JWT
"""
import base64
import hashlib
import hmac
import json
import urllib.parse
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Garena constants ─────────────────────────────────────────
HEX_KEY = (
    "32656534343831396539623435393838343531343130363762323831363231383"
    "734643064356437616639643866376530306331653534373135623764316533"
)
GARENA_KEY    = bytes.fromhex(HEX_KEY)
GARENA_APP_ID = "100067"
GARENA_BASE   = "https://100067.connect.garena.com"
GARENA_SDK_UA = "GarenaMSDK/4.0.19P8(ASUS_Z01QD ;Android 12;en;US;)"

# ── Google OAuth constants ───────────────────────────────────
GOOGLE_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_SCOPES    = "openid email profile"


def _hmac_sig(body_str: str) -> str:
    return hmac.new(GARENA_KEY, body_str.encode(), hashlib.sha256).hexdigest()


def _decode_jwt_payload(token: str) -> dict:
    """Giải mã JWT payload không cần verify."""
    try:
        part = token.split(".")[1]
        part += "=" * ((4 - len(part) % 4) % 4)
        return json.loads(base64.urlsafe_b64decode(part))
    except Exception:
        return {}


def garena_google_exchange(google_id_token: str, google_access_token: str = "",
                            google_sub: str = "", log_q=None) -> dict | None:
    """
    Đổi Google id_token → Garena access_token + open_id.
    Thử mọi variant có thể.
    """
    def log(msg):
        if log_q:
            log_q.put(msg)

    # Lấy Google sub (user_id) từ id_token
    payload = _decode_jwt_payload(google_id_token)
    sub = google_sub or payload.get("sub", "")
    log(f"[*] Google sub (user_id): {sub}")

    headers = {
        "User-Agent": GARENA_SDK_UA,
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept-Encoding": "gzip",
        "Connection": "Keep-Alive",
    }

    ENDPOINT = f"{GARENA_BASE}/oauth/token/grant"

    # ── Build attempt list ────────────────────────────────────
    attempts = []

    # Bộ tokens để thử
    tokens_to_try = [
        ("id_token",     google_id_token),
        ("access_token", google_access_token or google_id_token),
    ]

    # Platform numbers to try
    platforms = ["4", "google", "2"]   # 4=Google, "google", 2 cũng thử

    # Token param names
    tkeys = ["social_token", "id_token", "access_token", "token"]

    # ── Nhóm 1: token/grant + open_id = google sub ──────────
    for plat in platforms:
        for tname, tok in tokens_to_try:
            for tkey in tkeys:
                attempts.append({
                    "_label": f"[+open_id=sub] plat={plat} {tkey}={tname[:8]}",
                    "_url":   ENDPOINT,
                    "platform":      plat,
                    tkey:            tok,
                    "open_id":       sub,
                    "app_id":        GARENA_APP_ID,
                    "client_type":   "2",
                    "response_type": "token",
                })

    # ── Nhóm 2: token/grant + open_id + client_secret ────────
    for tname, tok in tokens_to_try:
        for csec in [GARENA_KEY.hex(), GARENA_KEY.decode("latin1", errors="replace")]:
            attempts.append({
                "_label":  f"[+client_secret] {tname[:8]}",
                "_url":    ENDPOINT,
                "platform":      "4",
                "social_token":  tok,
                "open_id":       sub,
                "app_id":        GARENA_APP_ID,
                "client_type":   "2",
                "response_type": "token",
                "client_secret": csec,
                "client_id":     GARENA_APP_ID,
            })

    # ── Nhóm 3: HMAC Authorization signature + open_id ───────
    for tname, tok in tokens_to_try:
        body_d = {
            "platform": "4", "social_token": tok,
            "open_id": sub, "app_id": GARENA_APP_ID,
            "client_type": "2", "response_type": "token",
        }
        body_s = urllib.parse.urlencode(body_d)
        sig    = _hmac_sig(body_s)
        attempts.append({
            "_label":  f"[+HMAC_sig+open_id] {tname[:8]}",
            "_url":    ENDPOINT,
            "_hmac":   sig,
            **body_d,
        })

    # ── Nhóm 4: không có open_id (original variants)  ───────
    for tname, tok in tokens_to_try:
        attempts.append({
            "_label": f"[no open_id] social_token={tname[:8]}",
            "_url":   ENDPOINT,
            "platform":      "4",
            "social_token":  tok,
            "app_id":        GARENA_APP_ID,
            "client_type":   "2",
            "response_type": "token",
        })

    # ── Chạy ─────────────────────────────────────────────────
    log(f"[*] Thử {len(attempts)} variants trên {ENDPOINT}...")

    prev_resp = None
    for i, att in enumerate(attempts):
        url   = att.pop("_url")
        label = att.pop("_label")
        sig   = att.pop("_hmac", None)

        hdrs = dict(headers)
        if sig:
            hdrs["Authorization"] = f"Signature {sig}"

        try:
            r = requests.post(url, headers=hdrs, data=att,
                              verify=False, timeout=12)
            resp_text = r.text[:300].replace('\n', ' ')

            # Chỉ log khi response thay đổi hoặc không phải invalid_request thông thường
            is_interesting = (r.status_code != 200 or
                              '"invalid_request"' not in r.text or
                              resp_text != prev_resp)

            if is_interesting:
                log(f"    [{i+1}] {label}")
                log(f"          HTTP {r.status_code}: {resp_text}")
                prev_resp = resp_text

            if r.status_code == 200:
                try:
                    js = r.json()
                    if "access_token" in js and "open_id" in js:
                        log(f"\n✅ Tìm thấy endpoint đúng!")
                        log(f"   Variant: {label}")
                        log(f"   Open ID: {js['open_id']}")
                        return js
                    elif js.get("error") != "invalid_request":
                        log(f"   [!] Lỗi mới (không phải invalid_request): {js}")
                except Exception:
                    pass

        except Exception as e:
            log(f"    [{i+1}] {label} → Exception: {e}")

    log(f"\n── Kết luận ──")
    log(f"   Garena yêu cầu Google client_id riêng của họ (từ APK).")
    log(f"   Token của chúng ta có audience khác với Garena's server.")
    log(f"   Cần serverAuthCode từ Garena's Google client_id.")
    return None


# ── Thử raw Google auth code với Garena ─────────────────────
def try_raw_code_with_garena(auth_code: str, redirect_uri: str,
                              log_q=None) -> dict | None:
    """
    Thử gửi raw Google authorization code thẳng lên Garena.
    Một số impl cho phép Garena tự exchange code với Google.
    NOTE: code vẫn còn hiệu lực sau nếu Garena reject ngay (không exchange).
    """
    def log(msg):
        if log_q:
            log_q.put(msg)

    ENDPOINT = f"{GARENA_BASE}/oauth/token/grant"
    headers = {
        "User-Agent": GARENA_SDK_UA,
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept-Encoding": "gzip",
        "Connection": "Keep-Alive",
    }

    variants = [
        {
            "platform": "4",
            "code": auth_code,
            "redirect_uri": redirect_uri,
            "app_id": GARENA_APP_ID,
            "client_type": "2",
            "response_type": "token",
            "grant_type": "authorization_code",
        },
        {
            "platform": "4",
            "server_auth_code": auth_code,
            "redirect_uri": redirect_uri,
            "app_id": GARENA_APP_ID,
            "client_type": "2",
            "response_type": "token",
        },
        {
            "platform": "google",
            "code": auth_code,
            "redirect_uri": redirect_uri,
            "app_id": GARENA_APP_ID,
            "client_type": "2",
            "response_type": "token",
        },
    ]

    for v in variants:
        try:
            r = requests.post(ENDPOINT, headers=headers, data=v,
                              verify=False, timeout=10)
            resp = r.text[:200]
            if log_q:
                log_q.put(f"    [raw_code] HTTP {r.status_code}: {resp}")
            if r.status_code == 200:
                js = r.json()
                if "access_token" in js and "open_id" in js:
                    log("✅ Raw code được Garena accept!")
                    return js
        except Exception as e:
            if log_q:
                log_q.put(f"    [raw_code] Exception: {e}")

    return None


# ── Build Google OAuth URL ────────────────────────────────────
def build_auth_url(client_id: str, redirect_uri: str, state: str = "") -> str:
    params = {
        "client_id":     client_id,
        "redirect_uri":  redirect_uri,
        "response_type": "code",
        "scope":         GOOGLE_SCOPES,
        "access_type":   "offline",
        "prompt":        "consent",
        "state":         state,
    }
    return GOOGLE_AUTH_URL + "?" + urllib.parse.urlencode(params)


# ── Đổi authorization code → Google tokens ──────────────────
def exchange_code(code: str, client_id: str, client_secret: str,
                  redirect_uri: str) -> dict | None:
    data = {
        "code":          code,
        "client_id":     client_id,
        "client_secret": client_secret,
        "redirect_uri":  redirect_uri,
        "grant_type":    "authorization_code",
    }
    r = requests.post(GOOGLE_TOKEN_URL, data=data, timeout=15)
    if r.status_code == 200:
        return r.json()
    return None


# ── Lấy user info từ Google token ────────────────────────────
def get_google_userinfo(access_token: str) -> dict:
    r = requests.get(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if r.status_code == 200:
        return r.json()
    return {}
