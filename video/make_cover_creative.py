"""Creative 5:4 cover: headlines bursting out of the gramophone horn like sound.

Usage: python3 make_cover_creative.py <gramophone_photo.png> <fonts_dir> <out.png>
"""
import math, random, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops, ImageEnhance

PHOTO, FONTS, OUT = sys.argv[1:4]
W, H = 1350, 1080
HORN = (900, 600)  # centre of the gramophone bell in the cropped frame
rng = np.random.default_rng(5)
random.seed(5)

PAPER = (238, 232, 218)
INK = (20, 19, 18)
RED = (204, 32, 30)
YEL = (255, 210, 0)
GOLD = (255, 196, 92)

F = lambda n, s: ImageFont.truetype(f"{FONTS}/{n}", int(s))
ANTON = lambda s: F("Anton-Regular.ttf", s)
COURB = lambda s: F("CourierPrime-Bold.ttf", s)
def OSWB(s):
    f = F("Oswald%5Bwght%5D.ttf", s); f.set_variation_by_name("Bold"); return f

# outlet, big word (both from the coverage), centre x/y, scale, tilt
STRIPS = [
    ("PTI", "SOLD-OUT", 790, 330, 0.55, 10),
    ("Eastern Herald", "SPELLBOUND", 1010, 290, 0.60, -8),
    ("The Tribune", "REDEFINING", 1135, 140, 0.70, 6),
    ("The Wire", "YOUNGEST", 1175, 445, 0.66, 9),
    ("Vie Stories", "HORATH PROJECT", 1150, 595, 0.56, -6),
    ("India Shorts", "PIONEER", 1215, 735, 0.62, 7),
    ("Business News This Week", "MAGNETIC", 1185, 880, 0.58, -8),
]


