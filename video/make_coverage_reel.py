"""Grunge editorial-collage reel (5:4, 1350x1080) of Shivam Barot's press coverage.

Usage: python3 make_coverage_reel.py <photoA.png,photoB.png> <fonts_dir> <out.mp4> [preview_times]
All on-screen copy is quoted verbatim from the syndicated article the seven outlets published.
"""
import math, random, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageChops

PHOTO, FONTS, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
W, H, FPS = 1350, 1080, 30
rng = np.random.default_rng(11)
random.seed(11)

PAPER = (234, 229, 217)
INK = (20, 19, 18)
RED = (204, 32, 30)
YEL = (255, 210, 0)
WHITE = (250, 248, 242)

HEADLINE = "Just 20 Years Old & Ruling the Stage: How Shivam Barot Became Gujarati Folk’s Biggest Young Sensation"

# name, domain, date (only where the page states it), template, big word, quote, highlighted phrase
OUTLETS = [
    ("The Tribune", "tribuneindia.com", "OCT 08, 2026", "A", "REDEFINING",
     "At just 20 years old, Shivam Barot is not merely participating in the traditional music scene—he is actively redefining it.",
     "actively redefining it."),
    ("The Wire", "thewire.in", "", "B", "YOUNGEST",
     "Holding the distinction of being the youngest Gujarati folk artist in the industry today, Shivam has accomplished what few achieve in a lifetime.",
     "youngest Gujarati folk artist in the industry today,"),
    ("Eastern Herald", "easternherald.com", "OCT 07, 2026", "C", "SPELLBOUND",
     "Shivam is headlining massive arenas, electrifying thousands of garba enthusiasts, and creating a stage aura that leaves audiences spellbound.",
     "electrifying thousands of garba enthusiasts,"),
    ("PTI", "ptinews.com", "", "A", "SOLD-OUT",
     "His performances during the last festive season were nothing short of legendary, delivering consecutive sold-out shows.",
     "consecutive sold-out shows."),
    ("Vie Stories", "viestories.com", "OCT 07, 2026", "B", "THE HORATH PROJECT",
     "The Horath Project, an independent musical tour initiative crafted to bring Gujarati folk music into the modern concert era.",
     "into the modern concert era."),
    ("Business News This Week", "businessnewsthisweek.com", "OCT 07, 2026", "C", "MAGNETIC",
     "The moment he takes the microphone, the energy in the stadium shifts.",
     "the energy in the stadium shifts."),
    ("India Shorts", "indiashorts.com", "OCT 07, 2026", "A", "PIONEER",
     "His ability to lead massive crowds while remaining deeply rooted in his heritage makes him a pioneer among young independent artists.",
     "a pioneer among young independent artists."),
]


# ---------------- fonts ----------------
def F(name, size, var=None):
    f = ImageFont.truetype(f"{FONTS}/{name}", int(size))
    if var:
        try: f.set_variation_by_name(var)
        except Exception: pass
    return f

ANTON = lambda s: F("Anton-Regular.ttf", s)
OSWB = lambda s: F("Oswald%5Bwght%5D.ttf", s, "Bold")
OSWR = lambda s: F("Oswald%5Bwght%5D.ttf", s, "Regular")
TYPE = lambda s: F("SpecialElite-Regular.ttf", s)
COUR = lambda s: F("CourierPrime-Regular.ttf", s)
COURB = lambda s: F("CourierPrime-Bold.ttf", s)
SERIF = lambda s: F("DMSerifDisplay-Regular.ttf", s)
SERIFI = lambda s: F("DMSerifDisplay-Italic.ttf", s)
HAND = lambda s: F("Caveat%5Bwght%5D.ttf", s, "Bold")
MARKER = lambda s: F("PermanentMarker-Regular.ttf", s)


# ---------------- helpers ----------------
def clamp01(t): return min(max(t, 0.0), 1.0)
def ease_out(t): t = clamp01(t); return 1 - (1 - t) ** 3
def ease_io(t): t = clamp01(t); return t * t * (3 - 2 * t)
def back(t):
    t = clamp01(t); c = 1.9
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2


def tsize(f, s):
    b = f.getbbox(s); return b[2] - b[0], b[3] - b[1], b[0], b[1]


def box_blur(a, r):
    k = 2 * r + 1
    for ax in (0, 1):
        pad = [(r + 1, r) if i == ax else (0, 0) for i in range(a.ndim)]
        c = np.cumsum(np.pad(a, pad, mode="edge"), axis=ax)
        n = c.shape[ax]
        a = (np.take(c, range(k, n), axis=ax) - np.take(c, range(0, n - k), axis=ax)) / k
    return a


