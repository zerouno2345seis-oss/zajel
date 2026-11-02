"""يرسم أيقونة «زاجل»: حمامة زاجلة بيضاء تحمل رسالة، فوق خلفية متدرجة بشكل أيقونات macOS."""
import math, sys
from PIL import Image, ImageDraw, ImageFilter

S = 1024 * 2  # رسم مضاعف ثم تصغير لحواف ناعمة


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def main(out):
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    # خلفية: مربع مستدير متدرج (أزرق ليلي ← فيروزي)
    bg = Image.new("RGBA", (S, S))
    top, bot = (24, 52, 120), (18, 168, 178)
    px = bg.load()
    for y in range(S):
        for x in range(0, S):
            t = min(1, max(0, (y * 0.8 + x * 0.35) / (S * 1.15)))
            px[x, y] = (*lerp(top, bot, t), 255)
    m = Image.new("L", (S, S), 0)
    pad = int(S * 0.098)
    ImageDraw.Draw(m).rounded_rectangle([pad, pad, S - pad, S - pad], radius=int(S * 0.185), fill=255)
    img.paste(bg, (0, 0), m)
    d = ImageDraw.Draw(img)
    d = ImageDraw.Draw(img)
    W = (255, 255, 255, 255)
    sc = S / 1024
    P = lambda pts: [(x * sc, y * sc) for x, y in pts]
    # الجناح الخلفي (أفتح قليلًا)
    d.polygon(P([(470, 470), (600, 250), (720, 205), (655, 330), (590, 455)]), fill=(225, 240, 250, 255))
    # الجسم
    d.ellipse(P([(330, 450), (700, 620)]), fill=W)
    # الرأس والمنقار
    d.ellipse(P([(640, 395), (760, 515)]), fill=W)
    d.polygon(P([(752, 440), (812, 462), (752, 482)]), fill=(255, 196, 70, 255))
    d.ellipse(P([(697, 432), (719, 454)]), fill=(24, 52, 120, 255))
    # الذيل
    d.polygon(P([(360, 500), (215, 450), (250, 530), (205, 590), (365, 575)]), fill=W)
    # الجناح الأمامي (كبير مرفوع)
    d.polygon(P([(420, 500), (330, 280), (380, 230), (505, 330), (585, 480)]), fill=W)
    d.line(P([(395, 300), (520, 470)]), fill=(200, 225, 240, 255), width=int(10 * sc))
    d.line(P([(440, 290), (545, 455)]), fill=(200, 225, 240, 255), width=int(8 * sc))
    # الرسالة المعلّقة
    ex, ey, ew, eh = 470, 640, 190, 128
    d.line(P([(560, 600), (565, ey)]), fill=W, width=int(8 * sc))
    d.rounded_rectangle(P([(ex, ey), (ex + ew, ey + eh)]), radius=int(14 * sc), fill=(255, 196, 70, 255))
    d.line(P([(ex + 8, ey + 10), (ex + ew / 2, ey + eh * 0.58), (ex + ew - 8, ey + 10)]), fill=(196, 120, 20, 255), width=int(9 * sc), joint="curve")
    # ظل خفيف تحت الحمامة
    sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse(P([(330, 805), (700, 835)]), fill=(0, 0, 0, 60))
    sh = sh.filter(ImageFilter.GaussianBlur(18 * sc))
    base = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    base.paste(bg, (0, 0), m)
    final = Image.alpha_composite(Image.alpha_composite(base, sh), img)
    final.resize((1024, 1024), Image.LANCZOS).save(out)


if __name__ == "__main__":
    main(sys.argv[1])