def paper_tex(w, h, base=PAPER):
    a = np.zeros((h, w, 3))
    fine = rng.standard_normal((h, w)) * 6
    small = rng.standard_normal((h // 30 + 2, w // 30 + 2))
    blot = np.asarray(Image.fromarray(((small - small.min()) / np.ptp(small) * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), float) / 255 - 0.5
    for i in range(3): a[..., i] = base[i] + fine + blot * 26
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).convert("RGBA")


def torn(img, j=9, seed=0):
    r = random.Random(seed); w, h = img.size; st = 12; pts = []
    for x in range(0, w + 1, st): pts.append((x, r.uniform(0, j)))
    for y in range(0, h + 1, st): pts.append((w - r.uniform(0, j), y))
    for x in range(w, -1, -st): pts.append((x, h - r.uniform(0, j)))
    for y in range(h, -1, -st): pts.append((r.uniform(0, j), y))
    m = Image.new("L", img.size, 0); ImageDraw.Draw(m).polygon(pts, fill=255)
    out = img.copy(); out.putalpha(ImageChops.multiply(img.split()[3], m)); return out


def shadow(img, blur=12, off=(10, 14), alpha=150):
    pad = blur * 3
    out = Image.new("RGBA", (img.width + 2 * pad, img.height + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("RGBA", out.size, (0, 0, 0, 0))
    sh.paste((0, 0, 0, 255), (pad + off[0], pad + off[1]), img.split()[3].point(lambda v: v * alpha // 255))
    out = Image.alpha_composite(out, sh.filter(ImageFilter.GaussianBlur(blur)))
    out.alpha_composite(img, (pad, pad)); return out


def place(base, im, cx, cy, scale=1.0, angle=0.0, alpha=1.0):
    if scale != 1.0: im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.LANCZOS)
    if angle: im = im.rotate(angle, resample=Image.BICUBIC, expand=True)
    if alpha < 1: im = im.copy(); im.putalpha(im.split()[3].point(lambda v: int(v * alpha)))
    base.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


def strip(outlet, word, seed):
    wf, of = ANTON(86), OSWB(24)
    w = int(max(wf.getlength(word), of.getlength(outlet.upper()) + 40)) + 70
    im = paper_tex(w, 150)
    d = ImageDraw.Draw(im)
    d.rectangle([30, 18, 30 + of.getlength(outlet.upper()) + 22, 52], fill=INK)
    d.text((41, 18), outlet.upper(), font=of, fill=PAPER)
    d.rectangle([30 + of.getlength(outlet.upper()) + 32, 33, w - 30, 36], fill=RED)
    d.text((32, 44), word, font=wf, fill=INK)
    return torn(im, seed=seed)


def brush(w, h, color, seed):
    r = random.Random(seed)
    im = Image.new("RGBA", (w + 40, h + 30), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for _ in range(9):
        hh = h * r.uniform(0.82, 1); y0 = 15 + (h - hh) / 2 + r.uniform(-4, 4)
        d.polygon([(20 + r.uniform(-14, 6), y0), (20 + w + r.uniform(-6, 16), y0 + r.uniform(-3, 3)),
                   (20 + w + r.uniform(-6, 16), y0 + hh), (20 + r.uniform(-14, 6), y0 + hh + r.uniform(-3, 3))], fill=color + (128,))
    a = np.array(im).astype(float)
    a[..., 3] = np.clip(a[..., 3] * 1.9 * (0.8 + 0.4 * rng.random(a.shape[:2])), 0, 255)
    return Image.fromarray(a.astype(np.uint8))


# ---- background photo, cropped to 5:4 and graded ----
src = Image.open(PHOTO).convert("RGB")
bg = src.crop((0, 300, src.width, 300 + int(src.width * H / W))).resize((W, H), Image.LANCZOS)
bg = ImageEnhance.Contrast(bg).enhance(1.12)
bg = ImageEnhance.Color(bg).enhance(1.08).convert("RGBA")
yy, xx = np.mgrid[0:H, 0:W]
shade = np.clip((yy - H * 0.62) / (H * 0.38), 0, 1) ** 1.3 * 215 + np.clip((H * 0.22 - yy) / (H * 0.22), 0, 1) * 120
bg.alpha_composite(Image.fromarray(np.dstack([np.zeros((H, W, 3)), shade]).astype(np.uint8), "RGBA"))

# ---- golden glow + sound rays from the horn ----
dx, dy = xx - HORN[0], yy - HORN[1]
dist = np.sqrt(dx ** 2 + dy ** 2) + 1
ang = np.degrees(np.arctan2(dy, dx))
fan = np.clip(1 - np.abs(((ang + 40 + 180) % 360) - 180) / 75, 0, 1)
rays = (0.5 + 0.5 * np.sin(np.radians(ang) * 46)) ** 6
glow = np.exp(-dist / 260) * 0.75 + rays * fan * np.exp(-dist / 520) * 0.55
g = np.clip(glow, 0, 1)[..., None] * np.array(GOLD)
bg = Image.fromarray(np.clip(np.asarray(bg.convert("RGB"), float) + g * 0.55, 0, 255).astype(np.uint8)).convert("RGBA")

# sound-wave arcs
arcs = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ad = ImageDraw.Draw(arcs)
for k, r in enumerate(range(250, 760, 70)):
    a = int(110 * (1 - k / 8))
    ad.arc([HORN[0] - r, HORN[1] - r, HORN[0] + r, HORN[1] + r], -110, 20, fill=GOLD + (a,), width=3)
bg.alpha_composite(arcs.filter(ImageFilter.GaussianBlur(1.2)))

# ---- paper confetti along the burst ----
for i in range(45):
    a = math.radians(random.uniform(-80, 30)); r = random.uniform(240, 700)
    x, y = HORN[0] + math.cos(a) * r, HORN[1] + math.sin(a) * r
    s = random.uniform(12, 34) * (0.6 + r / 900)
    bit = torn(paper_tex(int(s * 1.6), int(s)), j=3, seed=i)
    place(bg, bit, x, y, 1.0, random.uniform(0, 360), random.uniform(0.6, 0.95))

# ---- headline strips flying out of the horn (with motion ghosts) ----
for i, (outlet, word, cx, cy, sc, tilt) in enumerate(STRIPS):
    st = shadow(strip(outlet, word, i), blur=12, off=(10, 16), alpha=170)
    vx, vy = cx - HORN[0], cy - HORN[1]
    for g_, k in enumerate((0.42, 0.28, 0.15)):  # motion ghosts trailing back toward the horn
        place(bg, st.filter(ImageFilter.GaussianBlur(5)), cx - vx * k, cy - vy * k, sc * (1 - k * 0.5), tilt, 0.2 * (1 - g_ * 0.25))
    place(bg, st, cx, cy, sc, tilt)

# ---- title ----
d = ImageDraw.Draw(bg)
tf = ANTON(118)
d.text((48, 18), "JUST 20 YEARS OLD", font=tf, fill=(250, 247, 240))
d.text((52, 168), "THE YOUNGEST GUJARATI FOLK ARTIST IN THE INDUSTRY TODAY", font=COURB(22), fill=YEL)
bg.alpha_composite(brush(660, 108, RED, 4), (24, 818))
d.text((60, 820), "& RULING THE STAGE", font=ANTON(84), fill=INK)
nf = ANTON(74)
tag = Image.new("RGBA", (int(nf.getlength("SHIVAM BAROT")) + 60, 118), YEL + (255,))
ImageDraw.Draw(tag).text((30, -2), "SHIVAM BAROT", font=nf, fill=INK)
place(bg, shadow(torn(tag, j=6, seed=9), blur=8, off=(6, 8), alpha=140), 60 + tag.width / 2, 985, 1.0, -2)

# ---- grain + vignette ----
out = bg.convert("RGB")
gr = Image.fromarray(np.clip(128 + rng.standard_normal((H, W)) * 16, 0, 255).astype(np.uint8))
out = ImageChops.overlay(out, Image.merge("RGB", (gr, gr, gr)))
v = (255 * (1 - 0.5 * np.clip(np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) - 0.65, 0, 1))).astype(np.uint8)
v = Image.fromarray(v)
out = ImageChops.multiply(out, Image.merge("RGB", (v, v, v)))
out.save(OUT)
print("saved", OUT)
