import requests

def check_account_info(uid, token):
    url1 = f"https://account.garena.com/api/account/profile?account_id={uid}&session_key={token}"
    url2 = f"https://100067.connect.garena.com/oauth/user/info?access_token={token}&open_id={uid}"
    url3 = f"https://connect.garena.com/api/user/info?access_token={token}&open_id={uid}"
    
    headers = {
        "User-Agent": "GarenaMSDK/4.0.19P8(ASUS_Z01QD ;Android 12;en;US;)",
        "Authorization": f"Bearer {token}"
    }
    
    body = {
        "access_token": token,
        "open_id": uid
    }
    
    for url in [url1, url2, url3]:
        try:
            r = requests.get(url, headers=headers)
            print(f"GET {url}: {r.status_code}")
            print(r.text)
        except Exception as e:
            pass

check_account_info("123", "abc")
