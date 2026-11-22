#!/usr/bin/env bash
# Prepara la máquina de GitHub para el emulador: KVM, espacio, Android SDK.
set -e
echo 'KERNEL=="kvm", GROUP="kvm", MODE="0666", OPTIONS+="static_node=kvm"' | sudo tee /etc/udev/rules.d/99-kvm4all.rules >/dev/null
sudo udevadm control --reload-rules && sudo udevadm trigger --name-match=kvm
sudo rm -rf /usr/share/dotnet /opt/ghc /usr/local/share/boost /usr/local/lib/android/sdk/ndk || true
sudo mkdir -p /mnt/avd && sudo chown -R "$USER" /mnt/avd
sudo apt-get -qq update && sudo apt-get -qq install -y zstd ffmpeg >/dev/null
pip install -q pillow
SM=$ANDROID_SDK_ROOT/cmdline-tools/latest/bin/sdkmanager
yes | $SM --licenses >/dev/null || true
[ -d "$ANDROID_SDK_ROOT/system-images/android-34/google_apis_playstore/x86_64" ] || \
  $SM "system-images;android-34;google_apis_playstore;x86_64" >/dev/null
[ -x "$ANDROID_SDK_ROOT/emulator/emulator" ] || $SM "emulator" >/dev/null
$SM "platform-tools" >/dev/null
echo "$ANDROID_SDK_ROOT/platform-tools" >> "$GITHUB_PATH"
echo "$ANDROID_SDK_ROOT/emulator" >> "$GITHUB_PATH"
echo "ANDROID_AVD_HOME=/mnt/avd" >> "$GITHUB_ENV"
"$ANDROID_SDK_ROOT/emulator/emulator" -version | head -1
df -h / /mnt
