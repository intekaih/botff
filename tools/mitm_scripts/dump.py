from mitmproxy import http
import blackboxprotobuf
import os

# ─── Đường dẫn tệp ────────────────────────────────────────────
_DIR = os.path.dirname(__file__)
IDS_FILE = os.path.join(_DIR, "extracted_ids.txt")

# ─── Skin Súng: tự động lấy từ extracted_ids.txt (prefix 907) ────────────
# GUN_SKIN_SLOTS không còn hardcode — sẽ build động từ danh sách ID súng.
# Slot index lấy từ server response gốc, chỉ thay item_id bằng skin từ kho.
# Nếu muốn ghim ID cụ thể, thêm vào FORCE_GUN_SKIN_IDS:
FORCE_GUN_SKIN_IDS = []   # ví dụ: [907001401, 907001501] — để rỗng = tự động

def get_ids_from_file(file_path):
    """Đọc file extracted_ids.txt và chuyển thành list ID"""
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        ids = [int(i.strip()) for i in content.split(",") if i.strip().isdigit()]
    return ids


def get_gun_skin_ids(file_path):
    """Lọc ID skin súng (907XXXXXXX) từ extracted_ids.txt.
    Ưu tiên FORCE_GUN_SKIN_IDS nếu được set."""
    if FORCE_GUN_SKIN_IDS:
        return FORCE_GUN_SKIN_IDS
    all_ids = get_ids_from_file(file_path)
    # Skin súng trong FF bắt đầu bằng 907
    gun_ids = [i for i in all_ids if 907000000 <= i <= 907999999]
    return gun_ids


def request(flow: http.HTTPFlow):
    url = flow.request.pretty_url
    
    # ── 0. NGĂN CHẶN LỖI SERVER KHI TRANG BỊ ĐỒ ──
    # Thay vì để request đi lên server (và bị server trả về lỗi do không có đồ),
    # ta chặn ngay ở Client, trả về file nhị phân Success chuẩn của Game.
    static_maps = {
        "ChooseSlotsAndShow": "ChooseSlotsAndShow",
        "ChooseEmote": "ChooseEmote",
        "ChangeClothes": "ChangeClothes"
    }
    
    for endpoint, file_name in static_maps.items():
        if endpoint in url:
            file_path = os.path.join(_DIR, file_name)
            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    flow.response = http.Response.make(
                        200, f.read(), {"Content-Type": "application/octet-stream"}
                    )
                print(f"\n[📦] Bypassed Request: {endpoint} -> Fake Success")
            else:
                print(f"\n[⚠️] Thiếu file tĩnh cho {endpoint}, pass-through to server")
            return


