// Phone Backup — غلاف أصلي لـ macOS: نافذة WKWebView حول الخادم المحلي.
// البرنامج يشغّل الخادم (Python) كعملية تابعة له، فيرث صلاحياته هو (الوصول الكامل إلى القرص)،
// ويوقفه عند الخروج. نسخة واحدة فقط، ونقرة الـDock تُعيد النافذة نفسها.
import Cocoa
import WebKit
import Carbon.HIToolbox

// برنامجان من ملف واحد: «زاجل» الكامل، و«طرفية زاجل» (ZajelMode=terminal في Info.plist) يفتح على الطرفيات مباشرة.
// كلاهما يستعمل الخادم نفسه على 127.0.0.1 إن كان يعمل، فالجلسات والإعدادات واحدة.
let MODE = (Bundle.main.object(forInfoDictionaryKey: "ZajelMode") as? String) ?? "main"
let TERM = MODE == "terminal"
let APPNAME = TERM ? "طرفية زاجل" : "زاجل"

// «الباب» الداخلي بين النافذة والخادم: 8765 إن كان فارغًا أو يعمل عليه زاجل نفسه، وإلا أول باب فارغ بعده
// (على جهاز آخر قد يشغل 8765 برنامج آخر فلا يقوم الخادم).
var PORT = 8765
var BASE = URL(string: "http://127.0.0.1:8765/")!

func portFree(_ port: Int) -> Bool {
    let fd = socket(AF_INET, SOCK_STREAM, 0); if fd < 0 { return false }
    defer { close(fd) }
    var one: Int32 = 1; setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &one, socklen_t(MemoryLayout<Int32>.size))  // باب يُغلق للتو ليس مشغولًا
    var addr = sockaddr_in(); addr.sin_family = sa_family_t(AF_INET); addr.sin_port = in_port_t(UInt16(port).bigEndian)
    addr.sin_addr.s_addr = inet_addr("127.0.0.1")
    return withUnsafePointer(to: &addr) { $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { bind(fd, $0, socklen_t(MemoryLayout<sockaddr_in>.size)) } } == 0
}

