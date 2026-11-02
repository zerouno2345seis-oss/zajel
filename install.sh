#!/bin/bash
# مثبّت «زاجل» على جهاز ماك آخر.
# الاستعمال:  bash install.sh            (يسأل عند اللزوم)
# خيارات:     --dir المسار   --yes   --no-dock   --no-app   --skip-deps
set -u
SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/PhoneBackup"; YES=0; DOCK=ask; MAKEAPP=1; DEPS=1
while [ $# -gt 0 ]; do
  case "$1" in
    --dir) DEST="$2"; shift;;
    --yes) YES=1;;
    --no-dock) DOCK=no;;
    --no-app) MAKEAPP=0;;
    --skip-deps) DEPS=0;;
  esac
  shift
done
say() { printf '%s\n' "$*"; }
ask() { [ "$YES" = 1 ] && return 0; printf '%s [y/N] ' "$1"; read -r a; [ "$a" = y ] || [ "$a" = Y ]; }

say "== تثبيت زاجل =="
say "المجلد الهدف:"
say "$DEST"

if [ "$DEPS" = 1 ]; then
  command -v python3 >/dev/null 2>&1 || { say "python3 غير موجود. شغّل أولًا: xcode-select --install"; exit 1; }
  if ! python3 -c "import PIL" 2>/dev/null; then
    say "تثبيت مكتبة الصور (Pillow) لمصغّرات الصور…"
    python3 -m pip install --user pillow >/dev/null 2>&1 || python3 -m pip install --user --break-system-packages pillow || { say "تعذّر تثبيت Pillow"; exit 1; }
  fi
  ADB="$(command -v adb || true)"
  if [ -z "$ADB" ]; then
    for c in /opt/homebrew/bin/adb /usr/local/bin/adb "$HOME/Library/Android/sdk/platform-tools/adb"; do [ -x "$c" ] && ADB="$c" && break; done
  fi
  if [ -z "$ADB" ]; then
    if command -v brew >/dev/null 2>&1 && ask "أداة adb (الاتصال بالهاتف والساعة) غير مثبّتة. أثبّتها عبر Homebrew؟ (تنزيل من الإنترنت)"; then
      brew install android-platform-tools
    else
      say "تنبيه: بدون adb لا يعمل الهاتف والساعة، ويبقى الكمبيوتر والأقراص والسحابة."
      say "لتثبيته لاحقًا: brew install android-platform-tools"
    fi
  fi
fi


# rclone: الحسابات السحابية المباشرة (جوجل/وان درايف/دروبوكس...) — اختياري
if ! command -v rclone >/dev/null 2>&1 && [ ! -x /opt/homebrew/bin/rclone ]; then
  if command -v brew >/dev/null 2>&1 && ask "أداة rclone (للحسابات السحابية المباشرة) غير مثبّتة. أثبّتها عبر Homebrew؟ (تنزيل من الإنترنت)"; then
    brew install rclone
  else
    say "بدون rclone تعمل الأداة لكن لا تظهر الحسابات السحابية المباشرة. لتثبيته لاحقًا: brew install rclone"
  fi
fi


# libimobiledevice: قراءة iPhone وiPad (بالكابل أو الواي فاي) — اختياري
if [ ! -x /opt/homebrew/bin/idevice_id ] && ! command -v idevice_id >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1 && ask "أداة قراءة iPhone/iPad (libimobiledevice) غير مثبّتة. أثبّتها عبر Homebrew؟ (تنزيل من الإنترنت)"; then
    brew install libimobiledevice
  else
    say "بدونها لا يظهر iPhone/iPad. لتثبيتها لاحقًا: brew install libimobiledevice"
  fi
fi

# أدوات المطوّرين من آبل: لبناء النافذة الأصلية وأداة التعرّف على الصور (مجانية)
if [ "$MAKEAPP" = 1 ] && ! { [ -x /usr/bin/swiftc ] && /usr/bin/swiftc --version >/dev/null 2>&1; }; then
  if ask "أدوات المطوّرين من آبل غير مثبّتة (لازمة للنافذة الأصلية والتعرّف على الصور). أفتح نافذة تثبيتها؟"; then
    xcode-select --install >/dev/null 2>&1
    say "اضغط «تثبيت» في النافذة التي ظهرت. أنتظر حتى ينتهي التثبيت (حتى 30 دقيقة)…"
    for _ in $(seq 360); do /usr/bin/swiftc --version >/dev/null 2>&1 && break; sleep 5; done
    /usr/bin/swiftc --version >/dev/null 2>&1 && say "ثُبّتت أدوات المطوّرين." || say "لم تكتمل؛ سيُبنى تطبيق يفتح الأداة في المتصفح بدل النافذة الأصلية."
  fi
