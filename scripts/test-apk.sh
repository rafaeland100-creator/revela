#!/usr/bin/env bash
# Teste do APK no emulador: abre o app, carrega fotos, espera as IAs, salva e confere a galeria.
set -x
adb install -r Revela.apk

# Num emulador recém-ligado o Google Play Services costuma reiniciar para se atualizar. Quando isso acontece,
# o Android encerra os apps que estão usando o provedor de fontes dele ("depends on provider ... in dying proc").
# Por isso: espera o sistema assentar e, se o app for encerrado no meio, tenta mais uma vez.
sleep 90

rodar() {
  adb shell am force-stop com.revela.app
  adb shell am start -n com.revela.app/.MainActivity
  sleep 30
  PID=$(adb shell pidof com.revela.app | tr -d '\r')
  adb forward --remove-all || true
  adb forward tcp:9222 localabstract:webview_devtools_remote_$PID
  curl -s http://localhost:9222/json/version || true
  node scripts/test-apk.js
  R=$?
  PID2=$(adb shell pidof com.revela.app | tr -d '\r')
  echo "processo do app: $PID no começo, ${PID2:-encerrado} no fim | saída do teste: $R" | tee -a out/resultado.txt
  [ "$R" = "0" ] && [ "$PID" = "$PID2" ]
}

if ! rodar; then
  echo "=== o app parou no meio. O que o Android registrou: ===" | tee -a out/resultado.txt
  adb logcat -d | grep -E "Killing [0-9]+:com.revela.app|FATAL EXCEPTION|ANR in com.revela.app" | tail -5 | tee -a out/resultado.txt
  echo "=== segunda tentativa ===" | tee -a out/resultado.txt
  sleep 60
  rodar || echo "TESTE FALHOU nas duas tentativas" | tee -a out/resultado.txt
fi

adb exec-out screencap -p > out/tela-final.png
adb shell content query --uri content://media/external/images/media --projection _display_name:relative_path:_size > out/galeria.txt 2>&1 || true
adb shell ls -la /sdcard/Pictures/Revela >> out/galeria.txt 2>&1 || true
cat out/galeria.txt
adb logcat -d > out/logcat-completo.txt 2>&1 || true
grep -iE "Capacitor|chromium|revela|Media|FATAL|ANR|lowmem" out/logcat-completo.txt | tail -300 > out/logcat.txt || true
