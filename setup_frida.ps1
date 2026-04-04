$ErrorActionPreference = "Stop"

$FRIDA_VERSION = "17.9.1"
$URL = "https://github.com/frida/frida/releases/download/$FRIDA_VERSION/frida-server-$FRIDA_VERSION-android-arm64.xz"
$XZ_FILE = "frida-server.xz"
$BIN_FILE = "frida-server"

Write-Host "Downloading frida-server $FRIDA_VERSION..."
Invoke-WebRequest -Uri $URL -OutFile $XZ_FILE

Write-Host "Extracting..."
# PowerShell doesn't have native xz extraction, using Python
python -c "import lzma; data=lzma.open('frida-server.xz').read(); open('frida-server', 'wb').write(data)"

Write-Host "Pushing to device..."
adb push frida-server /data/local/tmp/
adb shell "su -c 'chmod 755 /data/local/tmp/frida-server'"

Write-Host "Starting frida-server..."
adb shell "su -c 'killall frida-server 2>/dev/null'"
# Run inside nohup or background
adb shell "su -c '/data/local/tmp/frida-server -D'"

Write-Host "Done!"
