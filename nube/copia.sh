#!/usr/bin/env bash
# La copia del celular (AVD eugenia_cel) en GitHub, cifrada.
#
# Cada copia vive en su propio release "cel-<corrida>". El archivo copia_actual.txt del repo
# dice cuál se usa. Una copia nueva se sube COMPLETA a su release, se verifica, y recién
# ahí se cambia copia_actual.txt. Si algo corta la subida a la mitad, la copia en uso
# no se toca (22/11: un guardado cortado destruyó la copia y tiró todas las historias).
#
# Uso: copia.sh restaurar | copia.sh guardar
set -e
AVD=/mnt/avd/eugenia_cel.avd
INI=/mnt/avd/eugenia_cel.ini
R=${GITHUB_REPOSITORY:-tomixrecoil/eugenia-celular}
enc() { openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass env:EMU_CLAVE; }
dec() { openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass env:EMU_CLAVE; }

escribir_ini() {
  printf 'avd.ini.encoding=UTF-8\npath=%s\ntarget=android-34\n' "$AVD" > "$INI"
}

restaurar() {
  # 23/11: SIEMPRE la última copia guardada (origin/main), no la del commit con el que se
  # lanzó la corrida: una corrida que esperó en cola arrancaba con una copia vieja, y
  # volver a una copia vieja después de usar una más nueva es lo que bloqueó a hidroponía.
  git fetch -q origin main && git show origin/main:copia_actual.txt > copia_actual.txt
  TAG=$(cat copia_actual.txt | tr -d '[:space:]')
  [ -n "$TAG" ] || { echo "no hay copia_actual.txt"; exit 1; }
  echo "copia: $TAG"
  D=/mnt/avd/dl; rm -rf "$D"; mkdir -p "$D" "$AVD"
  gh release download "$TAG" -R "$R" -D "$D"
  ls -la "$D"
  # Verifica que estén todas las partes que dice el índice
  dec < "$D/indice.enc" > "$D/indice.txt"
  while read -r nombre tam; do
    real=$(stat -c %s "$D/$nombre")
    [ "$real" = "$tam" ] || { echo "parte incompleta: $nombre $real != $tam"; exit 1; }
  done < "$D/indice.txt"
  cat $(ls "$D"/datos.part*.enc | sort) | dec | zstd -d -q -o "$AVD/userdata-qemu.img"
  dec < "$D/resto.tgz.enc" | tar -xz -C "$AVD"
  rm -rf "$D"
  escribir_ini
  ls -la "$AVD"
}

guardar() {
  # Apagado limpio: que Android escriba todo antes de copiar
  adb shell sync || true
  adb emu kill || true
  for i in $(seq 1 30); do pgrep -f qemu-system >/dev/null || break; sleep 2; done
  pkill -f qemu-system || true; sleep 3
  O=/mnt/avd/guardar; rm -rf "$O"; mkdir -p "$O"
  Q=$ANDROID_SDK_ROOT/emulator/qemu-img
  if [ -f "$AVD/userdata-qemu.img.qcow2" ]; then
    $Q convert -O raw "$AVD/userdata-qemu.img.qcow2" "$O/userdata.raw"
  else
    cp --sparse=always "$AVD/userdata-qemu.img" "$O/userdata.raw"
  fi
  ls -la "$O"
  zstd -T0 -3 -q -c "$O/userdata.raw" | enc | split -b 1900000000 -d -a 1 - "$O/datos.part"
  for f in "$O"/datos.part?; do mv "$f" "$f.enc"; done
  rm -f "$O/userdata.raw"
  (cd "$AVD" && tar -czf - --exclude='userdata-qemu.img*' --exclude='*.lock' --exclude='snapshots' .) | enc > "$O/resto.tgz.enc"
  (cd "$O" && for f in datos.part*.enc resto.tgz.enc; do echo "$f $(stat -c %s "$f")"; done) > "$O/indice.txt"
  enc < "$O/indice.txt" > "$O/indice.enc"; rm "$O/indice.txt"
  TAG="cel-${GITHUB_RUN_ID:-manual}-${GITHUB_RUN_ATTEMPT:-1}"
  gh release create "$TAG" -R "$R" --title "$TAG" --notes "copia del celular (cifrada)" --latest=false
  gh release upload "$TAG" -R "$R" "$O"/datos.part*.enc "$O/resto.tgz.enc" "$O/indice.enc"
  # Verificación: cada archivo subido con el tamaño exacto
  for f in "$O"/datos.part*.enc "$O/resto.tgz.enc" "$O/indice.enc"; do
    n=$(basename "$f"); t=$(stat -c %s "$f")
    s=$(gh release view "$TAG" -R "$R" --json assets -q ".assets[]|select(.name==\"$n\")|.size")
    [ "$s" = "$t" ] || { echo "subida incompleta: $n ($s != $t). La copia en uso no se toca."; exit 1; }
  done
  ANT=$(cat copia_actual.txt 2>/dev/null | tr -d '[:space:]' || true)
  echo "$TAG" > copia_actual.txt
  # 23/11: el puntero se cambia directo en GitHub (API), no con commit + pull --rebase: si
  # otra corrida ya lo había cambiado, el rebase chocaba en copia_actual.txt y la copia nueva
  # quedaba sin usar (y la próxima corrida volvía a una copia vieja).
  for i in 1 2 3 4 5; do
    sha=$(gh api "repos/$R/contents/copia_actual.txt?ref=main" -q .sha)
    gh api -X PUT "repos/$R/contents/copia_actual.txt" -f message="copia del celular: $TAG" -f content="$(echo "$TAG" | base64 -w0)" -f sha="$sha" -f branch=main >/dev/null && break
    sleep 5
  done
  git fetch -q origin main
  [ "$(git show origin/main:copia_actual.txt | tr -d '[:space:]')" = "$TAG" ] || {
    echo "NO pude dejar en uso la copia $TAG: no borro nada"; exit 1; }
  echo "copia nueva en uso: $TAG (antes: ${ANT:-ninguna})"
  # Se guardan la actual y la anterior; las más viejas se borran
  for t in $(gh release list -R "$R" --limit 100 --json tagName -q '.[].tagName' | grep '^cel-'); do
    [ "$t" = "$TAG" ] || [ "$t" = "$ANT" ] || gh release delete "$t" -R "$R" -y --cleanup-tag
  done
}

"$@"
