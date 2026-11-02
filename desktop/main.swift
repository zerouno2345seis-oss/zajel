// Phone Backup — غلاف أصلي لـ macOS: نافذة WKWebView حول الخادم المحلي.
// البرنامج يشغّل الخادم (Python) كعملية تابعة له، فيرث صلاحياته هو (الوصول الكامل إلى القرص)،
// ويوقفه عند الخروج. نسخة واحدة فقط، ونقرة الـDock تُعيد النافذة نفسها.
import Cocoa
import WebKit

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

final class AppDelegate: NSObject, NSApplicationDelegate, WKUIDelegate, WKNavigationDelegate {
    var window: NSWindow!
    var web: WKWebView!
    var server: Process?
    var logHandle: FileHandle?

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
                if ok { self.web.load(URLRequest(url: BASE)) }
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
                if self.healthy() { misses = 0; continue }
                misses += 1
                if misses < 2 { continue }
                if self.server == nil || self.server?.isRunning == false { self.startServer() }
                for _ in 0..<40 { if self.healthy() { break }; Thread.sleep(forTimeInterval: 0.25) }
                if self.healthy() { DispatchQueue.main.async { self.web.load(URLRequest(url: BASE)) } }
                misses = 0
            }
        }
    }

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
        web = WKWebView(frame: .zero, configuration: cfg)
        web.uiDelegate = self; web.navigationDelegate = self
        web.allowsMagnification = true
        web.setValue(false, forKey: "drawsBackground")

        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1320, height: 840),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = "زاجل"
        window.minSize = NSSize(width: 760, height: 520)
        window.contentView = web
        window.backgroundColor = .windowBackgroundColor
        window.setFrameAutosaveName("PhoneBackupMain")
        if !window.setFrameUsingName("PhoneBackupMain") { window.center() }
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
        web.loadHTMLString(html, baseURL: nil)
    }

    // MARK: الروابط الخارجية تُفتح في المتصفح الافتراضي
    func webView(_ w: WKWebView, decidePolicyFor a: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        if let u = a.request.url, let host = u.host, host != "127.0.0.1", host != "localhost", u.scheme?.hasPrefix("http") == true {
            NSWorkspace.shared.open(u); decisionHandler(.cancel); return
        }
        decisionHandler(.allow)
    }
    func webView(_ w: WKWebView, createWebViewWith c: WKWebViewConfiguration, for a: WKNavigationAction, windowFeatures f: WKWindowFeatures) -> WKWebView? {
        if let u = a.request.url { NSWorkspace.shared.open(u) }
        return nil
    }
    func webViewWebContentProcessDidTerminate(_ w: WKWebView) { w.reload() }

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
        appM.addItem(item("حول زاجل", #selector(NSApplication.orderFrontStandardAboutPanel(_:)), ""))
        appM.addItem(.separator())
        appM.addItem(item("فتح مجلد بيانات البرنامج", #selector(openData(_:)), "", target: self))
        appM.addItem(.separator())
        appM.addItem(item("إخفاء زاجل", #selector(NSApplication.hide(_:)), "h"))
        appM.addItem(item("إخفاء الآخرين", #selector(NSApplication.hideOtherApplications(_:)), "h", [.command, .option]))
        appM.addItem(.separator())
        appM.addItem(item("إنهاء زاجل", #selector(NSApplication.terminate(_:)), "q"))
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
        win.addItem(item("زاجل", #selector(showMain(_:)), "1", target: self))
        let w = NSMenuItem(); w.submenu = win; main.addItem(w)
        NSApp.windowsMenu = win
        NSApp.mainMenu = main
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
