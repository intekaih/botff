"""
Probe Garena API để tìm endpoint đúng cho Google social login.
Chạy: python tools/bot/probe_garena_social.py <google_id_token>
"""
import sys
import hmac
import hashlib
import requests
import urllib3
urllib3.disable_warnings()

HEX_KEY = "32656534343831396539623435393838343531343130363762323831363231383734643064356437616639643866376530306331653534373135623764316533"
KEY     = bytes.fromhex(HEX_KEY)
APP_ID  = "100067"

BASE_URLS = [
    "https://100067.connect.garena.com",
]

PATHS = [
    "/oauth/token/grant",
    "/oauth/social/token/grant",
    "/oauth/social/token",
    "/oauth/social/login",
    "/oauth/third_party/token/grant",
]

PLATFORM_VARIANTS = [
    ("4", "id_token_key"),
    ("google", "id_token_key"),
    ("4", "social_token"),
    ("google", "social_token"),
]

HDRS = {
    "User-Agent": "GarenaMSDK/4.0.19P8(ASUS_Z01QD ;Android 12;en;US;)",
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept-Encoding": "gzip",
    "Connection": "Keep-Alive",
}


def try_endpoint(url, data, extra_headers=None):
    h = dict(HDRS)
    if extra_headers:
        h.update(extra_headers)
    try:
        r = requests.post(url, headers=h, data=data, verify=False, timeout=10)
        return r.status_code, r.text[:300]
    except Exception as e:
        return 0, str(e)


def make_sig(data_str):
    return hmac.new(KEY, data_str.encode(), hashlib.sha256).hexdigest()


def probe(google_token: str):
    results = []

    for base in BASE_URLS:
        for path in PATHS:
            url = base + path

            # Variant 1: basic payload
            for plat, token_key in PLATFORM_VARIANTS:
                data = {
                    "platform": plat,
                    token_key: google_token,
                    "app_id": APP_ID,
                    "client_type": "2",
                    "response_type": "token",
                }
                sc, txt = try_endpoint(url, data)
                if sc != 404:
                    print(f"  🔥 INTERESTING [{sc}] {url} platform={plat} key={token_key}")
                    print(f"     → {txt}")
                results.append((sc, url, plat, token_key, "no_sig", txt[:80]))

            # Variant 2: with client_secret (like guest token)
            data_cs = {
                "platform": "4",
                "social_token": google_token,
                "app_id": APP_ID,
                "client_type": "2",
                "response_type": "token",
                "client_secret": KEY.hex(),
                "client_id": APP_ID,
            }
            sc, txt = try_endpoint(url, data_cs)
            if sc != 404:
                print(f"  🔥 INTERESTING [{sc}] {url} +client_secret")
                print(f"     → {txt}")
            results.append((sc, url, "4", "social_token", "client_secret", txt[:80]))

            # Variant 3: with HMAC signature in header
            data_s = f"platform=4&social_token={google_token}&app_id={APP_ID}&client_type=2&response_type=token"
            sig = make_sig(data_s)
            sc, txt = try_endpoint(url, data_s, {"Authorization": f"Signature {sig}"})
            if sc != 404:
                print(f"  🔥 INTERESTING [{sc}] {url} +HMAC_sig")
                print(f"     → {txt}")
            results.append((sc, url, "4", "social_token", "hmac_sig", txt[:80]))

    print("\n── Tổng kết (chỉ non-404) ──")
    for sc, url, plat, key, mode, txt in results:
        if sc != 404:
            print(f"  [{sc}] {url} plat={plat} key={key} mode={mode}")
            print(f"       {txt}")

    print("\n── Tất cả responses ──")
    for sc, url, plat, key, mode, txt in results:
        print(f"  [{sc}] {url.split('.com')[1]} plat={plat} key={key} mode={mode}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python probe_garena_social.py <google_id_token>")
        sys.exit(1)
    tok = sys.argv[1]
    print(f"[*] Token: {tok[:30]}...")
    probe(tok)
