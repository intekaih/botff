"""
Google OAuth2 → Garena API → Free Fire JWT
Không cần MITM, không cần điện thoại, không cần jailbreak
"""

import hashlib
import hmac
import json
import os
import time
import urllib.parse
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Garena API constants ─────────────────────────────────────
HEX_KEY = (
    "32656534343831396539623435393838343531343130363762323831363231383"
    "734643064356437616639643866376530306331653534373135623764316533"
)
GARENA_KEY       = bytes.fromhex(HEX_KEY)
GARENA_APP_ID    = "100067"

# ── Google OAuth constants ───────────────────────────────────
GOOGLE_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_SCOPES    = "openid email profile"

GARENA_SDK_UA = "GarenaMSDK/4.0.19P8(ASUS_Z01QD ;Android 12;en;US;)"
GARENA_BASE   = "https://100067.connect.garena.com"


def _hmac_sig(body_str: str) -> str:
    return hmac.new(GARENA_KEY, body_str.encode(), hashlib.sha256).hexdigest()


# ── Lấy Garena token từ Google token ────────────────────────
def garena_google_exchange(google_id_token: str, google_access_token: str = "",
                            log_q=None) -> dict | None:
    """
    Đổi Google id_token → Garena access_token + open_id
    Thử nhiều endpoint + params variations để tìm đúng cách.
    """
    def log(msg):
        if log_q:
            log_q.put(msg)

    headers_base = {
        "User-Agent": GARENA_SDK_UA,
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept-Encoding": "gzip",
        "Connection": "Keep-Alive",
    }

    # ── Tập hợp tất cả variants cần thử ────────────────────
    attempts = []

    # [1] Endpoint chính /oauth/token/grant (same as web login)
    #     Garena có thể chấp nhận platform param thay session_key
    for plat in ["4", "google"]:
        for tkey in ["social_token", "id_token", "access_token"]:
            tok = google_id_token if tkey != "access_token" else (google_access_token or google_id_token)
            attempts.append({
                "_label": f"token/grant plat={plat} key={tkey}",
                "_url": f"{GARENA_BASE}/oauth/token/grant",
                "platform": plat,
                tkey: tok,
                "app_id": GARENA_APP_ID,
                "client_type": "2",
                "response_type": "token",
            })

    # [2] Với client_secret (như guest token/grant)
    attempts.append({
        "_label": "token/grant +client_secret (raw key hex)",
        "_url": f"{GARENA_BASE}/oauth/token/grant",
        "platform": "4",
        "social_token": google_id_token,
        "app_id": GARENA_APP_ID,
        "client_type": "2",
        "response_type": "token",
        "client_secret": GARENA_KEY.hex(),
        "client_id": GARENA_APP_ID,
    })

    # [3] Với HMAC Authorization signature
    attempts.append({
        "_label": "token/grant +HMAC_sig",
        "_url": f"{GARENA_BASE}/oauth/token/grant",
        "_hmac": True,
        "platform": "4",
        "social_token": google_id_token,
        "app_id": GARENA_APP_ID,
        "client_type": "2",
        "response_type": "token",
    })

    # [4] /oauth/social/token (no /grant)
    attempts.append({
        "_label": "social/token (no grant)",
        "_url": f"{GARENA_BASE}/oauth/social/token",
        "platform": "4",
        "social_token": google_id_token,
        "app_id": GARENA_APP_ID,
        "client_type": "2",
        "response_type": "token",
    })

    # [5] /oauth/third_party/token/grant
    attempts.append({
        "_label": "third_party/token/grant",
        "_url": f"{GARENA_BASE}/oauth/third_party/token/grant",
        "platform": "4",
        "social_token": google_id_token,
        "app_id": GARENA_APP_ID,
        "client_type": "2",
        "response_type": "token",
    })

    # [6] /oauth/social/token/grant với client_secret
    attempts.append({
        "_label": "social/token/grant +client_secret",
        "_url": f"{GARENA_BASE}/oauth/social/token/grant",
        "platform": "4",
        "social_token": google_id_token,
        "app_id": GARENA_APP_ID,
        "client_type": "2",
        "response_type": "token",
        "client_secret": GARENA_KEY.hex(),
        "client_id": GARENA_APP_ID,
    })

    # ── Thực thi tuần tự ─────────────────────────────────
    log(f"[*] Thử {len(attempts)} endpoint variations...")

    for i, att in enumerate(attempts):
        url   = att.pop("_url")
        label = att.pop("_label")
        hmac_ = att.pop("_hmac", False)

        # Build headers
        hdrs = dict(headers_base)
        if hmac_:
            body_str = urllib.parse.urlencode(att)
            hdrs["Authorization"] = "Signature " + _hmac_sig(body_str)

        try:
            r = requests.post(url, headers=hdrs, data=att,
                              verify=False, timeout=12)
            short = r.text[:200].replace('\n', ' ')
            log(f"    [{i+1}] {label}")
            log(f"         HTTP {r.status_code}: {short}")

            if r.status_code == 200:
                js = r.json()
                if "access_token" in js and "open_id" in js:
                    log(f"\n✅ Tìm thấy endpoint đúng: {url}")
                    log(f"   Variant: {label}")
                    log(f"   Open ID: {js['open_id']}")
                    return js
                elif "access_token" in js:
                    log(f"   [!] Có access_token nhưng thiếu open_id: {js}")
            elif r.status_code != 404:
                log(f"   [!] Non-404 response — có thể gần đúng!")

        except Exception as e:
            log(f"    [{i+1}] {label} → Exception: {e}")

    log("\n❌ Tất cả {len(attempts)} variants đều thất bại.")
    log("   Garena có thể yêu cầu client_id riêng của họ cho Google OAuth.")
    log("   Xem log bên trên để phân tích response.")
    return None


# ── Build Google OAuth authorization URL ─────────────────────
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
