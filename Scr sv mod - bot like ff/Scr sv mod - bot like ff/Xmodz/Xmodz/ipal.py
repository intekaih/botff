from mitmproxy import http
import datetime
import base64

map_local = {
    "https://clientbp.ggpolarbear.com/GetBackpack": "GetBackpack",
    "https://clientbp.ggpolarbear.com/ChooseEmote": "ChooseEmote",
    "https://clientbp.ggpolarbear.com/ChooseSlotsAndShow": "ChooseSlotsAndShow",
    "https://clientbp.ggpolarbear.com/ChangeClothes": "ChangeClothes",
    "https://clientbp.ggpolarbear.com/GetPrimeAccountInfo": "prime",
    "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow": "GetPlayerPersonalShow",
     "https://clientbp.ggpolarbear.com/GetPlayerRecentMaxRank": "GetPlayerRecentMaxRank",
      "https://clientbp.ggpolarbear.com/GetPlayerRankingInfo": "GetPlayerRankingInfo",
       "https://clientbp.ggpolarbear.com/GetUnlockedFittingSlots": "GetUnlockedFittingSlots",
     "https://clientbp.ggpolarbear.com/GetVipCardInfo": "GetVipCardInfo",
     "https://clientbp.ggpolarbear.com/GetPlayerCSRankingInfoByAccountID": "GetPlayerCSRankingInfoByAccountID",
     "https://clientbp.ggpolarbear.com/GetWorkshopAuthorInfo": "GetWorkshopAuthorInfo",
}

def request(flow: http.HTTPFlow):
    """Xử lý request, map file cục bộ nếu có"""
    url = flow.request.url

    if url in map_local:
        try:
            with open(map_local[url], "rb") as f:
                flow.response = http.Response.make(
                    200, f.read(), {"Content-Type": "application/json"}
                )
        except Exception as e:
            flow.response = http.Response.make(500, f"Error: {str(e)}".encode())

def response(flow: http.HTTPFlow):
    """Cho phép tất cả request đi qua mà không bị block"""
    pass

