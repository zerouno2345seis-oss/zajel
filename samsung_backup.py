#!/usr/bin/env python3
"""Small macOS GUI for backing up Samsung files over Android Debug Bridge."""

from __future__ import annotations

import datetime as dt
import queue
import shutil
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


ADB = shutil.which("adb") or "/opt/homebrew/bin/adb"
SOURCES = {
    "الصور": ["/sdcard/DCIM", "/sdcard/Pictures"],
    "الفيديوهات": ["/sdcard/Movies", "/sdcard/DCIM/Camera"],
    "الصوتيات": ["/sdcard/Music", "/sdcard/Podcasts"],
    "التسجيلات الصوتية": ["/sdcard/Recordings", "/sdcard/Call", "/sdcard/Sounds/Recordings"],
    "المستندات والتنزيلات": ["/sdcard/Documents", "/sdcard/Download"],
}


class BackupApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("نسخ الهاتف الاحتياطي")
        self.root.geometry("720x650")
        self.root.minsize(620, 560)
        self.events: queue.Queue = queue.Queue()
        self.serial: str | None = None
        self.running = True
        self.destination = tk.StringVar(value=str(Path.home() / "Backups" / "Samsung"))
        self.status = tk.StringVar(value="جارٍ البحث عن هاتف موصول…")
        self.device_label = tk.StringVar(value="لم يُكتشف هاتف بعد")
        self.category_vars = {name: tk.BooleanVar(value=True) for name in SOURCES}
        self._build()
        self.root.after(250, self._drain_events)
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self._start_worker(self._detect_loop)

    def _build(self):
        style = ttk.Style()
        style.configure("Title.TLabel", font=("Helvetica Neue", 20, "bold"))
        style.configure("Sub.TLabel", font=("Helvetica Neue", 11))
        outer = ttk.Frame(self.root, padding=24)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="نسخ الهاتف الاحتياطي", style="Title.TLabel").pack(anchor="e")
        ttk.Label(outer, text="انسخ الصور والصوتيات والملفات المتاحة من هاتف Samsung إلى مجلد على هذا الجهاز.", style="Sub.TLabel", wraplength=660, justify="right").pack(anchor="e", pady=(6, 18))

        device = ttk.LabelFrame(outer, text="الهاتف", padding=14)
        device.pack(fill="x", pady=5)
        ttk.Label(device, textvariable=self.device_label, font=("Helvetica Neue", 12)).pack(anchor="e")
        ttk.Label(device, text="فعّل خيارات المطوّر وتصحيح USB، ثم وافق على رسالة الثقة التي تظهر على الهاتف.", wraplength=650, justify="right").pack(anchor="e", pady=(6, 0))

        cats = ttk.LabelFrame(outer, text="ما الذي تريد نسخه؟", padding=14)
        cats.pack(fill="x", pady=10)
        for i, name in enumerate(SOURCES):
            cb = ttk.Checkbutton(cats, text=name, variable=self.category_vars[name])
            cb.grid(row=i // 3, column=2 - (i % 3), sticky="e", padx=16, pady=7)

        dest = ttk.LabelFrame(outer, text="مكان النسخة", padding=14)
        dest.pack(fill="x", pady=3)
        ttk.Entry(dest, textvariable=self.destination, justify="left").pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Button(dest, text="اختيار مجلد…", command=self._choose_folder).pack(side="right")

        self.progress = ttk.Progressbar(outer, mode="indeterminate")
        self.progress.pack(fill="x", pady=(16, 5))
        ttk.Label(outer, textvariable=self.status, justify="right", wraplength=660).pack(anchor="e")
        self.log = tk.Text(outer, height=8, wrap="word", state="disabled", font=("Menlo", 10))
        self.log.pack(fill="both", expand=True, pady=10)
        self.backup_btn = ttk.Button(outer, text="ابدأ النسخ الاحتياطي", command=self._backup)
        self.backup_btn.pack(anchor="e", ipadx=12, ipady=6)
        self._append("ملاحظة: هذه الأداة تنسخ الملفات المشتركة. لا تنسخ بيانات التطبيقات الخاصة أو كلمات المرور.")

    def _choose_folder(self):
        path = filedialog.askdirectory(title="اختر مجلد حفظ النسخة")
        if path:
            self.destination.set(path)

    def _start_worker(self, fn, *args):
        threading.Thread(target=fn, args=args, daemon=True).start()

    def _adb(self, *args, serial=True, timeout=30):
        cmd = [ADB]
        if serial and self.serial:
            cmd += ["-s", self.serial]
        cmd += list(args)
        return subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)

    def _detect_loop(self):
        try:
            subprocess.run([ADB, "start-server"], capture_output=True, timeout=15)
        except Exception as e:
            self.events.put(("status", f"تعذر تشغيل ADB: {e}"))
        while self.running:
            try:
                result = self._adb("devices", "-l", serial=False, timeout=5)
                rows = result.stdout.splitlines()[1:]
                connected = [line.split() for line in rows if line.strip() and len(line.split()) > 1 and line.split()[1] == "device"]
                new = connected[0][0] if connected else None
                if new != self.serial:
                    self.serial = new
                    if new:
                        model = self._adb("shell", "getprop", "ro.product.model", timeout=5).stdout.strip()
                        self.events.put(("device", f"{model or 'هاتف Android'} متصل — {new}"))
                    else:
                        self.events.put(("device", "لم يُكتشف هاتف بعد"))
                if not new:
                    unauthorized = any("unauthorized" in line for line in rows)
                    self.events.put(("status", "وافق على تصحيح USB في الهاتف." if unauthorized else "وصّل الهاتف عبر USB وفعّل تصحيح USB."))
            except Exception as e:
                self.events.put(("status", f"تعذر فحص الاتصال: {e}"))
            import time; time.sleep(3)

    def _close(self):
        self.running = False
        self.root.destroy()

    def _backup(self):
        selected = [name for name, var in self.category_vars.items() if var.get()]
        if not self.serial:
            messagebox.showinfo("الهاتف غير متصل", "وصّل الهاتف ووافق على تصحيح USB أولًا.")
            return
        if not selected:
            messagebox.showinfo("اختر محتوى", "حدد نوعًا واحدًا على الأقل للنسخ.")
            return
        target = Path(self.destination.get()).expanduser()
        stamp = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        folder = target / f"Samsung_{stamp}"
        self.backup_btn.configure(state="disabled")
        self.progress.start(12)
        self.status.set("جارٍ نسخ الملفات… أبقِ الهاتف موصولًا ومفتوحًا.")
        self._append(f"بدء النسخ إلى: {folder}")
        self._start_worker(self._copy_selected, selected, folder)

    def _copy_selected(self, selected, folder):
        serial = self.serial
        copied = 0
        errors = []
        try:
            folder.mkdir(parents=True, exist_ok=True)
            for category in selected:
                out = folder / category
                out.mkdir(exist_ok=True)
                found = False
                for source in SOURCES[category]:
                    check = subprocess.run([ADB, "-s", serial, "shell", "test", "-d", source], capture_output=True, timeout=10)
                    if check.returncode:
                        continue
                    found = True
                    result = subprocess.run([ADB, "-s", serial, "pull", source, str(out)], text=True, capture_output=True, timeout=3600)
                    if result.returncode:
                        errors.append(f"{category} ({source}): {result.stderr.strip() or 'تعذر النسخ'}")
                    else:
                        copied += 1
                if not found:
                    errors.append(f"{category}: لم يوجد مجلد معروف؛ افحص مجلد التسجيلات في الهاتف يدويًا.")
            self.events.put(("done", (folder, copied, errors)))
        except Exception as e:
            self.events.put(("done", (folder, copied, [str(e)])))

    def _drain_events(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "status":
                    self.status.set(value)
                elif kind == "device":
                    self.device_label.set(value)
                    if self.serial:
                        self.status.set("الهاتف جاهز للنسخ.")
                elif kind == "done":
                    folder, copied, errors = value
                    self.progress.stop()
                    self.backup_btn.configure(state="normal")
                    self._append(f"اكتملت العملية. مجلدات نُقلت: {copied}")
                    for err in errors:
                        self._append(f"تنبيه: {err}")
                    self.status.set(f"انتهى النسخ إلى {folder}")
        except queue.Empty:
            pass
        if self.running:
            self.root.after(250, self._drain_events)

    def _append(self, message):
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")


if __name__ == "__main__":
    app_root = tk.Tk()
    BackupApp(app_root)
    app_root.mainloop()
