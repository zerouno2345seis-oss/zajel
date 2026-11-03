#!/bin/sh
set -eu
APP_ROOT="$(cd "$(dirname "$0")" && pwd)"
URL='http://127.0.0.1:8765'
healthy() {
  /usr/bin/curl -fsS --max-time 2 "$URL/api/health" 2>/dev/null | /usr/bin/python3 -c 'import json,sys; sys.exit(0 if json.load(sys.stdin).get("app")=="samsung-backup" else 1)' 2>/dev/null
}
if ! healthy; then
  /usr/bin/nohup /usr/bin/python3 "$APP_ROOT/samsung_backup_web.py" --no-browser >> "$APP_ROOT/.backup-server.log" 2>&1 < /dev/null &
  attempt=0
  until healthy; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 15 ]; then
      echo 'Unable to start Phone Backup. See .backup-server.log.' >&2
      exit 1
    fi
    sleep 1
  done
fi
# إن كانت نافذة الأداة مفتوحة فعلًا فأحضرها للأمام بدل فتح نافذة جديدة
if [ -d "/Applications/Google Chrome.app" ]; then
  FOUND=$(/usr/bin/osascript <<'AS' 2>/dev/null || true
if application "Google Chrome" is running then
  tell application "Google Chrome"
    repeat with w in windows
      repeat with i from 1 to (count of tabs of w)
        if (URL of tab i of w) starts with "http://127.0.0.1:8765" and (URL of tab i of w) does not contain "/pair" then
          set active tab index of w to i
          set index of w to 1
          activate
          return "found"
        end if
      end repeat
    end repeat
  end tell
end if
return "none"
AS
)
  if [ "$FOUND" = "found" ]; then exit 0; fi
  # استدعاء Chrome مباشرة يمرّر --app حتى إن كان Chrome يعمل (open -a يتجاهله)
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --app="$URL/" >/dev/null 2>&1 &
else
  /usr/bin/open "$URL/"
fi
