from mitmproxy import http
import datetime
import base64

map_local = {
    "https://clientbp.ggpolarbear.com/GetBackpack": "list",
}
def request(flow: http.HTTPFlow):
    """Xử lý request, map file cục bộ nếu có"""
    url = flow.request.url

    if url in map_local:
        try:
            import os
            with open(os.path.join(os.path.dirname(__file__), map_local[url]), "rb") as f:
                flow.response = http.Response.make(
                    200, f.read(), {"Content-Type": "application/json"}
                )
        except Exception as e:
            flow.response = http.Response.make(500, f"Error: {str(e)}".encode())

def response(flow: http.HTTPFlow):
    """Cho phép tất cả request đi qua mà không bị block"""
    pass

