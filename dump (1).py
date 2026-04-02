


from mitmproxy import http
import blackboxprotobuf
import os

def get_ids_from_file(file_path):
    """Đọc file extracted_ids.txt và chuyển thành list ID"""
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        ids = [int(i.strip()) for i in content.split(",") if i.strip().isdigit()]
    return ids

def response(flow: http.HTTPFlow):
    url = flow.request.pretty_url

    # --- 1. BYPASS VIP ---
    if "GetPrimeAccountInfo" in url:
        vip_hex = "08081008188094eb9a0f20f8bd0132050203050615"
        flow.response.content = bytes.fromhex(vip_hex)
        print("\n[💎] VIP BYPASS: OK")

    # --- 2. MOD BACKPACK (LẤY ID TỪ FILE EXTRACTED_IDS.TXT) ---
    if "GetBackpack" in url:
        print(f"\n[🎒] ĐANG NẠP ID TỪ FILE extracted_ids.txt...")
        try:

            CLOTHES_IDS = get_ids_from_file("extracted_ids.txt")
            
            if not CLOTHES_IDS:
                print("⚠️ CẢNH BÁO: Không tìm thấy ID nào trong extracted_ids.txt!")
                return
            source_content = bytes(flow.response.content)
            data, typedef = blackboxprotobuf.decode_message(source_content)

            new_items = []
            for item_id in CLOTHES_IDS:
                new_items.append({
                    '1': item_id,                  
                    '2': 1,                        
                    '4': 18446744073709551615,    
                    '5': 1, 
                    '7': 1, 
                    '8': 9                         
                })

            data['3'] = new_items

            if '2' in data and isinstance(data['2'], dict):
                data['2']['2'] = len(new_items)
            else:
                data['2'] = {'2': len(new_items)}

            output = blackboxprotobuf.encode_message(data, typedef)
            encoded_data = output[0] if isinstance(output, tuple) else output

            flow.response.content = bytes(encoded_data)
            print(f"✅ [SUCCESS] Đã nạp thành công {len(new_items)} món đồ từ file extracted_ids.txt!")

        except Exception as e:
            print(f"❌ LỖI MOD BACKPACK: {str(e)}")

    # --- 3. MOD CHOOSE EMOTE ---
    if "ChooseEmote" in url:
        try:
            data, typedef = blackboxprotobuf.decode_message(bytes(flow.response.content))
            ids = [909000125, 909000071, 909041014, 909040005, 909039013, 909038004, 
                   909037003, 909000137, 909034003, 909035006, 909000125, 909042001]
            if '1' in data and '8' in data['1']:
                data['1']['8'] = [{'1': {'1': idx, '2': eid}} for idx, eid in enumerate(ids, 1)]
            
            output = blackboxprotobuf.encode_message(data, typedef)
            flow.response.content = bytes(output[0] if isinstance(output, tuple) else output)
            print("✅ [SUCCESS] Mod Emote OK!")
        except Exception as e: print(f"❌ LỖI EMOTE: {e}")
            