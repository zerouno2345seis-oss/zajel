"""يرسم أيقونة «طرفية زاجل»: أيقونة زاجل نفسها على خلفية ليلية، وفي زاويتها علامة الطرفية ›_ ."""
import subprocess, sys, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, str(Path(__file__).parent))
import make_icon

ROOT = Path(__file__).resolve().parent.parent


def main():
    tmp = Path(tempfile.mkdtemp())
    base = tmp / "base.png"
    make_icon.main(str(base))
    img = Image.open(base).convert("RGBA")
    S = img.size[0]
    # الخلفية الليلية: مزج لون كحلي داكن فوق المربع المستدير مع إبقاء الحمامة واضحة
    alpha = img.split()[3]
    night = Image.new("RGBA", img.size, (14, 22, 34, 255))
    # الخلفية وحدها تُعتَّم؛ الحمامة البيضاء والرسالة الصفراء تبقيان بلونيهما
    keep = img.convert("L").point(lambda v: 255 if v > 175 else 0)
    tinted = Image.composite(img, Image.blend(img, night, 0.5), keep)
    tinted.putalpha(alpha)
    d = ImageDraw.Draw(tinted)
    # شارة الطرفية في الزاوية السفلية اليسرى
    x0, y0, x1, y1 = int(S * .14), int(S * .66), int(S * .50), int(S * .86)
    d.rounded_rectangle([x0, y0, x1, y1], radius=int(S * .045), fill=(10, 16, 26, 235), outline=(39, 179, 191, 255), width=int(S * .012))
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", int(S * .15))
    except OSError:
        font = ImageFont.load_default()
    d.text(((x0 + x1) / 2, (y0 + y1) / 2), "›_", font=font, fill=(39, 179, 191, 255), anchor="mm")
    out = ROOT / "icon_terminal.png"
    tinted.save(out)
    iconset = ROOT / "icon_terminal.iconset"
    iconset.mkdir(exist_ok=True)
    for n in (16, 32, 128, 256, 512):
        tinted.resize((n, n), Image.LANCZOS).save(iconset / f"icon_{n}x{n}.png")
        tinted.resize((n * 2, n * 2), Image.LANCZOS).save(iconset / f"icon_{n}x{n}@2x.png")
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(ROOT / "icon_terminal.icns")], check=True)
    print(ROOT / "icon_terminal.icns")


if __name__ == "__main__":
    main()
