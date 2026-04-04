import sys
sys.path.append('.')
import re
import pprint
from tools.bot.account_info import check_account_info, decode_jwt_claims

def run_test():
    try:
        with open('extracted.txt', 'rb') as f:
            text = f.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"Error reading file: {e}")
        return

    print("Searching for JWTs...")
    jwts = list(set(re.findall(r'eyJ[A-Za-z0-9_\-]{30,}\.[A-Za-z0-9_\-]{30,}\.[A-Za-z0-9_\-]{30,}', text)))
    
    # Also search for MSDK authToken
    auth_tokens = list(set(re.findall(r'authToken.*?(?:val:|value="|name="authToken">)([\da-fA-F]{64})', text, re.IGNORECASE)))

    print(f"Found {len(jwts)} JWTs.")
    for i, jwt in enumerate(jwts):
        print(f"\n[+] Testing JWT {i+1}: {jwt[:20]}...{jwt[-10:]}")
        claims = decode_jwt_claims(jwt)
        print("  - Decoded claims keys:", list(claims.keys()) if claims else "None")
        if claims and 'account_id' in claims:
            # Only test with actual game JWTs
            res = check_account_info(jwt, "")
            if res.get("summary"):
                print("= JWT SUMMARY =")
                for k, v in res["summary"].items():
                    print(f"  {k}: {v}")
            if res.get("player_info"):
                print("= PLAYER INFO =")
                for k, v in list(res["player_info"].items())[:5]:
                    print(f"  {k}: {v}")

    print(f"\nFound {len(auth_tokens)} MSDK Auth Tokens.")
    for i, t in enumerate(auth_tokens):
        print(f"\n[+] Testing MSDK Token {i+1}: {t}")
        # Need openId to go with authToken, roughly scanning for openId nearby
        res = check_account_info(t, "")
        if res.get("garena_info"):
            for k, v in res["garena_info"].items():
                print(f"  {k}: {v}")

    # Searching for normal access_token (> 50 chars, no eyJ)
    garena_tokens = list(set(re.findall(r'(?:access_token|garena_token).*?val: \s*([a-zA-Z0-9_\-]{50,})', text)))
    print(f"\nFound {len(garena_tokens)} OAuth Tokens.")
    for i, t in enumerate(garena_tokens):
        print(f"\n[+] Testing OAuth Token {i+1}: {t[:10]}...{t[-10:]}")
        res = check_account_info(t, "")
        if res.get("garena_info"):
            for k, v in res["garena_info"].items():
                print(f"  {k}: {v}")

if __name__ == "__main__":
    run_test()
