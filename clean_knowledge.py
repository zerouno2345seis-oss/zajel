"""Known user data locations shown by the Mac storage check."""
from __future__ import annotations

import fnmatch
from pathlib import Path


LOCATIONS = [
    {"pattern": "Library/CloudStorage/OneDrive-*", "id": "cloud-onedrive", "title": "ملفات OneDrive المحفوظة على الجهاز", "desc": "هذه ملفات سحابية نُسخت إلى هذا الجهاز؛ حذفها هنا قد يؤثر في النسخة المتزامنة. حرّر المساحة من Finder ليبقى الملف سحابيًا.", "risk": "info", "selectable": False, "action": {"kind": "free_cloud", "label": "تحرير المساحة من Finder", "steps": ["في Finder، انقر بزر الفأرة الأيمن على المجلد.", "اختر «تحرير مساحة / Liberar espacio / Free Up Space».", "قد تمنع طبقات شفافة مثل Wispr Flow النقر؛ أغلقها أو نفّذ الخطوة يدويًا."]}},
    {"pattern": "Library/CloudStorage/GoogleDrive-*", "id": "cloud-google-drive", "title": "ملفات Google Drive المحفوظة على الجهاز", "desc": "قد تكون هذه الملفات متزامنة مع السحابة؛ راجع إعداد المزامنة قبل حذفها.", "risk": "info", "selectable": False, "action": {"kind": "free_cloud", "label": "تحرير المساحة من Finder", "steps": ["في Finder، انقر بزر الفأرة الأيمن على المجلد.", "اختر «تحرير مساحة / Liberar espacio / Free Up Space».", "قد تمنع طبقات شفافة مثل Wispr Flow النقر؛ أغلقها أو نفّذ الخطوة يدويًا."]}},
    {"pattern": "Library/CloudStorage/Dropbox*", "id": "cloud-dropbox", "title": "ملفات Dropbox المحفوظة على الجهاز", "desc": "قد تكون هذه الملفات متزامنة مع السحابة؛ راجع إعداد المزامنة قبل حذفها.", "risk": "info", "selectable": False, "action": {"kind": "free_cloud", "label": "تحرير المساحة من Finder", "steps": ["في Finder، انقر بزر الفأرة الأيمن على المجلد.", "اختر «تحرير مساحة / Liberar espacio / Free Up Space».", "قد تمنع طبقات شفافة مثل Wispr Flow النقر؛ أغلقها أو نفّذ الخطوة يدويًا."]}},
    {"pattern": "*iCloud Drive*", "id": "icloud-archives", "title": "نسخ قديمة من iCloud Drive", "desc": "قد تحتوي النسخة القديمة على ملفات جديدة غير موجودة في أماكن أخرى. تُراجع الملفات الفريدة قبل نقلها.", "risk": "review", "selectable": True, "action": {"kind": "move_unique", "label": "نقل الملفات الفريدة أولًا"}},
    {"pattern": ".lmstudio", "id": "local-ai-lmstudio", "title": "ملفات LM Studio المحلية", "desc": "نماذج الذكاء الاصطناعي تعمل دون اتصال وقد تشغل مساحة كبيرة؛ احتفظ بها إن كنت تستخدمها.", "risk": "review", "selectable": True},
    {"pattern": ".ollama", "id": "local-ai-ollama", "title": "نماذج Ollama المحلية", "desc": "نماذج الذكاء الاصطناعي تعمل دون اتصال وقد تشغل مساحة كبيرة؛ احتفظ بها إن كنت تستخدمها.", "risk": "review", "selectable": True},
    {"pattern": ".cache/huggingface", "id": "local-ai-huggingface", "title": "نماذج Hugging Face المحلية", "desc": "ملفات نماذج ذكاء اصطناعي محلية؛ قد تحتاج تنزيلها مجددًا بعد إزالتها.", "risk": "review", "selectable": True},
    {"pattern": ".cache/lm-studio", "id": "local-ai-lm-studio-cache", "title": "ملفات LM Studio المؤقتة", "desc": "ملفات تطبيق ذكاء اصطناعي محلي؛ راجعها قبل الإزالة.", "risk": "review", "selectable": True},
    {"pattern": ".cache/gpt4all", "id": "local-ai-gpt4all", "title": "ملفات GPT4All المحلية", "desc": "نماذج ذكاء اصطناعي محلية؛ احتفظ بها إن كنت تستخدمها.", "risk": "review", "selectable": True},
    {"pattern": ".mlx", "id": "local-ai-mlx", "title": "ملفات MLX المحلية", "desc": "نماذج ذكاء اصطناعي محلية؛ احتفظ بها إن كنت تستخدمها.", "risk": "review", "selectable": True},
    {"pattern": "Library/Application Support/LM Studio", "id": "local-ai-lmstudio-app", "title": "بيانات تطبيق LM Studio", "desc": "بيانات تطبيق ونماذج محلية؛ راجعها قبل الإزالة.", "risk": "review", "selectable": True},
    {"pattern": "Library/Application Support/jan", "id": "local-ai-jan", "title": "بيانات تطبيق Jan", "desc": "بيانات تطبيق ذكاء اصطناعي محلي؛ راجعها قبل الإزالة.", "risk": "review", "selectable": True},
    {"pattern": ".gemini/antigravity-ide/browser_recordings", "id": "agent-recordings", "title": "تسجيلات تصفح المساعد", "desc": "تسجيلات شاشة أنشأها المساعد أثناء التصفح؛ يمكنك نقلها إلى السلة إذا لم تعد تحتاجها.", "risk": "safe", "selectable": True},
    {"pattern": ".local/share/opencode/opencode.db", "id": "opencode-history", "title": "سجل محادثات OpenCode", "desc": "قاعدة بيانات محادثات قديمة للمساعد؛ راجعها لأن حذفها يزيل سجل المحادثات.", "risk": "review", "selectable": True},
    {"pattern": ".git_archive_*", "id": "git-archives", "title": "أرشيفات مشاريع Git", "desc": "نسخ أرشيفية من مشاريع؛ تأكد من استقرار المشروع وأن النسخة غير مطلوبة.", "risk": "review", "selectable": True},
]

KEEP_PATTERNS = ["Library/Application Support/Claude*/vm_bundles", "Library/Keychains", "Library/Application Support/Bitwarden*", "Library/Application Support/1Password*"]
APP_NOTES = {
    "Claude": "قد تحتوي بيانات Claude على بيئة تشغيل افتراضية؛ أبقِ مجلد vm_bundles.",
    "Google": "بيانات تطبيقات Google؛ راجع التطبيقات قبل الإزالة.",
    "Wispr Flow": "بيانات Wispr Flow؛ قد تشمل طبقات واجهة شفافة.",
    "Antigravity IDE": "بيانات بيئة تطوير ومساعد؛ راجعها قبل الإزالة.",
    "ai.perplexity.": "بيانات Perplexity؛ راجعها قبل الإزالة.",
    "Manus": "بيانات Manus؛ راجعها قبل الإزالة.",
    "autoclaw": "بيانات أداة مساعد؛ راجعها قبل الإزالة.",
}


def matches_keep(path: str | Path, home: str | Path) -> bool:
    try:
        rel = Path(path).resolve().relative_to(Path(home).resolve()).as_posix()
    except (ValueError, OSError):
        rel = Path(path).as_posix()
    return any(fnmatch.fnmatchcase(rel, pattern) for pattern in KEEP_PATTERNS)
