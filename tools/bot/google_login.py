"""
Google OAuth2 → Garena API → Free Fire JWT
Không cần MITM, không cần điện thoại, không cần jailbreak
"""

import hashlib
import hmac
import json
import os
import re
import time
import urllib.parse
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Garena API constants ─────────────────────────────────────
GARENA_APP_ID   = "100067"
GARENA_KEY      = bytes.fromhex(
    "3265653434383139653962343539383834353134313036376232383136323138"
    "374643306435643761663964386637653030633165353437313562376431653300"[:128]
)
GARENA_TOKEN_URL = "https://100067.connect.garena.com/oauth/social/token/grant"

# Platform IDs (Garena internal)
PLATFORM_GOOGLE   = 4
PLATFORM_FACEBOOK = 1
PLATFORM_VK       = 7

# ── Google OAuth constants ───────────────────────────────────
GOOGLE_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_SCOPES    = "openid email profile"


# ── Lấy Garena token từ Google token ────────────────────────
def garena_google_exchange(google_token: str, token_type: str = "id_token",
                            log_q=None) -> dict | None:
    """
    Đổi Google id_token / access_token → Garena access_token + open_id
    token_type: "id_token" hoặc "access_token"
    """
    def log(msg):
        if log_q:
            log_q.put(msg)

    log(f"[*] Gọi Garena social login API (platform=Google)...")

    headers = {
        "User-Agent": "GarenaMSDK/4.0.19P8(ASUS_Z01QD ;Android 12;en;US;)",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept-Encoding": "gzip",
        "Connection": "Keep-Alive",
    }

    # Thử 2 dạng token
    payloads = []

    if token_type == "id_token":
        payloads = [
            {   # Dạng 1: id_token làm social_token
                "platform": str(PLATFORM_GOOGLE),
                "social_token": google_token,
                "app_id": GARENA_APP_ID,
                "client_type": "2",
                "response_type": "token",
            },
            {   # Dạng 2: access_token param name khác
                "platform": str(PLATFORM_GOOGLE),
                "access_token": google_token,
                "app_id": GARENA_APP_ID,
                "client_type": "2",
                "response_type": "token",
            },
        ]
    else:
        payloads = [
            {
                "platform": str(PLATFORM_GOOGLE),
                "social_token": google_token,
                "app_id": GARENA_APP_ID,
                "client_type": "2",
                "response_type": "token",
            }
        ]

    for i, data in enumerate(payloads):
        try:
            log(f"[*] Thử dạng {i+1}/{len(payloads)}...")
            r = requests.post(
                GARENA_TOKEN_URL,
                headers=headers,
                data=data,
                verify=False,
                timeout=15,
            )
            log(f"    HTTP {r.status_code}: {r.text[:150]}")

            if r.status_code == 200:
                js = r.json()
                if "access_token" in js and "open_id" in js:
                    log(f"[+] Thành công! Open ID: {js['open_id']}")
                    return js
                elif "error" in js:
                    log(f"    Lỗi Garena: {js.get('error')} - {js.get('error_description','')}")
        except Exception as e:
            log(f"    Exception: {e}")

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