def noise_img(w, h, scale):
    small = rng.standard_normal((h // scale + 2, w // scale + 2))
    im = Image.fromarray(((small - small.min()) / (np.ptp(small) + 1e-6) * 255).astype(np.uint8))
    return np.asarray(im.resize((w, h), Image.BICUBIC), float) / 255 - 0.5


def paper(w, h, base=PAPER, stain=1.0, vig=0.25):
    a = np.zeros((h, w, 3))
    fine = rng.standard_normal((h, w)) * 7
    blot = noise_img(w, h, 90) * 30 * stain + noise_img(w, h, 25) * 12 * stain
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    v = 1 - vig * np.clip(d - 0.5, 0, 1) ** 1.5
    for i in range(3):
        a[..., i] = (base[i] + fine + blot) * v
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).convert("RGBA")


def dark(w, h, base=(28, 27, 26)):
    return paper(w, h, base=base, stain=1.3, vig=0.45)


def greek_cols(img, x0, y0, x1, y1, cols=4, col=(170, 163, 150, 255), seed=0, lh=13):
    """Faint simulated newsprint columns for texture."""
    r = random.Random(seed)
    d = ImageDraw.Draw(img)
    gap = 26
    cw = (x1 - x0 - gap * (cols - 1)) / cols
    for c in range(cols):
        x = x0 + c * (cw + gap); y = y0
        while y < y1:
            ww = cw * (r.uniform(0.3, 0.75) if r.random() < 0.1 else r.uniform(0.9, 1))
            d.rectangle([x, y, x + ww, y + 4], fill=col)
            y += lh * (2 if r.random() < 0.08 else 1)


def jagged_poly(w, h, j=12, step=16, seed=0, edges="lrtb"):
    r = random.Random(seed)
    pts = []
    for x in range(0, w + 1, step): pts.append((x, r.uniform(0, j) if "t" in edges else 0))
    for y in range(0, h + 1, step): pts.append((w - (r.uniform(0, j) if "r" in edges else 0), y))
    for x in range(w, -1, -step): pts.append((x, h - (r.uniform(0, j) if "b" in edges else 0)))
    for y in range(h, -1, -step): pts.append(((r.uniform(0, j) if "l" in edges else 0), y))
    return pts


def torn(img, j=12, seed=0, edges="lrtb"):
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).polygon(jagged_poly(img.width, img.height, j, 14, seed, edges), fill=255)
    out = img.copy(); out.putalpha(ImageChops.multiply(img.split()[3], m))
    return out


def shadow(img, blur=14, off=(10, 16), alpha=120):
    pad = blur * 3
    out = Image.new("RGBA", (img.width + 2 * pad, img.height + 2 * pad), (0, 0, 0, 0))
    sa = img.split()[3].point(lambda v: v * alpha // 255)
    sh = Image.new("RGBA", out.size, (0, 0, 0, 0))
    sh.paste((0, 0, 0, 255), (pad + off[0], pad + off[1]), sa)
    out = Image.alpha_composite(out, sh.filter(ImageFilter.GaussianBlur(blur)))
    out.alpha_composite(img, (pad, pad))
    return out


def place(base, im, cx, cy, scale=1.0, angle=0.0, alpha=1.0):
    if alpha <= 0.01: return
    if abs(scale - 1) > 1e-3:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BILINEAR)
    if abs(angle) > 0.05:
        im = im.rotate(angle, resample=Image.BICUBIC, expand=True)
    if alpha < 0.999:
        im = im.copy(); im.putalpha(im.split()[3].point(lambda v: int(v * alpha)))
    base.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


