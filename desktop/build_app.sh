#!/bin/sh
# يبني «زاجل.app» الأصلي: يجمّع main.swift، وينسخ شيفرة الخادم إلى داخل البرنامج، ويوقّعه محليًا.
# الاستعمال: sh desktop/build_app.sh [مجلد_الإخراج]   (الافتراضي: build/)
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/build}"
APP="$OUT/زاجل.app"
rm -rf "$OUT/Phone Backup.app"
# أغلق النسخة العاملة وانتظر خروجها فعلًا قبل حذفها؛ وإلا بقيت حيّة بلا ملفات فلا يبدأ خادمها، و«open» يوقظها هي لا الجديدة
if pgrep -f "/MacOS/PhoneBackup" >/dev/null 2>&1; then
  osascript -e 'tell application id "com.mohamad.phonebackup" to quit' >/dev/null 2>&1 || true
  i=0; while pgrep -f "/MacOS/PhoneBackup" >/dev/null 2>&1 && [ $i -lt 40 ]; do sleep 0.25; i=$((i+1)); done
  pkill -f "/MacOS/PhoneBackup" 2>/dev/null || true
  pkill -f "Resources/server/samsung_backup_web.py" 2>/dev/null || true
  sleep 1
fi
VER="2.1"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources/server"
/usr/bin/swiftc -O -target arm64-apple-macos13.0 -o "$APP/Contents/MacOS/PhoneBackup" "$ROOT/desktop/main.swift" -framework Cocoa -framework WebKit
/usr/bin/swiftc -O -target arm64-apple-macos13.0 -o "$APP/Contents/MacOS/pbvision" "$ROOT/desktop/vision.swift" -framework Vision -framework ImageIO || echo "تعذّر بناء أداة تصنيف الصور؛ يعمل البرنامج بدونها."
for f in "$ROOT"/*.py "$ROOT"/app.js "$ROOT"/ui.js "$ROOT"/assistant.js "$ROOT"/assistant_nav.js "$ROOT"/terminal_ui.js "$ROOT"/sections.js "$ROOT"/sw.js "$ROOT"/samsung_backup.html "$ROOT"/VERSION; do cp "$f" "$APP/Contents/Resources/server/"; done
cp -R "$ROOT/icons" "$APP/Contents/Resources/server/icons"
rm -f "$APP/Contents/Resources/server/app.py"
cp "$ROOT/icon.icns" "$APP/Contents/Resources/icon.icns"
cat > "$APP/Contents/Info.plist" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleIdentifier</key><string>com.mohamad.phonebackup</string>
  <key>CFBundleName</key><string>زاجل</string>
  <key>CFBundleDisplayName</key><string>زاجل</string>
  <key>CFBundleExecutable</key><string>PhoneBackup</string>
  <key>CFBundleIconFile</key><string>icon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>$VER</string>
  <key>CFBundleVersion</key><string>$VER</string>
  <key>CFBundleDevelopmentRegion</key><string>ar</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>LSApplicationCategoryType</key><string>public.app-category.utilities</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSSupportsAutomaticTermination</key><false/>
  <key>NSLocalNetworkUsageDescription</key><string>للاتصال بالهاتف والساعة لاسلكيًا على شبكة البيت.</string>
  <key>NSAppTransportSecurity</key><dict><key>NSAllowsLocalNetworking</key><true/></dict>
  <key>NSDesktopFolderUsageDescription</key><string>لتصفّح ملفات سطح المكتب ونسخها.</string>
  <key>NSDocumentsFolderUsageDescription</key><string>لتصفّح ملفات المستندات ونسخها.</string>
  <key>NSDownloadsFolderUsageDescription</key><string>لتصفّح ملفات التنزيلات ونسخها.</string>
  <key>NSRemovableVolumesUsageDescription</key><string>لقراءة الأقراص الخارجية والفلاشات ونسخ ملفاتها.</string>
  <key>NSNetworkVolumesUsageDescription</key><string>لقراءة أقراص الشبكة الموصولة.</string>
  <key>NSAppleEventsUsageDescription</key><string>لفتح الطرفية عند ربط حساب iCloud، ولإظهار الملفات في Finder.</string>
  <key>NSHumanReadableCopyright</key><string>زاجل — للاستعمال الشخصي</string>
</dict></plist>
PL
# توقيع بهوية ثابتة إن وُجدت: التوقيع المؤقت «-» يتغيّر مع كل بناء فينسى الماك إذن «الشبكة المحلية»
# (فيفشل اتصال الهاتف لاسلكيًا بـ No route to host)
ID=$(security find-identity -v -p codesigning 2>/dev/null | sed -n 's/.*\([0-9A-F]\{40\}\) "\(.*\)"/\1/p' | head -1)
/usr/bin/codesign --force --deep --sign "${ID:--}" "$APP" >/dev/null 2>&1 || /usr/bin/codesign --force --deep --sign - "$APP" >/dev/null 2>&1 || true
echo "$APP"
