grep -aroE 'eyJ[A-Za-z0-9_-]{30,}\.[A-Za-z0-9_-]{30,}\.[A-Za-z0-9_-]{30,}' /data/data/com.dts.freefiremax/ 2>/dev/null
grep -aroE '"access_token"[^>]*>[^<]+' /data/data/com.dts.freefiremax/ 2>/dev/null