/// صفحة زاجل لا تعرف مسار الملف المسحوب إليها (المتصفح يعطيها الاسم فقط)، فيلتقط البرنامج الإفلات
/// ويسلّم المسارات الكاملة إلى الطرفية التي أُفلتت فوقها (ZajelTermApp.dropPaths). غير ذلك يمضي كما هو.
final class DropWebView: WKWebView {
    override func performDragOperation(_ sender: NSDraggingInfo) -> Bool {
        let urls = (sender.draggingPasteboard.readObjects(forClasses: [NSURL.self], options: [.urlReadingFileURLsOnly: true]) as? [URL]) ?? []
        if !urls.isEmpty {
            let p = convert(sender.draggingLocation, from: nil)
            let y = isFlipped ? p.y : bounds.height - p.y
            let mag = max(0.1, magnification)
            let items = urls.map { u -> [String: Any] in
                var dir: ObjCBool = false
                FileManager.default.fileExists(atPath: u.path, isDirectory: &dir)
                return ["path": u.path, "dir": dir.boolValue]
            }
            if let data = try? JSONSerialization.data(withJSONObject: items), let json = String(data: data, encoding: .utf8) {
                let js = "window.ZajelTermApp && window.ZajelTermApp.dropPaths ? window.ZajelTermApp.dropPaths(\(json), \(p.x / mag), \(y / mag)) : false"
                var handled = false
                let sem = DispatchSemaphore(value: 0)
                evaluateJavaScript(js) { r, _ in handled = (r as? Bool) ?? false; sem.signal() }
                // الانتظار بلا حجب حلقة الأحداث: تُدار حتى يجيب الـJavaScript (أقصى ثانية)
                let until = Date().addingTimeInterval(1)
                while sem.wait(timeout: .now()) == .timedOut && Date() < until { RunLoop.current.run(mode: .default, before: Date().addingTimeInterval(0.01)) }
                if handled { return true }
            }
        }
        return super.performDragOperation(sender)
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate, WKUIDelegate, WKNavigationDelegate {
    var window: NSWindow!
    var web: WKWebView!
    var server: Process?
    var logHandle: FileHandle?
    var onSplash = true     // الصفحة الحالية رسالة انتظار أو خطأ، لا الواجهة

    // MARK: دورة الحياة
    func applicationDidFinishLaunching(_ n: Notification) {
        buildMenu()
        buildWindow()
        showSplash("جارٍ التشغيل…")
        DispatchQueue.global().async {
            self.choosePort()
            if !self.healthy() { self.startServer() }
            var ok = false
            for _ in 0..<60 { if self.healthy() { ok = true; break }; Thread.sleep(forTimeInterval: 0.25) }
            self.startWatchdog()
            DispatchQueue.main.async {
                if ok { self.web.load(URLRequest(url: self.homeURL())) }
                if TERM { self.startTerminalExtras() }
                else { self.showSplash("تعذّر تشغيل الخادم. راجع السجل:\n~/Library/Application Support/Phone Backup/server.log") }
            }
        }
    }

    func applicationShouldHandleReopen(_ s: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        window.makeKeyAndOrderFront(nil); return true
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ s: NSApplication) -> Bool { false }
    func applicationWillTerminate(_ n: Notification) {
        if let p = server, p.isRunning { p.terminate(); p.waitUntilExit() }
    }

    // MARK: الخادم
    /// حارس: كل 4 ثوانٍ، إن لم يستجب الخادم ولم تكن نسختنا تعمل، نشغّله من جديد ونعيد تحميل الصفحة.
    func startWatchdog() {
        DispatchQueue.global().async {
            var misses = 0
            while true {
                Thread.sleep(forTimeInterval: 4)
                // الخادم صار يجيب والنافذة ما زالت على رسالة الخطأ (البرنامج الآخر شغّله بعد مهلتنا): افتح الواجهة
                if self.healthy() { misses = 0; if self.onSplash { DispatchQueue.main.async { self.web.load(URLRequest(url: self.homeURL())) } }; continue }
                misses += 1
                if misses < 2 { continue }
                if self.server == nil || self.server?.isRunning == false { self.startServer() }
                for _ in 0..<40 { if self.healthy() { break }; Thread.sleep(forTimeInterval: 0.25) }
                if self.healthy() { DispatchQueue.main.async { self.web.load(URLRequest(url: self.homeURL())) } }
                misses = 0
            }
        }
    }

    func homeURL() -> URL { TERM ? URL(string: BASE.absoluteString + "?mode=terminal")! : BASE }

    func dataDir() -> URL {
        let d = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/Phone Backup")
        try? FileManager.default.createDirectory(at: d, withIntermediateDirectories: true)
        return d
    }

    func choosePort() {
        // الباب المعتاد أولًا مع مهلة قصيرة (نسخة سابقة قد تكون تُغلق الآن)، ثم أول باب فارغ بعده
        func use(_ p: Int) -> Bool { PORT = p; BASE = URL(string: "http://127.0.0.1:\(p)/")!; return healthy() || portFree(p) }
        for _ in 0..<12 { if use(8765) { return }; if !isOurs(8765) && !portFree(8765) && someoneElse(8765) { break }; Thread.sleep(forTimeInterval: 0.25) }
        for p in 8766...8799 where use(p) { return }
        PORT = 8765; BASE = URL(string: "http://127.0.0.1:8765/")!
    }
    func isOurs(_ p: Int) -> Bool { let b = BASE; BASE = URL(string: "http://127.0.0.1:\(p)/")!; let ok = healthy(); BASE = b; return ok }
    /// برنامج آخر يجيب على هذا الباب (لا زاجل): لا فائدة من الانتظار
    func someoneElse(_ p: Int) -> Bool {
        var req = URLRequest(url: URL(string: "http://127.0.0.1:\(p)/api/health")!); req.timeoutInterval = 1
        let sem = DispatchSemaphore(value: 0); var answered = false
        URLSession.shared.dataTask(with: req) { _, r, _ in answered = r != nil; sem.signal() }.resume()
        _ = sem.wait(timeout: .now() + 1.5); return answered
    }

    func healthy() -> Bool {
        var req = URLRequest(url: BASE.appendingPathComponent("api/health")); req.timeoutInterval = 1.5
        let sem = DispatchSemaphore(value: 0); var ok = false
        URLSession.shared.dataTask(with: req) { d, _, _ in
            if let d = d, let s = String(data: d, encoding: .utf8), s.contains("samsung-backup") { ok = true }
            sem.signal()
        }.resume()
        _ = sem.wait(timeout: .now() + 2)
        return ok
    }

    func startServer() {
        guard let res = Bundle.main.resourceURL?.appendingPathComponent("server") else { return }
        let data = dataDir()
        migrateOldState(to: data)
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
        p.arguments = [res.appendingPathComponent("samsung_backup_web.py").path, "--no-browser"]
        p.currentDirectoryURL = res
        var env = ProcessInfo.processInfo.environment
        env["PB_DATA"] = data.path
        env["PB_PORT"] = String(PORT)
        env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:" + (env["PATH"] ?? "")
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        p.environment = env
        let logURL = data.appendingPathComponent("server.log")
        if !FileManager.default.fileExists(atPath: logURL.path) { FileManager.default.createFile(atPath: logURL.path, contents: nil) }
        if let h = try? FileHandle(forWritingTo: logURL) { h.seekToEndOfFile(); p.standardOutput = h; p.standardError = h; logHandle = h }
        do { try p.run(); server = p } catch { NSLog("server failed: \(error)") }
    }

    /// أول تشغيل: انقل المفضلة والقواعد وغيرها من مجلد الأداة القديم إن وُجدت.
    func migrateOldState(to data: URL) {
        let old = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("j")
        let marker = data.appendingPathComponent(".migrated")
        if FileManager.default.fileExists(atPath: marker.path) { return }
        for name in [".favorites.json", ".appgroups.json", ".clean_rules.json", ".watch.json", "operations.log", "cleaning.log", "deletions.log", ".appmeta"] {
            let src = old.appendingPathComponent(name), dst = data.appendingPathComponent(name)
            if FileManager.default.fileExists(atPath: src.path) && !FileManager.default.fileExists(atPath: dst.path) {
                try? FileManager.default.copyItem(at: src, to: dst)
            }
        }
        FileManager.default.createFile(atPath: marker.path, contents: nil)
    }

    // MARK: النافذة
    func buildWindow() {
        let cfg = WKWebViewConfiguration()
        cfg.preferences.javaScriptCanOpenWindowsAutomatically = true
        cfg.preferences.setValue(true, forKey: "developerExtrasEnabled")
        cfg.applicationNameForUserAgent = "PhoneBackupDesktop/1.0"
        web = DropWebView(frame: .zero, configuration: cfg)
        web.uiDelegate = self; web.navigationDelegate = self
        web.allowsMagnification = true
        web.setValue(false, forKey: "drawsBackground")

        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1320, height: 840),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = APPNAME
        window.minSize = NSSize(width: 760, height: 520)
        window.contentView = web
        window.backgroundColor = .windowBackgroundColor
        let frameName = TERM ? "ZajelTerminalWin" : "PhoneBackupMain"
        window.setFrameAutosaveName(frameName)
        if !window.setFrameUsingName(frameName) {
            // الطرفية تبدأ أول مرة بمساحة الشاشة كلها
            if TERM, let f = NSScreen.main?.visibleFrame { window.setFrame(f, display: true) } else { window.center() }
        }
        window.isReleasedWhenClosed = false
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    func showSplash(_ msg: String) {
        let html = """
        <html dir="rtl"><body style="margin:0;height:100vh;display:flex;align-items:center;justify-content:center;
        font:15px -apple-system,'SF Arabic',sans-serif;color:#888;background:transparent;white-space:pre-line;text-align:center">
        \(msg)</body></html>
        """
        onSplash = true
        web.loadHTMLString(html, baseURL: nil)
    }

    // MARK: الروابط الخارجية تُفتح في المتصفح الافتراضي
    func webView(_ w: WKWebView, decidePolicyFor a: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        if let u = a.request.url, let host = u.host, host != "127.0.0.1", host != "localhost", u.scheme?.hasPrefix("http") == true {
            NSWorkspace.shared.open(u); decisionHandler(.cancel); return
        }
        // ملف أُفلت خارج الطرفية: لا تغادر الصفحة إليه (كانت النافذة تصير عارض ملفات)
        if a.request.url?.isFileURL == true { decisionHandler(.cancel); return }
        decisionHandler(.allow)
    }
    func webView(_ w: WKWebView, createWebViewWith c: WKWebViewConfiguration, for a: WKNavigationAction, windowFeatures f: WKWindowFeatures) -> WKWebView? {
        if let u = a.request.url { NSWorkspace.shared.open(u) }
        return nil
    }
    func webViewWebContentProcessDidTerminate(_ w: WKWebView) { w.reload() }
    func webView(_ w: WKWebView, didFinish n: WKNavigation!) { if w.url?.host == "127.0.0.1" { onSplash = false } }

    // MARK: نوافذ JavaScript الأصلية (تنبيه، تأكيد، إدخال، اختيار ملف)
    func webView(_ w: WKWebView, runJavaScriptAlertPanelWithMessage m: String, initiatedByFrame f: WKFrameInfo, completionHandler: @escaping () -> Void) {
        let a = NSAlert(); a.messageText = m; a.addButton(withTitle: "حسنًا")
        a.beginSheetModal(for: window) { _ in completionHandler() }
    }
    func webView(_ w: WKWebView, runJavaScriptConfirmPanelWithMessage m: String, initiatedByFrame f: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        let a = NSAlert(); a.messageText = m; a.addButton(withTitle: "موافق"); a.addButton(withTitle: "إلغاء")
        a.beginSheetModal(for: window) { r in completionHandler(r == .alertFirstButtonReturn) }
    }
    func webView(_ w: WKWebView, runJavaScriptTextInputPanelWithPrompt p: String, defaultText d: String?, initiatedByFrame f: WKFrameInfo, completionHandler: @escaping (String?) -> Void) {
        let a = NSAlert(); a.messageText = p; a.addButton(withTitle: "موافق"); a.addButton(withTitle: "إلغاء")
        let tf = NSTextField(frame: NSRect(x: 0, y: 0, width: 280, height: 24)); tf.stringValue = d ?? ""; a.accessoryView = tf
        a.beginSheetModal(for: window) { r in completionHandler(r == .alertFirstButtonReturn ? tf.stringValue : nil) }
    }
    func webView(_ w: WKWebView, runOpenPanelWith p: WKOpenPanelParameters, initiatedByFrame f: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
        let op = NSOpenPanel(); op.allowsMultipleSelection = p.allowsMultipleSelection; op.canChooseDirectories = p.allowsDirectories
        op.beginSheetModal(for: window) { r in completionHandler(r == .OK ? op.urls : nil) }
    }

    // MARK: القوائم (⌘W لا يغلق النافذة: هو «إغلاق التبويب» داخل الأداة)
    @objc func reload(_ s: Any?) { web.reload() }
    @objc func zoomIn(_ s: Any?) { web.magnification = min(2, web.magnification + 0.1) }
    @objc func zoomOut(_ s: Any?) { web.magnification = max(0.6, web.magnification - 0.1) }
    @objc func zoomReset(_ s: Any?) { web.magnification = 1 }
    @objc func openData(_ s: Any?) { NSWorkspace.shared.open(dataDir()) }
    @objc func showMain(_ s: Any?) { window.makeKeyAndOrderFront(nil) }

    func buildMenu() {
        let main = NSMenu()
        func item(_ t: String, _ a: Selector?, _ k: String = "", _ m: NSEvent.ModifierFlags = [.command], target: AnyObject? = nil) -> NSMenuItem {
            let i = NSMenuItem(title: t, action: a, keyEquivalent: k); i.keyEquivalentModifierMask = m; if let t = target { i.target = t }; return i
        }
        let appM = NSMenu()
        appM.addItem(item("حول " + APPNAME, #selector(NSApplication.orderFrontStandardAboutPanel(_:)), ""))
        appM.addItem(.separator())
        appM.addItem(item("فتح مجلد بيانات البرنامج", #selector(openData(_:)), "", target: self))
        appM.addItem(.separator())
        appM.addItem(item("إخفاء " + APPNAME, #selector(NSApplication.hide(_:)), "h"))
        appM.addItem(item("إخفاء الآخرين", #selector(NSApplication.hideOtherApplications(_:)), "h", [.command, .option]))
        appM.addItem(.separator())
        appM.addItem(item("إنهاء " + APPNAME, #selector(NSApplication.terminate(_:)), "q"))
        let a = NSMenuItem(); a.submenu = appM; main.addItem(a)

        let edit = NSMenu(title: "تحرير")
        edit.addItem(item("تراجع", Selector(("undo:")), "z"))
        edit.addItem(item("إعادة", Selector(("redo:")), "z", [.command, .shift]))
        edit.addItem(.separator())
        edit.addItem(item("قص", #selector(NSText.cut(_:)), "x"))
        edit.addItem(item("نسخ", #selector(NSText.copy(_:)), "c"))
        edit.addItem(item("لصق", #selector(NSText.paste(_:)), "v"))
        edit.addItem(item("تحديد الكل", #selector(NSText.selectAll(_:)), "a"))
        let e = NSMenuItem(); e.submenu = edit; main.addItem(e)

        let view = NSMenu(title: "عرض")
        view.addItem(item("إعادة التحميل", #selector(reload(_:)), "r", target: self))
        view.addItem(.separator())
        view.addItem(item("تكبير", #selector(zoomIn(_:)), "+", target: self))
        view.addItem(item("تصغير", #selector(zoomOut(_:)), "-", target: self))
        view.addItem(item("الحجم الفعلي", #selector(zoomReset(_:)), "0", target: self))
        view.addItem(.separator())
        view.addItem(item("ملء الشاشة", #selector(NSWindow.toggleFullScreen(_:)), "f", [.command, .control]))
        let v = NSMenuItem(); v.submenu = view; main.addItem(v)

        let win = NSMenu(title: "نافذة")
        win.addItem(item("تصغير", #selector(NSWindow.performMiniaturize(_:)), "m"))
        win.addItem(item("تكبير النافذة", #selector(NSWindow.performZoom(_:)), ""))
        win.addItem(item("إغلاق النافذة", #selector(NSWindow.performClose(_:)), "w", [.command, .shift]))
        win.addItem(.separator())
        win.addItem(item(APPNAME, #selector(showMain(_:)), "1", target: self))
        let w = NSMenuItem(); w.submenu = win; main.addItem(w)
        NSApp.windowsMenu = win
        NSApp.mainMenu = main
    }

    // MARK: إضافات «طرفية زاجل»: الدائرة على الأيقونة، قائمة الزر الأيمن، مفتاح الاستدعاء
    var agents: [[String: Any]] = []
    var lastWaiting = 0

    func startTerminalExtras() {
        registerHotKey()
        DispatchQueue.global().async {
            while true {
                self.pollAgents()
                Thread.sleep(forTimeInterval: 3)
            }
        }
    }

    func pollAgents() {
        var req = URLRequest(url: BASE.appendingPathComponent("api/term/list")); req.timeoutInterval = 2
        let sem = DispatchSemaphore(value: 0)
        URLSession.shared.dataTask(with: req) { d, _, _ in
            defer { sem.signal() }
            guard let d = d, let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any],
                  let rows = j["agents"] as? [[String: Any]] else { return }
            let waiting = rows.filter { ($0["state"] as? String) == "waiting" }.count
            DispatchQueue.main.async {
                self.agents = rows
                NSApp.dockTile.badgeLabel = waiting > 0 ? String(waiting) : nil
                if waiting > self.lastWaiting && !NSApp.isActive { NSApp.requestUserAttention(.informationalRequest) }
                self.lastWaiting = waiting
            }
        }.resume()
        _ = sem.wait(timeout: .now() + 3)
    }

    /// طلب إلى الخادم بالعنوان نفسه الذي ترسله الواجهة (الخادم يرفض طلبات الكتابة من مصدر غريب)
    func post(_ act: String, _ body: [String: Any]) {
        var req = URLRequest(url: BASE.appendingPathComponent("api/term/" + act)); req.httpMethod = "POST"; req.timeoutInterval = 30
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue("http://127.0.0.1:\(PORT)", forHTTPHeaderField: "Origin")
        req.httpBody = try? JSONSerialization.data(withJSONObject: body)
        URLSession.shared.dataTask(with: req) { _, _, _ in DispatchQueue.global().async { self.pollAgents() } }.resume()
    }

    func js(_ code: String) {
        showMain(nil); NSApp.activate(ignoringOtherApps: true)
        web.evaluateJavaScript("window.ZajelTermApp && " + code, completionHandler: nil)
    }

    func confirm(_ title: String, _ info: String) -> Bool {
        NSApp.activate(ignoringOtherApps: true)
        let a = NSAlert(); a.messageText = title; a.informativeText = info
        a.addButton(withTitle: "أعد التشغيل"); a.addButton(withTitle: "إلغاء")
        return a.runModal() == .alertFirstButtonReturn
    }

    var runnable: [[String: Any]] { agents.filter { !(($0["cmd"] as? String) ?? "").isEmpty && ($0["installed"] as? Bool) != false } }

    func applicationDockMenu(_ s: NSApplication) -> NSMenu? {
        guard TERM else { return nil }
        let m = NSMenu()
        let dots = ["working": "🟢", "waiting": "🟡", "idle": "⚪️", "shell": "⚪️", "stopped": "⚫️"]
        for a in agents {
            guard let id = a["id"] as? String else { continue }
            let name = (a["name"] as? String) ?? id, st = (a["state"] as? String) ?? "", lab = (a["label"] as? String) ?? ""
            let sub = NSMenu()
            for (t, act) in [("افتح هنا", "open"), ("شغّل", "start"), ("أعد التشغيل", "restart"), ("افحص", "check")] {
                if act == "check" && ((a["cmd"] as? String) ?? "").isEmpty { continue }
                let i = NSMenuItem(title: t, action: #selector(dockAction(_:)), keyEquivalent: ""); i.target = self
                i.representedObject = [act, id, name]; sub.addItem(i)
            }
            let row = NSMenuItem(title: "\(dots[st] ?? "⚪️") \(name)" + (lab.isEmpty ? "" : " — \(lab)"), action: nil, keyEquivalent: "")
            row.submenu = sub; m.addItem(row)
        }
        if agents.isEmpty { m.addItem(NSMenuItem(title: "يجري تحميل الوكلاء…", action: nil, keyEquivalent: "")) }
        m.addItem(.separator())
        for (t, act) in [("شغّل كل الوكلاء", "startAll"), ("افحص كل الوكلاء", "checkAll"), ("أعد تشغيل كل الوكلاء", "restartAll")] {
            let i = NSMenuItem(title: t, action: #selector(dockAction(_:)), keyEquivalent: ""); i.target = self; i.representedObject = [act, "", ""]; m.addItem(i)
        }
        m.addItem(.separator())
        for (t, act) in [("أرسل لعدة وكلاء", "broadcast"), ("افتح زاجل الكامل", "main")] {
            let i = NSMenuItem(title: t, action: #selector(dockAction(_:)), keyEquivalent: ""); i.target = self; i.representedObject = [act, "", ""]; m.addItem(i)
        }
        return m
    }

    @objc func dockAction(_ sender: NSMenuItem) {
        guard let o = sender.representedObject as? [String], o.count == 3 else { return }
        let act = o[0], id = o[1], name = o[2]
        let safeId = id.replacingOccurrences(of: "'", with: "")
        switch act {
        case "open": js("ZajelTermApp.open('\(safeId)')")
        case "start": post("start", ["id": id])
        case "restart":
            if confirm("إعادة تشغيل \(name)؟", "سيتوقف ما يكتبه الآن، ويبدأ من جديد.") { post("restart", ["id": id]) }
        case "check": post("health", ["id": id, "check": true, "force": true])
        case "startAll": for a in runnable { if let i = a["id"] as? String, (a["state"] as? String) == "stopped" { post("start", ["id": i]) } }
        case "checkAll": for a in runnable { if let i = a["id"] as? String { post("health", ["id": i, "check": true, "force": true]) } }
        case "restartAll":
            if confirm("إعادة تشغيل كل الوكلاء؟", "سيتوقف كل وكيل يعمل الآن عمّا يكتبه، ويبدأ من جديد.") {
                for a in runnable { if let i = a["id"] as? String { post("restart", ["id": i]) } }
            }
        case "broadcast": js("ZajelTermApp.broadcast()")
        case "main":
            if let u = NSWorkspace.shared.urlForApplication(withBundleIdentifier: "com.mohamad.phonebackup") {
                NSWorkspace.shared.openApplication(at: u, configuration: NSWorkspace.OpenConfiguration(), completionHandler: nil)
            }
        default: break
        }
    }

    /// مفتاح الاستدعاء (الافتراضي ⌥ مسافة). يُغيَّر بـ: defaults write com.mohamad.zajel.terminal HotKey control-option | off
    func registerHotKey() {
        let pref = UserDefaults.standard.string(forKey: "HotKey") ?? "option"
        if pref == "off" { return }
        let mods = pref == "control-option" ? UInt32(controlKey | optionKey) : UInt32(optionKey)
        var spec = EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed))
        InstallEventHandler(GetApplicationEventTarget(), { _, _, _ in
            DispatchQueue.main.async { delegate.toggleVisible() }
            return noErr
        }, 1, &spec, nil, nil)
        var ref: EventHotKeyRef?
        RegisterEventHotKey(UInt32(kVK_Space), mods, EventHotKeyID(signature: OSType(0x5A4A544D), id: 1), GetApplicationEventTarget(), 0, &ref)
    }

    func toggleVisible() {
        if NSApp.isActive && window.isVisible && !window.isMiniaturized { NSApp.hide(nil) }
        else { window.deminiaturize(nil); showMain(nil); NSApp.activate(ignoringOtherApps: true) }
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
