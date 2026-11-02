"""تصنيف الصور بالكلمات (لقطات شاشة، أشخاص، حيوانات، طعام…) عبر أداة pbvision المبنية بإطار Vision في macOS."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

IMG_EXT = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".dng"}

# كلمة عربية ← معرّفات Vision (التصنيف هرمي: «animal» تشمل القطط والكلاب…)
WORDS = {
    "لقطات الشاشة": ["@screenshot", "screenshot"],
    "أشخاص": ["@faces", "people", "adult", "child", "baby", "crowd", "portrait", "selfie"],
    "حيوانات": ["animal", "mammal", "cat", "dog", "bird", "fish", "insect", "horse", "pet"],
    "طعام": ["food", "fruit", "vegetable", "dessert", "baked_goods", "meal", "drink", "beverage"],
    "مستندات": ["document", "printed_page", "receipt", "paper", "text", "handwriting"],
    "طبيعة": ["nature", "landscape", "sky", "mountain", "beach", "forest", "plant", "flower", "tree", "sea", "sunset"],
    "سيارات": ["car", "vehicle", "automobile", "truck", "motorcycle"],
    "مبانٍ": ["structure", "building", "architecture", "house", "interior_room"],
}
ALIASES = {"لقطات": "لقطات الشاشة", "سكرين شوت": "لقطات الشاشة", "شاشة": "لقطات الشاشة", "ناس": "أشخاص", "اشخاص": "أشخاص", "وجوه": "أشخاص",
           "حيوان": "حيوانات", "اكل": "طعام", "أكل": "طعام", "طعام وشراب": "طعام", "وثائق": "مستندات", "مستند": "مستندات", "مباني": "مبانٍ"}


def tool():
    here = Path(__file__).resolve().parent
    for c in (here.parent.parent / "MacOS" / "pbvision", here / "pbvision", Path(shutil.which("pbvision") or "/nonexistent")):
        if c.exists():
            return str(c)
    return None


def available():
    return bool(tool())


FREE = {  # كلمات حرّة شائعة بالعربية ← معرّفات Vision
    "قطة": ["cat"], "قطط": ["cat"], "كلب": ["dog"], "كلاب": ["dog"], "طيور": ["bird"], "طائر": ["bird"], "حصان": ["horse"], "خيول": ["horse"],
    "بحر": ["sea", "ocean", "beach", "shore"], "شاطئ": ["beach", "shore"], "غروب": ["sunset_sunrise", "sunset"], "سماء": ["sky"], "جبال": ["mountain"], "جبل": ["mountain"],
    "ثلج": ["snow"], "زهور": ["flower"], "ورد": ["flower", "rose"], "شجر": ["tree"], "أشجار": ["tree"], "نخيل": ["palm_tree"],
    "أطفال": ["child", "baby"], "طفل": ["child", "baby"], "سيارة": ["car", "vehicle"], "كتاب": ["book"], "كتب": ["book", "bookshelf"],
    "حلويات": ["dessert", "cake", "baked_goods"], "قهوة": ["coffee", "drink"], "فواكه": ["fruit"], "خضار": ["vegetable"], "ليل": ["night_sky", "night"],
    "مسجد": ["mosque", "religious_building", "dome"], "شارع": ["street", "road"], "مطبخ": ["kitchen"], "ورقة": ["document", "paper"], "خط يد": ["handwriting"],
}


def word_ids(word):
    w = ALIASES.get(word.strip(), word.strip())
    return WORDS.get(w) or FREE.get(w) or [w.lower().replace(" ", "_")]  # كلمة حرة: تُطابق معرّف Vision كما هو (بالإنجليزية)


def analyze(paths):
    t = tool()
    if not t or not paths:
        return {}
    r = subprocess.run([t, *map(str, paths)], capture_output=True, text=True, timeout=60 + 5 * len(paths))
    out = {}
    for line in r.stdout.splitlines():
        try:
            d = json.loads(line)
            out[d["path"]] = d
        except Exception:
            pass
    return out


def matches(info, words):
    """هل تطابق الصورة إحدى الكلمات؟"""
    if not info:
        return False
    labels = info.get("labels") or {}
    for w in words:
        for i in word_ids(w):
            if i == "@screenshot" and info.get("screenshot"):
                return True
            if i == "@faces" and (info.get("faces") or 0) > 0:
                return True
            if labels.get(i, 0) >= 0.35:
                return True
    return False


def is_image(path):
    return os.path.splitext(str(path))[1].lower() in IMG_EXT
