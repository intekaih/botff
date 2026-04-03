import os
from reg import token, create_acc

print("Test creating acc and getting token...")
res = create_acc("VN")
print(res)

print("Test existing acc...")
uid = res['uid']
password = res['password']
res2 = token(uid, password, "VN")
print("Response from token() for EXISTING account:")
print(res2)
