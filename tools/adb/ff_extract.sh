#!/system/bin/sh
# BOT FF - ADB Token Extractor v2
# Ho tro: Free Fire (com.dts.freefireth) + Free Fire MAX (com.dts.freefiremax)
# Tim: access_token (OAuth) + JWT game + authToken/openId (MSDK)

DIVIDER="========================================"

for PKG in com.dts.freefireth com.dts.freefiremax; do
  DIR=/data/data/$PKG
  if [ -d "$DIR" ]; then
    echo ""
    echo "$DIVIDER"
    echo ">>> PACKAGE: $PKG"
    echo "$DIVIDER"

    echo ""
    echo "--- [1] Tim JWT game (starts with eyJ) ---"
    find $DIR -name '*.xml' -o -name '*.json' -o -name '*.dat' 2>/dev/null | while read f; do
      grep -oE 'eyJ[A-Za-z0-9_\-]{50,}\.[A-Za-z0-9_\-]{50,}\.[A-Za-z0-9_\-]{30,}' "$f" 2>/dev/null | while read jwt; do
        echo "[JWT FOUND in $f]"
        echo "  $jwt"
      done
    done

    echo ""
    echo "--- [2] Tim token OAuth (access_token / garena_token dai > 50 ky tu) ---"
    find $DIR/shared_prefs -name '*.xml' 2>/dev/null | while read f; do
      echo "[XML] $f:"
      # Lay tat ca string value dai > 30 ky tu
      grep -oE 'name="[^"]*" *>[^<]{30,}</string' "$f" 2>/dev/null | sed 's/name="/  key: /;s/" *>/  val: /;s/<\/string//'
      grep -oE 'name="[^"]*">[^<]{15,}</string' "$f" 2>/dev/null | sed 's/name="/  key: /;s/">/  val: /;s/<\/string//'
    done

    echo ""
    echo "--- [3] Tim authToken + openId (MSDK GarenaSDK) ---"
    find $DIR/shared_prefs -name '*.xml' 2>/dev/null | xargs grep -hiE 'authToken|openId|access_token|open_id|garena_token|session_key' 2>/dev/null

    echo ""
    echo "--- [4] Danh sach tat ca XML files ---"
    find $DIR/shared_prefs -name '*.xml' 2>/dev/null | while read f; do
      SIZE=$(wc -c < "$f" 2>/dev/null || echo 0)
      echo "  $f ($SIZE bytes)"
    done

    echo ""
    echo "--- [5] Files JSON trong /files ---"
    find $DIR/files -name '*.json' 2>/dev/null | head -10 | while read f; do
      echo "  $f"
      cat "$f" 2>/dev/null | head -3
    done

  else
    echo "$PKG: chua cai dat"
  fi
done

echo ""
echo "$DIVIDER"
echo "HOAN THANH"
echo "$DIVIDER"