def brush_bar(w, h, color, seed=0):
    """Rough marker/brush stroke rectangle."""
    r = random.Random(seed)
    im = Image.new("RGBA", (w + 40, h + 30), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for k in range(9):
        yo = r.uniform(-4, 4); hh = h * r.uniform(0.82, 1.0)
        y0 = 15 + (h - hh) / 2 + yo
        pts = [(20 + r.uniform(-14, 6), y0 + r.uniform(-3, 3)), (20 + w + r.uniform(-6, 16), y0 + r.uniform(-3, 3)),
               (20 + w + r.uniform(-6, 16), y0 + hh + r.uniform(-3, 3)), (20 + r.uniform(-14, 6), y0 + hh + r.uniform(-3, 3))]
        d.polygon(pts, fill=color + (int(255 * 0.5),))
    a = np.array(im).astype(float)
    tex = 0.75 + 0.5 * noise_img(im.width, im.height, 3)
    streak = 0.85 + 0.3 * np.repeat(rng.random((im.height, 1)), im.width, 1)
    a[..., 3] = np.clip(a[..., 3] * 1.9 * tex * streak, 0, 255)
    return Image.fromarray(a.astype(np.uint8))


def reveal_x(im, p):
    """Left-to-right wipe of an RGBA image (for brush strokes)."""
    if p >= 1: return im
    out = im.copy()
    a = np.array(out)
    a[:, int(im.width * clamp01(p)):, 3] = 0
    return Image.fromarray(a)


def tape(w=150, h=46, seed=0):
    im = Image.new("RGBA", (w, h), (232, 222, 190, 170))
    return torn(im, j=5, seed=seed, edges="lr")


# ---------------- photos ----------------
# "A": studio shot on a light backdrop (cut out as a sticker); "B": low-key portrait with gramophone (used as torn prints).
def load_photo(path, cut):
    im = Image.open(path).convert("RGB")
    if im.width < 800:
        k = max(2, 1200 // im.width)
        im = im.resize((im.width * k, im.height * k), Image.LANCZOS).filter(ImageFilter.UnsharpMask(2, 80, 2))
    if not cut:
        return im, None
    arr = np.asarray(im, float)
    border = np.concatenate([arr[:8].reshape(-1, 3), arr[-8:].reshape(-1, 3), arr[:, :8].reshape(-1, 3), arr[:, -8:].reshape(-1, 3)])
    bgc = np.median(border, 0)
    # background = low-saturation light pixels connected to the frame edge (gradient studio backdrop)
    lum = arr.mean(-1); sat = arr.max(-1) - arr.min(-1)
    cand = ((np.abs(arr - bgc).max(-1) < 34) | ((lum > bgc.mean() - 30) & (sat < 14))).astype(np.uint8) * 255
    ff_ = Image.fromarray(cand).filter(ImageFilter.MedianFilter(5))
    for seed in [(0, 0), (ff_.width - 1, 0), (0, ff_.height - 1), (ff_.width - 1, ff_.height - 1), (ff_.width // 2, 0)]:
        if ff_.getpixel(seed) == 255: ImageDraw.floodfill(ff_, seed, 128)
    m = (~(np.asarray(ff_) == 128)).astype(float)
    m = (box_blur(m, 2) > 0.5).astype(np.uint8) * 255
    return im, Image.fromarray(m).filter(ImageFilter.GaussianBlur(1.0))


_paths = PHOTO.split(",")
PHOTOS = {"A": load_photo(_paths[0], True), "B": load_photo(_paths[1], False)}


def get_photo(pid, crop=None):
    im, mk = PHOTOS[pid]
    if crop:
        box = (int(crop[0] * im.width), int(crop[1] * im.height), int(crop[2] * im.width), int(crop[3] * im.height))
        im = im.crop(box); mk = mk.crop(box) if mk else None
    return im, mk


def stylize(im, style):
    if style == "bw":
        g = ImageOps.autocontrast(ImageOps.grayscale(im), cutoff=1)
        return ImageOps.colorize(g, (18, 18, 18), (245, 242, 235))
    if style == "duo":
        g = ImageOps.autocontrast(ImageOps.grayscale(im), cutoff=1)
        return ImageOps.colorize(g, (25, 10, 10), (240, 60, 50), mid=(150, 25, 25))
    if style == "warm":
        return ImageOps.autocontrast(im, cutoff=0.5)
    return im


def add_grain(im, amt=9):
    a = np.array(im).astype(float)
    a[..., :3] = np.clip(a[..., :3] + rng.standard_normal(a.shape[:2])[..., None] * amt, 0, 255)
    return Image.fromarray(a.astype(np.uint8))


def cutout(pid, style, height, crop=None, border=12):
    raw, mk = get_photo(pid, crop)
    bb = mk.getbbox(); raw, mk = raw.crop(bb), mk.crop(bb)
    im = stylize(raw, style).convert("RGBA"); im.putalpha(mk)
    s = height / im.height
    im = add_grain(im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS))
    mk = im.split()[3]
    pad = border * 2
    big = Image.new("L", (im.width + 2 * pad, im.height + 2 * pad), 0); big.paste(mk, (pad, pad))
    st = big.filter(ImageFilter.MaxFilter(min(31, border * 2 + 1))).filter(ImageFilter.GaussianBlur(1))
    out = Image.new("RGBA", big.size, WHITE + (0,)); out.putalpha(st)
    out.alpha_composite(im, (pad, pad))
    return shadow(out, blur=16, off=(12, 18), alpha=140)


def torn_print(pid, style, height, crop=None, seed=0, border=14):
    """Rectangular photo print with a white border and torn edges."""
    raw, _ = get_photo(pid, crop)
    im = stylize(raw, style)
    s = height / im.height
    im = add_grain(im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS).convert("RGBA"), 7)
    card = Image.new("RGBA", (im.width + 2 * border, im.height + 2 * border), WHITE + (255,))
    card.alpha_composite(im, (border, border))
    return shadow(torn(card, j=10, seed=seed), blur=16, off=(12, 18), alpha=150)


def polaroid(pid, style, w, crop=None):
    raw, mk = get_photo(pid, crop)
    ph = stylize(raw, style).convert("RGB")
    if mk is not None:
        bg = Image.new("RGB", ph.size, (236, 232, 224)); bg.paste(ph, (0, 0), mk); ph = bg
    s = (w - 40) / ph.width
    ph = ph.resize((int(ph.width * s), int(ph.height * s)), Image.LANCZOS)
    hh = min(ph.height, int((w - 40) * 1.18))
    ph = ph.crop((0, 0, ph.width, hh))
    card = Image.new("RGBA", (w, hh + 130), WHITE + (255,))
    card.paste(ph, (20, 20))
    d = ImageDraw.Draw(card)
    f = HAND(54)
    tw = tsize(f, "Shivam Barot, 20")[0]
    d.text(((w - tw) / 2, hh + 42), "Shivam Barot, 20", font=f, fill=(40, 40, 120))
    return card


# crops (fractions of each source image)
A_FULL, A_UPPER, A_FACE = None, (0.0, 0.0, 1.0, 0.62), (0.08, 0.04, 0.72, 0.46)
B_FULL, B_HALF, B_FACE, B_TALL = (0.0, 0.12, 1.0, 1.0), (0.0, 0.2, 0.62, 0.78), (0.06, 0.16, 0.56, 0.5), (0.0, 0.14, 0.78, 0.96)

# which photo each segment uses: (kind, photo, style, crop)
SHOTS = [
    ("cut", "A", "color", A_FULL),    # Tribune
    ("polaroid", "A", "color", A_FACE),  # The Wire
    ("print", "B", "duo", B_HALF),    # Eastern Herald
    ("cut", "A", "bw", A_FULL),       # PTI
    ("polaroid", "B", "warm", B_FACE),  # Vie Stories
    ("cut", "A", "duo", A_UPPER),     # Business News This Week
    ("print", "B", "bw", B_TALL),     # India Shorts
]


def shot_image(i, height):
    kind, pid, style, crop = SHOTS[i]
    if kind == "cut": return cutout(pid, style, height, crop)
    if kind == "print": return torn_print(pid, style, height, crop, seed=i)
    return shadow(polaroid(pid, style, int(height * 0.5), crop), blur=14, off=(12, 18), alpha=150)


# ---------------- text layout ----------------
def layout(text, font, maxw, lh):
    """Return list of words with (x, y, w) and char offsets."""
    words = text.split(" ")
    out, x, y, pos = [], 0, 0, 0
    space = tsize(font, " ")[0] or font.size * 0.3
    for wd in words:
        ww = font.getlength(wd)
        if x > 0 and x + ww > maxw:
            x = 0; y += lh
        out.append({"w": wd, "x": x, "y": y, "wd": ww, "c0": pos, "c1": pos + len(wd)})
        x += ww + font.getlength(" "); pos += len(wd) + 1
    return out


def phrase_idx(words, phrase):
    toks = phrase.split(" ")
    for i in range(len(words) - len(toks) + 1):
        if [w["w"] for w in words[i:i + len(toks)]] == toks:
            return list(range(i, i + len(toks)))
    return []


def draw_typed(img, words, font, ox, oy, nchars, color, hl=None, hl_p=0.0, hl_color=YEL, cursor=True):
    d = ImageDraw.Draw(img)
    asc = font.getmetrics()[0]
    if hl and hl_p > 0:
        boxes = [words[i] for i in hl]
        total = sum(b["wd"] for b in boxes)
        rem = total * hl_p
        for b in boxes:
            if rem <= 0: break
            ww = min(b["wd"] + font.getlength(" ") * 0.6, rem + 2)
            d.rectangle([ox + b["x"] - 4, oy + b["y"] + asc * 0.12, ox + b["x"] + ww, oy + b["y"] + asc * 1.18], fill=hl_color + (235,))
            rem -= b["wd"]
    last = None
    for w in words:
        if nchars <= w["c0"]: break
        s = w["w"][: max(0, int(nchars - w["c0"]))]
        d.text((ox + w["x"], oy + w["y"]), s, font=font, fill=color)
        last = (ox + w["x"] + font.getlength(s), oy + w["y"])
    if cursor and last and nchars < words[-1]["c1"]:
        d.rectangle([last[0] + 3, last[1] + asc * 0.15, last[0] + 3 + font.size * 0.5, last[1] + asc * 1.1], fill=color)


def fit(font_fn, text, maxw, start, minsize=20):
    s = start
    while s > minsize and font_fn(s).getlength(text) > maxw: s -= 4
    return font_fn(s)


# ---------------- grain & finishing ----------------
GRAIN = [Image.fromarray(np.clip(128 + rng.standard_normal((H, W)) * 22, 0, 255).astype(np.uint8)) for _ in range(4)]
yy, xx = np.mgrid[0:H, 0:W]
VIG = Image.fromarray((255 * (1 - 0.55 * np.clip(np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) - 0.6, 0, 1) ** 1.3)).astype(np.uint8))


def finish(fr, n):
    g = GRAIN[n % 4]
    fr = ImageChops.overlay(fr.convert("RGB"), Image.merge("RGB", (g, g, g)))
    fr = ImageChops.multiply(fr, Image.merge("RGB", (VIG, VIG, VIG)))
    return fr


# ---------------- scenes ----------------
EVENTS = []  # (time, kind)


class Scene:
    dur = 5.0
    def frame(self, t): raise NotImplementedError


class Intro(Scene):
    dur = 4.6
    def __init__(self):
        self.bg = dark(W, H)
        greek_cols(self.bg, 60, 60, W - 60, H - 60, cols=5, col=(48, 46, 44, 255), seed=9)
        self.photo = torn_print("B", "warm", 800, (0.0, 0.18, 1.0, 1.0), seed=1)
        self.w1 = ANTON(160)
        self.bar = brush_bar(760, 120, RED, seed=4)
        self.sub_words = layout("How Shivam Barot Became Gujarati Folk’s Biggest Young Sensation", TYPE(36), 620, 48)

    def frame(self, t):
        fr = self.bg.copy()
        # photo rises from bottom right
        p = ease_out((t - 0.15) / 0.8)
        place(fr, self.photo, 1090, 620 + (1 - p) * 700, 1.0, -3 + (1 - p) * 8)
        d = ImageDraw.Draw(fr)
        words = [("JUST", 0.35), ("20 YEARS", 0.7), ("OLD", 1.05)]
        y = 40
        for wd, st in words:
            q = (t - st) / 0.22
            if q > 0:
                sc = 1 + 0.9 * (1 - back(q))
                layer = Image.new("RGBA", (int(self.w1.getlength(wd)) + 20, 200), (0, 0, 0, 0))
                ImageDraw.Draw(layer).text((10, -26), wd, font=self.w1, fill=WHITE)
                place(fr, layer, 70 + layer.width / 2, y + 100, sc, 0, clamp01(q * 3))
            y += 178
        # brush bar + "& RULING THE STAGE"
        bp = (t - 1.45) / 0.35
        if bp > 0:
            fr.alpha_composite(reveal_x(self.bar, ease_out(bp)), (40, 620))
            if bp > 0.6:
                d.text((80, 622), "& RULING THE STAGE", font=ANTON(92), fill=INK)
        tp = (t - 2.0) * 60
        if tp > 0:
            draw_typed(fr, self.sub_words, TYPE(36), 80, 800, tp, (215, 210, 200))
        return fr


class TemplateA(Scene):
    """Paper page: outlet tag, slammed big word over brush stroke, cut-out photo, typed quote."""
    dur = 5.6
    def __init__(self, i, o):
        self.o = o; self.i = i; name, dom, date, _, big, quote, hl = o
        self.bg = paper(W, H)
        greek_cols(self.bg, 50, 40, W - 50, H - 40, cols=6, seed=i)
        self.photo = shot_image(i, 860 if SHOTS[i][0] == "cut" else 700)
        self.bigf = fit(ANTON, big, 820, 230)
        self.bar = brush_bar(int(self.bigf.getlength(big)) + 40, int(self.bigf.size * 0.62), RED, seed=i + 20)
        self.tag = self.make_tag(name, dom, date)
        self.qf = TYPE(36)
        self.words = layout(quote, self.qf, 740, 50)
        self.hl = phrase_idx(self.words, hl)
        self.nchar = len(quote)

    @staticmethod
    def make_tag(name, dom, date):
        f1, f2 = OSWB(54), COURB(24)
        info = dom + ("   ·   " + date if date else "")
        w = int(max(f1.getlength(name.upper()), f2.getlength(info)) + 70)
        im = Image.new("RGBA", (w, 132), INK + (255,))
        d = ImageDraw.Draw(im)
        d.text((34, 10), name.upper(), font=f1, fill=WHITE)
        d.text((36, 92), info, font=f2, fill=YEL)
        d.rectangle([0, 0, 12, 132], fill=RED + (255,))
        return shadow(torn(im, j=6, seed=len(name), edges="r"), blur=8, off=(6, 8), alpha=110)

    def frame(self, t):
        fr = self.bg.copy()
        p = ease_out((t - 0.1) / 0.7)
        tp = ease_out(t / 0.45)
        fr.alpha_composite(self.tag, (int(-self.tag.width + tp * (self.tag.width + 20)), 30))
        big = self.o[4]
        photo_args = (self.photo, min(1080, W - self.photo.width / 2 + 20), 600 + (1 - p) * 650, 1.0, 3 - (1 - p) * 6)
        on_top = SHOTS[self.i][0] == "cut"  # cut-outs sit above the big word so it never crosses the face
        if not on_top: place(fr, *photo_args)
        bp = (t - 0.35) / 0.3
        if bp > 0:
            fr.alpha_composite(reveal_x(self.bar, ease_out(bp)), (40, 250 + int(self.bigf.size * 0.25)))
        q = (t - 0.55) / 0.22
        if q > 0:
            layer = Image.new("RGBA", (int(self.bigf.getlength(big)) + 30, int(self.bigf.size * 1.4)), (0, 0, 0, 0))
            ImageDraw.Draw(layer).text((15, 0), big, font=self.bigf, fill=INK)
            place(fr, layer, 70 + layer.width / 2, 250 + layer.height / 2, 1 + 0.8 * (1 - back(q)), 0, clamp01(q * 3))
        if on_top: place(fr, *photo_args)
        typ = (t - 1.0) * 58
        hlp = (t - 1.0 - self.nchar / 58 - 0.1) / 0.6
        # paper strip behind quote
        if typ > 0:
            draw_typed(fr, self.words, self.qf, 78, 640, typ, INK, self.hl, ease_io(hlp))
        ImageDraw.Draw(fr).text((80, H - 62), "SOURCE: " + self.o[1].upper(), font=COURB(22), fill=(90, 86, 80))
        return fr


class TemplateB(Scene):
    """Dark desk: torn article clipping with masthead + typed quote, polaroid photo with tape, marker underline."""
    dur = 5.8
    def __init__(self, i, o):
        self.o = o; name, dom, date, _, big, quote, hl = o
        self.bg = dark(W, H)
        greek_cols(self.bg, 40, 40, W - 40, H - 40, cols=6, col=(44, 42, 40, 255), seed=i + 50)
        cw, ch = 790, 900
        clip = paper(cw, ch, base=(240, 236, 226), stain=0.6, vig=0.3)
        d = ImageDraw.Draw(clip)
        mf = fit(SERIF, name, cw - 100, 96)
        tw = mf.getlength(name)
        d.text(((cw - tw) / 2, 34), name, font=mf, fill=INK)
        y = 60 + mf.size
        d.rectangle([50, y, cw - 50, y + 4], fill=INK); d.rectangle([50, y + 10, cw - 50, y + 11], fill=INK)
        d.text((52, y + 22), dom.upper(), font=COURB(20), fill=(90, 86, 80))
        if date: d.text((cw - 52 - COURB(20).getlength(date), y + 22), date, font=COURB(20), fill=(90, 86, 80))
        y += 70
        hf = SERIF(40)
        for w_ in self.wrap(HEADLINE, hf, cw - 100):
            d.text((50, y), w_, font=hf, fill=INK); y += 48
        y += 16
        d.rectangle([50, y, cw - 50, y + 2], fill=(120, 115, 105))
        self.q_y = y + 30
        greek_cols(clip, 50, ch - 170, cw - 50, ch - 50, cols=2, seed=i + 7)
        self.clip_base = clip
        self.mast_y = 60 + mf.size; self.mast_w = tw
        self.qf = COUR(34)
        self.words = layout(quote, self.qf, cw - 100, 46)
        self.hl = phrase_idx(self.words, hl)
        self.nchar = len(quote)
        self.pol = shadow(polaroid(SHOTS[i][1], SHOTS[i][2], 420, SHOTS[i][3]), blur=14, off=(12, 18), alpha=150)
        self.tape1, self.tape2 = tape(seed=i), tape(seed=i + 1)
        self.cw, self.ch = cw, ch
        self.big = big

    @staticmethod
    def wrap(s, f, maxw):
        out, cur = [], ""
        for w in s.split():
            t = (cur + " " + w).strip()
            if f.getlength(t) <= maxw: cur = t
            else: out.append(cur); cur = w
        out.append(cur); return out

    def frame(self, t):
        fr = self.bg.copy()
        clip = self.clip_base.copy()
        typ = (t - 0.9) * 60
        hlp = (t - 0.9 - self.nchar / 60 - 0.1) / 0.6
        if typ > 0:
            draw_typed(clip, self.words, self.qf, 50, self.q_y, typ, INK, self.hl, ease_io(hlp))
        # red marker underline under masthead
        up = ease_out((t - 0.6) / 0.4)
        if up > 0:
            d = ImageDraw.Draw(clip)
            x0 = (self.cw - self.mast_w) / 2; y0 = self.mast_y - 8
            pts = [(x0 + k * self.mast_w * up / 20, y0 + math.sin(k * 0.9) * 3) for k in range(21)]
            d.line(pts, fill=RED, width=8, joint="curve")
        clip = shadow(torn(clip, j=14, seed=7), blur=16, off=(12, 20), alpha=150)
        p = ease_out(t / 0.55)
        place(fr, clip, 470 - (1 - p) * 900, 545, 1.0, -2 + (1 - p) * -6)
        pp = ease_out((t - 0.3) / 0.6)
        place(fr, self.pol, 1080 + (1 - pp) * 500, 520, 1.0, 5 + (1 - pp) * 10)
        if pp > 0.95:
            place(fr, self.tape1, 1000, 205, 1.0, -18)
            place(fr, self.tape2, 1170, 225, 1.0, 22)
        # big word stamp along the bottom
        sq = (t - 2.2) / 0.25
        if sq > 0:
            f = fit(ANTON, self.big, 560, 110)
            layer = Image.new("RGBA", (int(f.getlength(self.big)) + 50, int(f.size * 1.45)), (0, 0, 0, 0))
            dl = ImageDraw.Draw(layer)
            dl.rectangle([0, 0, layer.width, layer.height], fill=YEL + (255,))
            dl.text((25, 0), self.big, font=f, fill=INK)
            place(fr, layer, min(1080, W - layer.width / 2 - 45), 930, 1 + 0.9 * (1 - back(sq)), -4, clamp01(sq * 3))
        return fr


class TemplateC(Scene):
    """Split: dark panel with stacked outlet name, duotone photo, paper side with big red word and serif quote."""
    dur = 5.6
    def __init__(self, i, o):
        self.o = o; name, dom, date, _, big, quote, hl = o
        self.split = 520
        self.left = dark(self.split, H, base=(22, 21, 20))
        self.right = paper(W - self.split, H)
        greek_cols(self.right, 40, 40, W - self.split - 40, H - 40, cols=4, seed=i + 90)
        self.name_lines = self.stack(name.upper())
        self.photo = shot_image(i, 560 if SHOTS[i][0] == "cut" else 470)
        self.bigf = fit(ANTON, big, W - self.split - 140, 200)
        self.qf = SERIFI(54)
        self.words = layout(quote, self.qf, W - self.split - 150, 66)
        self.hl = phrase_idx(self.words, hl)

    @staticmethod
    def stack(name):
        words = name.split()
        if len(words) > 2: words = [" ".join(words[:2]), " ".join(words[2:])]
        return words

    def frame(self, t):
        fr = Image.new("RGBA", (W, H))
        p = ease_out(t / 0.5)
        fr.alpha_composite(self.right, (self.split, 0))
        fr.alpha_composite(self.left, (int(-self.split * (1 - p)), 0))
        d = ImageDraw.Draw(fr)
        # outlet name stacked
        y = 70
        for k, ln in enumerate(self.name_lines):
            q = ease_out((t - 0.25 - k * 0.12) / 0.4)
            f = fit(ANTON, ln, self.split - 90, 130)
            if q > 0:
                d.text((45 - (1 - q) * 300, y), ln, font=f, fill=WHITE)
            y += int(f.size * 1.18)
        q = ease_out((t - 0.55) / 0.4)
        if q > 0:
            d.text((48, y + 10), self.o[1], font=COURB(26), fill=YEL)
            if self.o[2]: d.text((48, y + 46), self.o[2], font=COURB(26), fill=YEL)
        pp = ease_out((t - 0.35) / 0.7)
        place(fr, self.photo, 280, 800 + (1 - pp) * 500, 1.0, -4)
        # big red word on the paper side
        bq = (t - 0.7) / 0.22
        if bq > 0:
            big = self.o[4]
            layer = Image.new("RGBA", (int(self.bigf.getlength(big)) + 30, int(self.bigf.size * 1.4)), (0, 0, 0, 0))
            ImageDraw.Draw(layer).text((15, 0), big, font=self.bigf, fill=RED)
            place(fr, layer, self.split + 70 + layer.width / 2, 110 + layer.height / 2, 1 + 0.8 * (1 - back(bq)), 0, clamp01(bq * 3))
        # word-by-word serif quote
        ox, oy = self.split + 75, 160 + int(self.bigf.size * 1.4)
        asc = self.qf.getmetrics()[0]
        n_words = len(self.words)
        rate = 9.0
        hlp = ease_io((t - 1.2 - n_words / rate - 0.1) / 0.6)
        if self.hl and hlp > 0:
            boxes = [self.words[i] for i in self.hl]
            total = sum(b["wd"] for b in boxes); rem = total * hlp
            for b in boxes:
                if rem <= 0: break
                ww = min(b["wd"], rem)
                d.rectangle([ox + b["x"], oy + b["y"] + asc * 1.0, ox + b["x"] + ww + 6, oy + b["y"] + asc * 1.14], fill=RED)
                rem -= b["wd"]
        for k, w in enumerate(self.words):
            a = clamp01((t - 1.2 - k / rate) / 0.18)
            if a <= 0: break
            col = tuple(int(PAPER[c] + (INK[c] - PAPER[c]) * a) for c in range(3))
            d.text((ox + w["x"], oy + w["y"] + (1 - a) * 12), w["w"], font=self.qf, fill=col)
        d.text((self.split + 75, H - 62), "SOURCE: " + self.o[1].upper(), font=COURB(22), fill=(90, 86, 80))
        return fr


class Outro(Scene):
    dur = 6.6
    def __init__(self):
        self.bg = paper(W, H)
        greek_cols(self.bg, 50, 40, W - 50, H - 40, cols=6, seed=99)
        self.photo = cutout("A", "bw", 700)
        self.photo2 = torn_print("B", "warm", 520, B_HALF, seed=5)
        self.tags = []
        for i, o in enumerate(OUTLETS):
            f = OSWB(34)
            w = int(f.getlength(o[0].upper()) + 50)
            im = Image.new("RGBA", (w, 64), INK + (255,))
            ImageDraw.Draw(im).text((25, 6), o[0].upper(), font=f, fill=WHITE)
            self.tags.append(shadow(torn(im, j=5, seed=i, edges="lr"), blur=6, off=(5, 6), alpha=110))
        self.bar = brush_bar(600, 150, RED, seed=77)

    def frame(self, t):
        fr = self.bg.copy()
        d = ImageDraw.Draw(fr)
        hp = ease_out(t / 0.4)
        d.text((70 - (1 - hp) * 400, 50), "AS FEATURED IN", font=ANTON(84), fill=INK)
        # tags in two columns
        x, y = 70, 190
        for i, tg in enumerate(self.tags):
            q = (t - 0.35 - i * 0.16) / 0.2
            if q > 0:
                place(fr, tg, x + tg.width / 2, y + tg.height / 2, 1 + 0.7 * (1 - back(q)), (-2, 1.5, -1, 2, -1.5, 1, -2)[i], clamp01(q * 3))
            y += 82
        pp = ease_out((t - 0.2) / 0.8)
        place(fr, self.photo2, 1000, 420 + (1 - pp) * 700, 1.0, -6)
        place(fr, self.photo, 1170, 680 + (1 - pp) * 600, 1.0, 3)
        bp = (t - 1.9) / 0.4
        if bp > 0:
            fr.alpha_composite(reveal_x(self.bar, ease_out(bp)), (30, 795))
        nq = (t - 2.2) / 0.25
        if nq > 0:
            nf = ANTON(108)
            layer = Image.new("RGBA", (int(nf.getlength("SHIVAM BAROT")) + 20, 170), (0, 0, 0, 0))
            ImageDraw.Draw(layer).text((10, 4), "SHIVAM BAROT", font=nf, fill=WHITE)
            place(fr, layer, 70 + layer.width / 2, 795 + 92, 1 + 0.6 * (1 - back(nq)), 0, clamp01(nq * 3))
        sp = (t - 2.8) * 55
        if sp > 0:
            words = layout("The youngest Gujarati folk artist in the industry today", TYPE(30), 720, 40)
            draw_typed(fr, words, TYPE(30), 78, 975, sp, INK)
        fade = clamp01((t - (self.dur - 0.7)) / 0.7)
        if fade > 0:
            fr = Image.blend(fr, Image.new("RGBA", (W, H), (10, 10, 10, 255)), fade)
        return fr


print("building scenes...", flush=True)
TEMPL = {"A": TemplateA, "B": TemplateB, "C": TemplateC}
SCENES = [Intro()] + [TEMPL[o[3]](i, o) for i, o in enumerate(OUTLETS)] + [Outro()]
STARTS = []
acc = 0.0
for s in SCENES:
    STARTS.append(acc); acc += s.dur
TOTAL = acc
TRANS = 0.45
N = int(TOTAL * FPS)
print(f"duration {TOTAL:.1f}s, {N} frames", flush=True)

TEAR = {}
def tear_mask(x, seed):
    """Mask (L) that is 255 to the right of a jagged vertical tear at x."""
    r = random.Random(seed)
    pts = [(W + 50, -10), (x, -10)]
    yy_ = -10
    while yy_ < H + 10:
        yy_ += r.uniform(14, 30); pts.append((x + r.uniform(-22, 22), yy_))
    pts.append((W + 50, H + 10))
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).polygon(pts, fill=255)
    return m


