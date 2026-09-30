#!/usr/bin/env bash
# Teste do APK no emulador: abre o app, carrega a foto de exemplo, espera as IAs, salva e confere a galeria.
set -x
adb install -r Revela.apk
adb shell am start -n com.revela.app/.MainActivity
sleep 30
PID=$(adb shell pidof com.revela.app | tr -d '\r')
adb forward tcp:9222 localabstract:webview_devtools_remote_$PID
curl -s http://localhost:9222/json/version || true
node scripts/test-apk.js || echo "TESTE FALHOU"
adb exec-out screencap -p > out/tela-final.png
adb shell content query --uri content://media/external/images/media --projection _display_name:relative_path:_size > out/galeria.txt 2>&1 || true
cat out/galeria.txt
adb logcat -d | grep -iE "Capacitor|chromium|Revela|Media" | tail -200 > out/logcat.txt || true
