from mitmproxy import http
import os

# Chỉ map các endpoint cần serve file TĨNH (pre-dumped binary) thực sự
# Các endpoint động (ChooseSlotsAndShow, ChangeClothes, GetPlayerPersonalShow,
# GetBackpack, ChooseEmote) đã được xử lý bởi dump.py
map_local = {
    "https://clientbp.ggpolarbear.com/GetPrimeAccountInfo":               "prime",
    "https://clientbp.ggpolarbear.com/GetPlayerRecentMaxRank":            "GetPlayerRecentMaxRank",
    "https://clientbp.ggpolarbear.com/GetPlayerRankingInfo":              "GetPlayerRankingInfo",
    "https://clientbp.ggpolarbear.com/GetUnlockedFittingSlots":           "GetUnlockedFittingSlots",
    "https://clientbp.ggpolarbear.com/GetVipCardInfo":                    "GetVipCardInfo",
    "https://clientbp.ggpolarbear.com/GetPlayerCSRankingInfoByAccountID": "GetPlayerCSRankingInfoByAccountID",
    "https://clientbp.ggpolarbear.com/GetWorkshopAuthorInfo":             "GetWorkshopAuthorInfo",
}

def request(flow: http.HTTPFlow):
    """Serve file tĩnh đã dump sẵn cho các endpoint phụ (Rank, VIP, Workshop...)"""
    url = flow.request.url
    if url in map_local:
        fname = map_local[url]
        fpath = os.path.join(os.path.dirname(__file__), fname)
        try:
            with open(fpath, "rb") as f:
                flow.response = http.Response.make(
                    200, f.read(), {"Content-Type": "application/octet-stream"}
                )
            print(f"[📁] Static serve: {fname}")
        except FileNotFoundError:
            # File chưa dump → để request đi thẳng qua server thật, không bị gián đoạn
            print(f"[⚠️] Static file không tìm thấy: {fname} — pass-through")
        except Exception as e:
            flow.response = http.Response.make(500, f"Error: {str(e)}".encode())

def response(flow: http.HTTPFlow):
    """Pass-through tất cả response — các mod động xử lý ở dump.py"""
    pass
