import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

try:
    import blackboxprotobuf
except ImportError:
    blackboxprotobuf = None

def _enc_varint(n: int) -> bytes:
    H = []
    while True:
        b = n & 0x7F; n >>= 7
        if n: b |= 0x80
        H.append(b)
        if not n: break
    return bytes(H)

def _field_varint(field: int, value: int) -> bytes:
    return _enc_varint((field << 3) | 0) + _enc_varint(value)

def build_like_payload(target_uid: int) -> bytes:
    # 1: target_uid, 2: source (e.g. 1 or 2)
    return _field_varint(1, target_uid) + _field_varint(2, 1) + _field_varint(3, 1)

_AES_KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
_AES_IV  = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69,  51, 121, 99, 104, 106, 77, 37])

def aes_encrypt(raw: bytes) -> bytes:
    cipher = AES.new(_AES_KEY, AES.MODE_CBC, _AES_IV)
    return cipher.encrypt(pad(raw, AES.block_size))

def aes_decrypt(enc: bytes) -> bytes:
    cipher = AES.new(_AES_KEY, AES.MODE_CBC, _AES_IV)
    return unpad(cipher.decrypt(enc), AES.block_size)

jwt_token = "eyJhbGciOiJIUzI1NiIsInN2ciI6IjEiLCJ0eXAiOiJKV1QifQ.eyJhY2NvdW50X2lkIjoxNTI3MjkyMDQ5Niwibmlja25hbWUiOiJkaF9ZMVNQUjMyOCIsIm5vdGlfcmVnaW9uIjoiVk4iLCJsb2NrX3JlZ2lvbiI6IlZOIiwiZXh0ZXJuYWxfaWQiOiJmNDZjNTU5OTA0ZmVkMzNhYzQ2ZGU3MzA4YmM0MDQ0MSIsImV4dGVybmFsX3R5cGUiOjQsInBsYXRfaWQiOjEsImNsaWVudF92ZXJzaW9uIjoiMS4xMTQuMTMiLCJlbXVsYXRvcl9zY29yZSI6MTAwLCJpc19lbXVsYXRvciI6dHJ1ZSwiY291bnRyeV9jb2RlIjoiVk4iLCJleHRlcm5hbF91aWQiOjQ2ODQ1MDE2NzIsInJlZ19hdmF0YXIiOjEwMjAwMDAwNywic291cmNlIjowLCJsb2NrX3JlZ2lvbl90aW1lIjoxNzc1MTQ3NDY1LCJjbGllbnRfdHlwZSI6Miwic2lnbmF0dXJlX21kNSI6Ijc0MjhiMjUzZGVmYzE2NDAxOGM2MDRhMWViYmZlYmRmIiwidXNpbmdfdmVyc2lvbiI6MSwicmVsZWFzZV9jaGFubmVsIjoiYW5kcm9pZCIsInJlbGVhc2VfdmVyc2lvbiI6Ik9CNTIiLCJleHAiOjE3NzUxNzYyNjV9.VAqMFhtDjAlQLVyimi5TMGxWNsGM6SRgqyDkdcVly0Y"
target_uid = 14210443593

url = "https://clientbp.ggblueshark.com/GetPlayerPersonalShow"
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

payload = build_like_payload(target_uid)
print(f"Plaintext Protobuf Hex: {payload.hex()}")
encrypted_payload = aes_encrypt(payload)

resp = requests.post(url, headers=headers, data=encrypted_payload, verify=False)
print("Status Code:", resp.status_code)
print("Response Length:", len(resp.content))

if len(resp.content) > 0:
    try:
        dec_resp = aes_decrypt(resp.content)
        print("Decrypted Response Hex:", dec_resp.hex())
        if blackboxprotobuf:
            try:
                val, typedef = blackboxprotobuf.decode_message(dec_resp)
                print("Decoded Protobuf:", val)
            except Exception as e:
                print("blackboxprotobuf decode failed:", e)
    except Exception as e:
        print("AES decrypt failed:", e)
        print("Response Hex:", resp.content.hex())