def response(flow: http.HTTPFlow):
    url = flow.request.pretty_url

    # ── 1. BYPASS VIP ─────────────────────────────────────────
    if "GetPrimeAccountInfo" in url:
        vip_hex = "08081008188094eb9a0f20f8bd0132050203050615"
        flow.response.content = bytes.fromhex(vip_hex)
        print("\n[💎] VIP BYPASS: OK")

    # ── 2. MOD BACKPACK (inject toàn bộ item từ extracted_ids) ─
    if "GetBackpack" in url:
        print("\n[🎒] Nạp item kho đồ từ extracted_ids.txt...")
        try:
            CLOTHES_IDS = get_ids_from_file(IDS_FILE)
            if not CLOTHES_IDS:
                print("⚠️  Không tìm thấy ID trong extracted_ids.txt!")
                return

            data, typedef = blackboxprotobuf.decode_message(bytes(flow.response.content))

            new_items = []
            for item_id in CLOTHES_IDS:
                new_items.append({
                    '1': item_id,
                    '2': 1,
                    '4': 18446744073709551615,   # expire = never
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
            flow.response.content = bytes(output[0] if isinstance(output, tuple) else output)
            print(f"✅ Backpack: nạp {len(new_items)} món đồ thành công!")

        except Exception as e:
            print(f"❌ LỖI MOD BACKPACK: {e}")

    # ── 3. MOD CHOOSE EMOTE ───────────────────────────────────
    if "ChooseEmote" in url:
        try:
            data, typedef = blackboxprotobuf.decode_message(bytes(flow.response.content))
            ids = [909000125, 909000071, 909041014, 909040005, 909039013, 909038004,
                   909037003, 909000137, 909034003, 909035006, 909000125, 909042001]
            if '1' in data and '8' in data['1']:
                data['1']['8'] = [{'1': {'1': idx, '2': eid}} for idx, eid in enumerate(ids, 1)]
            output = blackboxprotobuf.encode_message(data, typedef)
            flow.response.content = bytes(output[0] if isinstance(output, tuple) else output)
            print("✅ Emote: OK!")
        except Exception as e:
            print(f"❌ LỖI EMOTE: {e}")

    # ── 4. MOD CHOOSE SLOTS AND SHOW (Skin Súng hiển thị trong trận) ──
    # Endpoint này quyết định skin nào thực sự hiển thị trong trận.
    # Chiến lược: giữ nguyên cấu trúc slot từ server (slot index đúng với
    # vũ khí thực tế player đang cầm), chỉ thay item_id = skin súng từ kho.
    if "ChooseSlotsAndShow" in url:
        try:
            data, typedef = blackboxprotobuf.decode_message(bytes(flow.response.content))

            # Lấy danh sách skin súng từ extracted_ids
            gun_skin_ids = get_gun_skin_ids(IDS_FILE)
            if not gun_skin_ids:
                print("⚠️  Không tìm thấy ID skin súng (907XXXXXXX) trong extracted_ids.txt!")
                return

            # Field '1' chứa mảng các slot vũ khí
            # Mỗi slot: {'1': slot_index, '2': item_id}
            existing_slots = data.get('1', [])
            if not isinstance(existing_slots, list):
                existing_slots = [existing_slots] if existing_slots else []

            if not existing_slots:
                print("⚠️  ChooseSlotsAndShow: không có slot nào từ server — bỏ qua")
                return

            # Rotate qua danh sách skin súng để assign mỗi slot một skin khác nhau
            skin_cycle = gun_skin_ids
            skin_idx = 0
            for slot in existing_slots:
                if isinstance(slot, dict) and '1' in slot:
                    slot['2'] = skin_cycle[skin_idx % len(skin_cycle)]
                    skin_idx += 1

            data['1'] = existing_slots
            output = blackboxprotobuf.encode_message(data, typedef)
            flow.response.content = bytes(output[0] if isinstance(output, tuple) else output)
            print(f"✅ Slots: inject skin súng vào {len(existing_slots)} slot thành công!")
        except Exception as e:
            print(f"❌ LỖI CHOOSE SLOTS: {e}")

    # ── 5. MOD CHANGE CLOTHES (Cho phép thay đồ dynamic) ─────
    # Intercept nhưng pass-through để không bị lỗi static file,
    # client nhận response gốc từ server để có thể thay đồ thật sự.
    if "ChangeClothes" in url:
        # Nếu server trả 200 thì pass-through không cần fake
        if flow.response.status_code == 200:
            print("✅ ChangeClothes: pass-through (server OK)")
        else:
            # Server lỗi → fake thành success rỗng
            flow.response.status_code = 200
            flow.response.content = b''
            print("⚠️  ChangeClothes: server lỗi → fake success")

    # ── 6. GET PLAYER PERSONAL SHOW (hiển thị trong trận + xem nick) ──
    # Đây là endpoint game gọi khi vào trận để lấy outfit hiển thị.
    # Inject toàn bộ item vào đây để thấy đồ cả trong trận.
    if "GetPlayerPersonalShow" in url:
        try:
            CLOTHES_IDS = get_ids_from_file(IDS_FILE)
            if not CLOTHES_IDS:
                return

            data, typedef = blackboxprotobuf.decode_message(bytes(flow.response.content))

            # Field '1' = PlayerPersonalShow, con field '3' = danh sách item show
            if '1' not in data:
                data['1'] = {}
            show_entry = data['1']

            show_items = []
            for item_id in CLOTHES_IDS:
                show_items.append({
                    '1': item_id,
                    '2': 1,
                    '4': 18446744073709551615,
                    '5': 1,
                    '7': 1,   # ← FIX: field này bắt buộc để render đồ TRONG TRẬN
                    '8': 9
                })
            show_entry['3'] = show_items
            data['1'] = show_entry

            output = blackboxprotobuf.encode_message(data, typedef)
            flow.response.content = bytes(output[0] if isinstance(output, tuple) else output)
            print(f"✅ PersonalShow: inject {len(show_items)} item (hiển thị trong trận) OK!")
        except Exception as e:
            print(f"❌ LỖI GET_PLAYER_PERSONAL_SHOW: {e}")