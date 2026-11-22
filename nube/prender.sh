#!/usr/bin/env bash
# Prende un AVD y espera a que Android termine de arrancar.
# Uso: prender.sh <avd> [ventana] [extra flags...]
#   ventana: corre con ventana en el DISPLAY actual (sesión en vivo); si no, -no-window.
set -e
AVD=$1; shift
VENTANA=""
if [ "$1" = "ventana" ]; then VENTANA=1; shift; fi
mkdir -p ~/.android
printf '%s\n' "$ADB_KEY" > ~/.android/adbkey
printf '%s\n' "$ADB_KEY_PUB" > ~/.android/adbkey.pub
chmod 600 ~/.android/adbkey
adb kill-server >/dev/null 2>&1 || true
adb start-server >/dev/null 2>&1 || { sleep 2; adb start-server >/dev/null 2>&1 || true; }
W="-no-window"; [ -n "$VENTANA" ] && W=""
nohup emulator -avd "$AVD" $W -no-audio -no-boot-anim -no-snapshot -no-metrics \
  -gpu swiftshader_indirect -memory 4096 -cores 4 -accel on "$@" >> emulador.log 2>&1 &
ok=0
for i in $(seq 1 90); do
  b=$(adb shell getprop sys.boot_completed 2>/dev/null | tr -dc '0-9')
  [ "$b" = "1" ] && ok=1 && break
  sleep 5
done
[ $ok = 1 ] || { echo "no terminó de arrancar"; tail -40 emulador.log; exit 1; }
adb shell input keyevent 82 || true
for s in window_animation_scale transition_animation_scale animator_duration_scale; do
  adb shell settings put global $s 0 || true
done
adb shell settings put system screen_off_timeout 2147483647 || true
echo "prendido: $AVD"
