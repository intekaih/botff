#!/system/bin/sh
# BOT FF - ADB Token Extractor
# Ho tro: Free Fire (com.dts.freefireth) + Free Fire MAX (com.dts.freefiremax)

for PKG in com.dts.freefireth com.dts.freefiremax; do
  DIR=/data/data/$PKG
  if [ -d "$DIR" ]; then
    echo ""
    echo "==== $PKG ===="
    echo "-- SharedPreferences --"
    find $DIR/shared_prefs -name '*.xml' 2>/dev/null | while read f; do
      if grep -qi 'access_token\|open_id\|garena_token' "$f" 2>/dev/null; then
        echo "[FILE] $f"
        grep -i 'access_token\|open_id\|garena_token' "$f" 2>/dev/null
      fi
    done
    echo "-- Files JSON --"
    find $DIR/files -name '*.json' 2>/dev/null | head -5
  else
    echo "$PKG: not installed"
  fi
done