fi

# Calibre: أغلفة الكتب، وإعادة تسمية الكتب، والتحويل التلقائي إلى صيغة الكيندل — اختياري
if [ "$DEPS" = 1 ] && [ ! -d /Applications/calibre.app ]; then
  if command -v brew >/dev/null 2>&1 && ask "برنامج Calibre (أغلفة الكتب وإعادة تسميتها وتحويلها للكيندل) غير مثبّت. أثبّته عبر Homebrew؟ (تنزيل كبير نسبيًّا)"; then
    brew install --cask calibre || say "تعذّر تثبيت Calibre؛ تعمل الأداة بدونه عدا ميزات الكتب."
  else
    say "بدون Calibre لا تظهر أغلفة الكتب ولا تعمل إعادة تسميتها. لتثبيته لاحقًا: brew install --cask calibre"
  fi
fi

mkdir -p "$DEST" "$HOME/نسخ احتياطي"
for f in "$SRC"/*.py "$SRC"/*.js "$SRC"/*.html "$SRC"/VERSION "$SRC"/launch_backup.sh "$SRC"/icon.icns "$SRC"/icon.png; do cp "$f" "$DEST/"; done
rm -rf "$DEST/icons"; cp -R "$SRC/icons" "$DEST/icons"
chmod +x "$DEST/launch_backup.sh"
say "نُسخت الملفات."

if [ "$MAKEAPP" = 1 ]; then
  APP="$HOME/Applications/زاجل.app"; rm -rf "$HOME/Applications/Phone Backup.app"
  mkdir -p "$HOME/Applications"; rm -rf "$APP"
  # البرنامج الأصلي (نافذة macOS): يُبنى هنا إن كانت أدوات المطوّر من آبل موجودة (xcode-select --install)
  if [ -x /usr/bin/swiftc ] && /usr/bin/swiftc --version >/dev/null 2>&1 && sh "$SRC/desktop/build_app.sh" "$HOME/Applications" >/dev/null 2>&1; then
    NATIVE=1
  else
    NATIVE=0
    say "أدوات بناء البرنامج الأصلي غير موجودة؛ أنشئ تطبيقًا يفتح الأداة في Chrome. (لتثبيتها: xcode-select --install)"
  fi
  TMP="$(mktemp -t pbapp).applescript"
  [ "$NATIVE" = 1 ] || cat > "$TMP" <<EOT
on run
    try
        do shell script "/bin/sh '$DEST/launch_backup.sh'"
    on error problem
        display alert "تعذر فتح زاجل" message problem as critical
    end try
end run
EOT
  if [ "$NATIVE" = 1 ] || osacompile -o "$APP" "$TMP" 2>/dev/null; then
    if [ "$NATIVE" = 0 ]; then
      cp "$DEST/icon.icns" "$APP/Contents/Resources/applet.icns"
      /usr/libexec/PlistBuddy -c "Delete :CFBundleIconName" "$APP/Contents/Info.plist" >/dev/null 2>&1
      rm -f "$APP/Contents/Resources/Assets.car"
      codesign --force --deep -s - "$APP" >/dev/null 2>&1
    fi
    touch "$APP"
    say "أُنشئ التطبيق:"
    say "$APP"
    if [ "$DOCK" = ask ] && ask "أضع أيقونته في الشريط السفلي (Dock)؟"; then DOCK=yes; fi
    if [ "$DOCK" = yes ]; then
      defaults write com.apple.dock persistent-apps -array-add "<dict><key>tile-data</key><dict><key>file-data</key><dict><key>_CFURLString</key><string>$APP</string><key>_CFURLStringType</key><integer>0</integer></dict></dict></dict>"
      killall Dock
    fi
  else
    say "تعذّر إنشاء التطبيق؛ شغّل: sh '$DEST/launch_backup.sh'"
  fi
  rm -f "$TMP"
fi

say ""
say "تم التثبيت."
say "للتشغيل: افتح «زاجل» من مجلد التطبيقات في مجلدك الشخصي، أو شغّل:"
say "sh '$DEST/launch_backup.sh'"
say "ملاحظة: يتصل الهاتف بجهاز واحد في كل مرة عبر USB. بقية المصادر تعمل من الجهازين."