def frame_at(t, n=0):
    k = max(i for i, s in enumerate(STARTS) if s <= t + 1e-9)
    k = min(k, len(SCENES) - 1)
    lt = t - STARTS[k]
    cur = SCENES[k].frame(lt)
    # slow push-in
    z = 1 + 0.035 * lt / SCENES[k].dur
    if z > 1.001:
        cw, ch = W / z, H / z
        cur = cur.resize((W, H), Image.BILINEAR, box=((W - cw) / 2, (H - ch) / 2, (W + cw) / 2, (H + ch) / 2))
    # slam shake for the first beats of each scene's big word
    if k > 0 and lt < TRANS:
        prev = SCENES[k - 1].frame(SCENES[k - 1].dur - 1e-3)
        pz = 1.035
        cw, ch = W / pz, H / pz
        prev = prev.resize((W, H), Image.BILINEAR, box=((W - cw) / 2, (H - ch) / 2, (W + cw) / 2, (H + ch) / 2))
        p = ease_io(lt / TRANS)
        x = int(W * (1 - p))
        m = tear_mask(x, k)
        edge = m.filter(ImageFilter.MaxFilter(9))
        rim = Image.new("RGBA", (W, H), WHITE + (255,))
        sh = ImageChops.subtract(m.filter(ImageFilter.GaussianBlur(18)).point(lambda v: min(255, v * 2)), m)
        base = prev.copy()
        base.paste(Image.new("RGBA", (W, H), (0, 0, 0, 255)), (0, 0), sh.point(lambda v: v // 2))
        base.paste(rim, (0, 0), edge)
        base.paste(cur, (0, 0), m)
        cur = base
    return finish(cur, n)


if len(sys.argv) > 4:
    for ts in sys.argv[4].split(","):
        frame_at(float(ts)).save(f"{OUT}_{ts}.png")
    sys.exit(0)


# ---------------- audio ----------------
SR = 44100
audio = np.zeros(int((TOTAL + 1) * SR))

def add(sig, at, g=1.0):
    i = int(at * SR)
    if i >= len(audio): return
    seg = sig[: len(audio) - i]; audio[i:i + len(seg)] += seg * g

def env_exp(n, k): return np.exp(-np.arange(n) / SR * k)

def kick():
    n = int(0.35 * SR); t = np.arange(n) / SR
    return np.sin(2 * np.pi * (48 * t + 90 * (1 - np.exp(-t * 30)) / 30)) * env_exp(n, 9)

def snare():
    n = int(0.25 * SR)
    nz = rng.standard_normal(n); nz = nz - np.concatenate([[0], nz[:-1]]) * 0.6
    t = np.arange(n) / SR
    return (nz * 0.6 + np.sin(2 * np.pi * 190 * t) * 0.5) * env_exp(n, 22)

def hat():
    n = int(0.06 * SR); nz = rng.standard_normal(n)
    nz = nz - np.concatenate([[0], nz[:-1]])
    return nz * env_exp(n, 70) * 0.35

def click():
    n = int(0.03 * SR); nz = rng.standard_normal(n)
    t = np.arange(n) / SR
    return (nz * 0.5 + np.sin(2 * np.pi * 1800 * t) * 0.6) * env_exp(n, 160)

def thud():
    n = int(0.4 * SR); t = np.arange(n) / SR
    return (np.sin(2 * np.pi * (70 * t - 40 * t * t)) * env_exp(n, 12) + rng.standard_normal(n) * env_exp(n, 50) * 0.4)

def rip(d=0.45):
    n = int(d * SR); nz = rng.standard_normal(n)
    crackle = (rng.random(n) < 0.02) * rng.standard_normal(n) * 4
    s = box_blur((nz + crackle)[None, :], 2)[0]
    env = np.sin(np.linspace(0, np.pi, n)) ** 0.7
    return s * env * 0.8

BPM = 100; beat = 60 / BPM
b = 0; tt = 0.0
while tt < TOTAL - 0.7:
    if b % 4 in (0, 2): add(kick(), tt, 0.9)
    if b % 4 in (1, 3): add(snare(), tt, 0.35)
    add(hat(), tt + beat / 2, 0.5)
    b += 1; tt += beat
# drone bed
n = len(audio); t_ = np.arange(n) / SR
bed = sum(np.sin(2 * np.pi * f * t_) for f in (55, 82.4, 110)) / 3
bed *= np.minimum(1, t_ / 2) * np.clip((TOTAL - t_) / 1.5, 0, 1) * 0.12
audio += bed

for k, s in enumerate(SCENES):
    st = STARTS[k]
    if k > 0: add(rip(), st - 0.05, 0.7)
    if isinstance(s, Intro):
        for x in (0.35, 0.7, 1.05): add(thud(), x, 0.9)
        add(thud(), 1.5, 0.7)
        for c in range(int(len("How Shivam Barot Became Gujarati Folk's Biggest Young Sensation"))): add(click(), st + 2.0 + c / 60, 0.25)
    elif isinstance(s, TemplateA):
        add(thud(), st + 0.55, 1.0)
        for c in range(0, s.nchar, 2): add(click(), st + 1.0 + c / 58, 0.25)
    elif isinstance(s, TemplateB):
        add(thud(), st + 2.2, 0.9)
        for c in range(0, s.nchar, 2): add(click(), st + 0.9 + c / 60, 0.25)
    elif isinstance(s, TemplateC):
        add(thud(), st + 0.7, 1.0)
    elif isinstance(s, Outro):
        for i in range(len(OUTLETS)): add(thud(), st + 0.35 + i * 0.16, 0.45)
        add(thud(), st + 2.2, 1.0)
audio = np.tanh(audio * 1.2)
audio = audio / (np.abs(audio).max() + 1e-6) * 0.9
fade = np.clip((TOTAL - np.arange(len(audio)) / SR) / 0.7, 0, 1); audio *= fade
wav = OUT.rsplit(".", 1)[0] + ".wav"
with wave.open(wav, "w") as wf:
    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR)
    wf.writeframes((audio * 32767).astype(np.int16).tobytes())

# ---------------- render ----------------
ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                       "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "slow", "-crf", "27", "-pix_fmt", "yuv420p",
                       "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", OUT], stdin=subprocess.PIPE)
for n in range(N):
    ff.stdin.write(frame_at(n / FPS, n).tobytes())
    if n % 150 == 0: print(f"frame {n}/{N}", flush=True)
ff.stdin.close(); ff.wait()
print("done", OUT)
