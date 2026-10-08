"""Render a newspaper-style press-coverage video (1080x1920, 30fps) from the order-link spreadsheet."""
import math, random, subprocess, sys, wave, struct
from urllib.parse import urlparse
import numpy as np
import openpyxl
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

XLSX = sys.argv[1]
OUT = sys.argv[2]
FONTS = sys.argv[3]

W, H, FPS = 1080, 1920, 30
S = 1.5  # supersampling for the front page (allows zoom without blur)
random.seed(7); np.random.seed(7)

PAPER = (243, 235, 214)
INK = (30, 25, 20)
RED = (150, 32, 26)
GREY = (120, 110, 95)

# ---------- data ----------
ws = openpyxl.load_workbook(XLSX, data_only=True).active
rows = [r for r in ws.iter_rows(min_row=2, values_only=True) if r[1]]
TOTAL_PUBS = len(rows)
TOTAL_REACH = sum(int(r[2]) for r in rows)
pubs = sorted(rows, key=lambda r: -int(r[2]))[:12]
TOP = []
for r in pubs:
    name = r[1].replace("Stratup", "Startup").replace("Business News this week", "Business News This Week")
    name = "Google News" if name == "Google" else name
    dom = urlparse(r[3]).netloc.replace("www.", "")
    TOP.append((name, int(r[2]), dom))
HEADLINE = "Just 20 Years Old, Ruling the Stage"
SUBHEAD = "How Shivam Barot Became Gujarati Folk's Biggest Young Sensation"


def fmt_num(n):
    if n >= 1e9: return f"{n/1e9:.1f} B"
    if n >= 1e6: return f"{n/1e6:.1f} M"
    if n >= 1e3: return f"{n/1e3:.1f} K"
    return str(n)


CRORE = f"{TOTAL_REACH/1e7:.1f}"

# ---------- fonts ----------
def F(name, size, var=None):
    f = ImageFont.truetype(f"{FONTS}/{name}", int(size))
    if var: f.set_variation_by_name(var)
    return f

BLACK = lambda s: F("PlayfairDisplay%5Bwght%5D.ttf", s, "Black")
BOLDP = lambda s: F("PlayfairDisplay%5Bwght%5D.ttf", s, "Bold")
GOTH = lambda s: F("UnifrakturMaguntia-Book.ttf", s)
OSB = lambda s: F("OldStandard-Bold.ttf", s)
OSR = lambda s: F("OldStandard-Regular.ttf", s)
OSI = lambda s: F("OldStandard-Italic.ttf", s)
SYM = lambda s: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(s))

# ---------- helpers ----------
def ease_out(t): t = min(max(t, 0), 1); return 1 - (1 - t) ** 3
def ease_in_out(t): t = min(max(t, 0), 1); return 3 * t * t - 2 * t * t * t
def ease_back(t):
    t = min(max(t, 0), 1); c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def box_blur(a, r):
    """Cheap separable blur on a float array (no scipy)."""
    k = 2 * r + 1
    for ax in (0, 1):
        c = np.cumsum(np.pad(a, [(r + 1, r) if i == ax else (0, 0) for i in range(a.ndim)], mode="edge"), axis=ax)
        a = (np.take(c, range(k, c.shape[ax]), axis=ax) - np.take(c, range(0, c.shape[ax] - k), axis=ax)) / k
    return a


def paper_texture(w, h, base=PAPER, vignette=0.22):
    n1 = box_blur(np.random.randn(h, w), 2) * 6
    n2 = box_blur(np.random.randn(h // 8 + 1, w // 8 + 1), 2)
    n2 = np.array(Image.fromarray(((n2 - n2.min()) / (np.ptp(n2) + 1e-6) * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), float)
    n2 = (n2 / 255 - 0.5) * 18
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    vig = 1 - vignette * np.clip(d - 0.55, 0, 1) ** 1.6
    img = np.stack([(base[i] + n1 + n2) * vig for i in range(3)], -1)
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


def text_w(d, s, f): b = d.textbbox((0, 0), s, font=f); return b[2] - b[0]


def center_text(d, y, s, f, fill=INK, cx=None, width=None):
    cx = cx if cx is not None else (width or d.im.size[0]) / 2
    b = d.textbbox((0, 0), s, font=f)
    d.text((cx - (b[2] - b[0]) / 2 - b[0], y), s, font=f, fill=fill)
    return b[3] - b[1]


def wrap(d, s, f, maxw):
    lines, cur = [], ""
    for w_ in s.split():
        t = (cur + " " + w_).strip()
        if text_w(d, t, f) <= maxw: cur = t
        else: lines.append(cur); cur = w_
    if cur: lines.append(cur)
    return lines


def fit_font(d, s, maker, maxw, start):
    size = start
    while size > 10 and text_w(d, s, maker(size)) > maxw: size -= 2
    return maker(size)


def rule(d, x0, x1, y, t=2, fill=INK):
    d.rectangle([x0, y, x1, y + t - 1], fill=fill)


def double_rule(d, x0, x1, y, k=1.0):
    rule(d, x0, x1, y, int(5 * k)); rule(d, x0, x1, y + int(9 * k), int(2 * k))


def greek(d, x, y, w, h, k, lh=13, seed=0):
    """Simulated body copy: grey bars of varying length."""
    rnd = random.Random(seed)
    yy = y
    while yy + lh * k <= y + h:
        para_end = rnd.random() < 0.12
        ww = w * (rnd.uniform(0.35, 0.8) if para_end else rnd.uniform(0.93, 1.0))
        d.rectangle([x, yy, x + ww, yy + 5 * k], fill=(150, 140, 122))
        yy += lh * k * (1.9 if para_end else 1)


def halftone_stage(w, h):
    """Halftone illustration: spotlight on a vintage microphone with music notes."""
    g = Image.new("L", (w, h), 40)
    yy, xx = np.mgrid[0:h, 0:w]
    # spotlight cone
    cone = np.clip(1 - np.abs(xx - w * 0.5) / (40 + (yy / h) * w * 0.42), 0, 1) ** 0.7
    floor = np.exp(-(((xx - w * 0.5) / (w * 0.32)) ** 2 + ((yy - h * 0.9) / (h * 0.07)) ** 2))
    arr = 40 + 190 * np.clip(cone * 0.85 + floor * 0.6, 0, 1)
    g = Image.fromarray(arr.astype(np.uint8))
    d = ImageDraw.Draw(g)
    cx = w * 0.5
    # mic stand
    d.rectangle([cx - w * 0.008, h * 0.38, cx + w * 0.008, h * 0.88], fill=15)
    d.polygon([(cx, h * 0.84), (cx - w * 0.12, h * 0.92), (cx - w * 0.1, h * 0.93), (cx, h * 0.87),
               (cx + w * 0.1, h * 0.93), (cx + w * 0.12, h * 0.92)], fill=15)
    # mic head
    r = w * 0.06
    d.rounded_rectangle([cx - r, h * 0.2, cx + r, h * 0.2 + r * 3.2], radius=r, fill=20)
    for i in range(6):
        y0 = h * 0.2 + r * 0.6 + i * r * 0.4
        d.line([cx - r * 0.75, y0, cx + r * 0.75, y0], fill=90, width=max(2, int(r * 0.08)))
    d.rectangle([cx - r * 1.15, h * 0.2 + r * 1.3, cx - r * 0.95, h * 0.2 + r * 2.1], fill=20)
    d.rectangle([cx + r * 0.95, h * 0.2 + r * 1.3, cx + r * 1.15, h * 0.2 + r * 2.1], fill=20)
    # notes
    g = g.filter(ImageFilter.GaussianBlur(1.2))
    # halftone
    cell = max(6, int(w / 70))
    out = Image.new("L", (w, h), 245)
    od = ImageDraw.Draw(out)
    a = np.array(g, float)
    for y in range(0, h, cell):
        for x in range(0, w, cell):
            v = a[min(y + cell // 2, h - 1), min(x + cell // 2, w - 1)]
            rad = (1 - v / 255) ** 0.8 * cell * 0.72
            if rad > 0.4:
                c = (x + cell / 2, y + cell / 2)
                od.ellipse([c[0] - rad, c[1] - rad, c[0] + rad, c[1] + rad], fill=25)
    return out.convert("RGB")


# ---------- front page ----------
def build_front_page():
    pw, ph = int(W * S), int(H * S)
    k = S
    img = paper_texture(pw, ph)
    d = ImageDraw.Draw(img)
    m = 60 * k
    y = 70 * k
    rule(d, m, pw - m, y, int(2 * k)); y += 12 * k
    sm = OSB(22 * k)
    d.text((m, y), "VOL. CXII · No. 281", font=sm, fill=INK)
    center_text(d, y, "THURSDAY, OCTOBER 8, 2026", sm, width=pw)
    t = "SPECIAL EDITION"; d.text((pw - m - text_w(d, t, sm), y), t, font=sm, fill=INK)
    y += 40 * k
    rule(d, m, pw - m, y, int(2 * k)); y += 18 * k
    center_text(d, y, "The Folk Chronicle", GOTH(120 * k), width=pw); y += 170 * k
    center_text(d, y, "—  CELEBRATING THE VOICES OF GUJARAT  —", OSI(25 * k), width=pw); y += 44 * k
    double_rule(d, m, pw - m, y, k); y += 34 * k
    center_text(d, y, "PRESS COVERAGE REPORT", OSB(28 * k), fill=RED, width=pw); y += 52 * k
    hf = BLACK(98 * k)
    for line in wrap(d, HEADLINE.upper(), hf, pw - 2 * m):
        center_text(d, y, line, hf, width=pw); y += 112 * k
    y += 30 * k
    sf = OSI(44 * k)
    for line in wrap(d, SUBHEAD, sf, pw - 2.6 * m):
        center_text(d, y, line, sf, width=pw); y += 56 * k
    y += 18 * k
    rule(d, m, pw - m, y, int(2 * k)); y += 28 * k
    headline_box = (0, 330 * k, pw, y)

    # photo
    ph_h = 360 * k
    photo = halftone_stage(int(pw - 2 * m), int(ph_h))
    photo_y = y
    img.paste(photo, (int(m), int(y)))
    d.rectangle([m, y, pw - m, y + ph_h], outline=INK, width=int(3 * k))
    y += ph_h + 12 * k
    d.text((m, y), "The young voice of Gujarati folk music, now in the national spotlight.", font=OSI(24 * k), fill=GREY)
    y += 50 * k
    rule(d, m, pw - m, y, int(2 * k)); y += 26 * k

    # three columns
    gap = 28 * k
    cw = (pw - 2 * m - 2 * gap) / 3
    cols = [m + i * (cw + gap) for i in range(3)]
    for i in (1, 2):
        x = cols[i] - gap / 2
        d.line([x, y, x, ph - 160 * k], fill=(160, 150, 130), width=max(1, int(k)))
    body = OSR(23 * k)
    lh = 31 * k
    # col 1: lead paragraph
    lead = (f"The story of 20-year-old Shivam Barot has travelled far beyond Gujarat. "
            f"His rise as the youngest sensation of Gujarati folk music was carried by "
            f"{TOTAL_PUBS} publications with a combined potential audience of more than "
            f"{CRORE} crore readers.")
    yy = y
    d.text((cols[0], yy), "AHMEDABAD —", font=OSB(23 * k), fill=INK); yy += lh
    for line in wrap(d, lead, body, cw):
        d.text((cols[0], yy), line, font=body, fill=INK); yy += lh
    greek(d, cols[0], yy + 10 * k, cw, ph - 170 * k - yy, k, seed=1)
    # col 2: top outlets list
    yy = y
    d.text((cols[1], yy), "WHERE IT RAN", font=OSB(23 * k), fill=RED); yy += lh + 4 * k
    for name, aud, _ in TOP[:8]:
        d.text((cols[1], yy), "■ " + name, font=OSB(22 * k), fill=INK)
        t = fmt_num(aud); d.text((cols[1] + cw - text_w(d, t, OSR(22 * k)), yy), t, font=OSR(22 * k), fill=GREY)
        yy += lh
    yy += 8 * k
    d.text((cols[1], yy), f"…and {TOTAL_PUBS - 8} more", font=OSI(22 * k), fill=GREY); yy += lh + 6 * k
    greek(d, cols[1], yy, cw, ph - 170 * k - yy, k, seed=2)
    # col 3: reach box
    yy = y
    bx = [cols[2], yy, cols[2] + cw, yy + 300 * k]
    d.rectangle(bx, fill=INK)
    center_text(d, yy + 22 * k, "POTENTIAL REACH", OSB(22 * k), fill=PAPER, cx=cols[2] + cw / 2)
    center_text(d, yy + 64 * k, f"{CRORE} Cr+", BLACK(64 * k), fill=PAPER, cx=cols[2] + cw / 2)
    rule(d, cols[2] + 30 * k, cols[2] + cw - 30 * k, yy + 170 * k, int(2 * k), fill=PAPER)
    center_text(d, yy + 190 * k, f"{TOTAL_PUBS}", BLACK(54 * k), fill=PAPER, cx=cols[2] + cw / 2)
    center_text(d, yy + 258 * k, "PUBLICATIONS", OSB(20 * k), fill=PAPER, cx=cols[2] + cw / 2)
    greek(d, cols[2], yy + 330 * k, cw, ph - 170 * k - yy - 330 * k, k, seed=3)
    # footer
    double_rule(d, m, pw - m, ph - 140 * k, k)
    center_text(d, ph - 110 * k, "THE FOLK CHRONICLE  ·  COVERAGE EDITION  ·  PAGE ONE", OSB(22 * k), width=pw)
    return img, headline_box, photo_y


# ---------- clipping card ----------
def torn_mask(w, h, j=10, seed=0):
    rnd = random.Random(seed)
    pts = []
    step = 18
    for x in range(0, w, step): pts.append((x, rnd.uniform(0, j)))
    for y in range(0, h, step): pts.append((w - rnd.uniform(0, j), y))
    for x in range(w, 0, -step): pts.append((x, h - rnd.uniform(0, j)))
    for y in range(h, 0, -step): pts.append((rnd.uniform(0, j), y))
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).polygon(pts, fill=255)
    return m


def build_card(i, name, aud, dom):
    cw, ch = 900, 760
    tex = paper_texture(cw, ch, base=(247, 240, 222), vignette=0.35)
    d = ImageDraw.Draw(tex)
    pad = 56
    y = 52
    d.text((pad, y), f"No. {i+1:02d}", font=OSB(30), fill=RED)
    t = "FEATURED COVERAGE"; d.text((cw - pad - text_w(d, t, OSB(26)), y + 3), t, font=OSB(26), fill=GREY)
    y += 56
    double_rule(d, pad, cw - pad, y); y += 36
    nf = fit_font(d, name, BLACK, cw - 2 * pad, 112)
    b = d.textbbox((0, 0), name, font=nf)
    center_text(d, y - b[1] + (130 - (b[3] - b[1])) / 2, name, nf, width=cw)
    y += 150
    rule(d, pad, cw - pad, y, 2); y += 30
    center_text(d, y, "POTENTIAL AUDIENCE", OSB(28), fill=GREY, width=cw); y += 46
    center_text(d, y, fmt_num(aud), BLACK(118), fill=RED, width=cw); y += 168
    rule(d, pad, cw - pad, y, 2); y += 24
    hf = OSI(31)
    for line in wrap(d, f"“{HEADLINE}: {SUBHEAD}”", hf, cw - 2 * pad)[:3]:
        center_text(d, y, line, hf, width=cw); y += 40
    y += 14
    center_text(d, y, dom, OSB(26), fill=GREY, width=cw)
    card = tex.convert("RGBA")
    card.putalpha(torn_mask(cw, ch, seed=i))
    return card


def stamp(text, size=64, color=RED, filled=False):
    f = OSB(size)
    d0 = ImageDraw.Draw(Image.new("L", (1, 1)))
    tw = text_w(d0, text, f)
    w, h = tw + 70, size + 60
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if filled:
        d.rounded_rectangle([4, 4, w - 5, h - 5], radius=14, fill=color + (255,))
        d.rounded_rectangle([14, 14, w - 15, h - 15], radius=10, outline=PAPER + (255,), width=3)
        d.text((35, 22), text, font=f, fill=PAPER + (255,))
    else:
        d.rounded_rectangle([4, 4, w - 5, h - 5], radius=14, outline=color + (255,), width=7)
        d.text((35, 22), text, font=f, fill=color + (255,))
    # ink wear
    a = np.array(im)
    wear = (np.random.rand(h, w) > 0.18)
    a[..., 3] = (a[..., 3] * wear * 0.88).astype(np.uint8)
    return Image.fromarray(a)


def shadowed(card, blur=18, off=(14, 22), alpha=110):
    pad = blur * 3
    w, h = card.size
    out = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("RGBA", out.size, (0, 0, 0, 0))
    sa = card.split()[3].point(lambda v: v * alpha // 255)
    sh.paste((20, 15, 10, 255), (pad + off[0], pad + off[1]), sa)
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    out = Image.alpha_composite(out, sh)
    out.alpha_composite(card, (pad, pad))
    return out


def place(base, im, cx, cy, scale=1.0, angle=0.0, alpha=1.0):
    if scale != 1.0:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BILINEAR)
    if angle:
        im = im.rotate(angle, resample=Image.BICUBIC, expand=True)
    if alpha < 1:
        a = im.split()[3].point(lambda v: int(v * alpha)); im = im.copy(); im.putalpha(a)
    base.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


# ---------- build assets ----------
print("building assets...", flush=True)
front_big, hl_box, PHOTO_Y = build_front_page()
front = front_big.resize((W, H), Image.LANCZOS)
desk = Image.new("RGB", (W, H), (26, 22, 19))
yy, xx = np.mgrid[0:H, 0:W]
dv = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H / 2) / H) ** 2)
desk_arr = np.stack([np.clip(c * (1.25 - dv * 1.1) + np.random.randn(H, W) * 3, 0, 255) for c in (52, 42, 34)], -1)
desk = Image.fromarray(desk_arr.astype(np.uint8)).convert("RGBA")

cards = [shadowed(build_card(i, *t)) for i, t in enumerate(TOP)]
featured_stamp = stamp("FEATURED", 58)
breaking_stamp = stamp("BREAKING NEWS", 64, filled=True)

# clippings scene backdrop: darkened, blurred front page + header banner
clip_bg = front.filter(ImageFilter.GaussianBlur(6)).convert("RGBA")
clip_bg = Image.alpha_composite(clip_bg, Image.new("RGBA", (W, H), (20, 15, 10, 170)))
hdr = paper_texture(W, 250, vignette=0.1).convert("RGBA")
hd = ImageDraw.Draw(hdr)
center_text(hd, 26, "As Seen In", GOTH(118), width=W)
double_rule(hd, 60, W - 60, 196)
clip_bg.alpha_composite(hdr, (0, 0))
foot = Image.new("RGBA", (W, 170), (0, 0, 0, 0))
fd = ImageDraw.Draw(foot)
center_text(fd, 40, f"{TOTAL_PUBS} PUBLICATIONS  ·  {CRORE} CRORE+ POTENTIAL REACH", OSB(34), fill=PAPER, width=W)
center_text(fd, 96, SUBHEAD, OSI(30), fill=(200, 188, 165), width=W)
clip_bg.alpha_composite(foot, (0, H - 200))

# stats page
stats_bg = paper_texture(W, H).convert("RGBA")
sd = ImageDraw.Draw(stats_bg)
center_text(sd, 120, "The Folk Chronicle", GOTH(100), width=W)
double_rule(sd, 60, W - 60, 270)
center_text(sd, 310, "BY THE NUMBERS", OSB(48), fill=RED, width=W)
rule(sd, 300, W - 300, 380, 2)

# outro page
outro = paper_texture(W, H).convert("RGBA")
od = ImageDraw.Draw(outro)
center_text(od, 110, "The Folk Chronicle", GOTH(100), width=W)
double_rule(od, 60, W - 60, 260)
center_text(od, 300, "AS FEATURED ON", OSB(52), fill=RED, width=W)
gy = 400
for idx, (name, _, _) in enumerate(TOP):
    col, row = idx % 2, idx // 2
    cx = W / 4 + col * W / 2
    f = fit_font(od, name, BOLDP, W / 2 - 80, 50)
    center_text(od, gy + row * 112, name, f, cx=cx)
    if row < 5: rule(od, cx - 160, cx + 160, gy + row * 112 + 84, 1, fill=(170, 158, 135))
od.line([W / 2, gy, W / 2, gy + 6 * 112 - 30], fill=(170, 158, 135), width=2)
center_text(od, gy + 6 * 112 + 10, f"+ {TOTAL_PUBS - 12} more publications", OSI(40), fill=GREY, width=W)
double_rule(od, 60, W - 60, 1220)
center_text(od, 1270, "SHIVAM BAROT", BLACK(118), width=W)
center_text(od, 1420, "The Young Voice of Gujarati Folk", OSI(54), width=W)
center_text(od, 1530, f"{CRORE} Crore+ potential readers  ·  {TOTAL_PUBS} publications", OSB(32), fill=RED, width=W)
double_rule(od, 60, W - 60, 1640)
center_text(od, 1690, "OCTOBER 2026  ·  COVERAGE EDITION", OSB(28), fill=GREY, width=W)

# ---------- timeline ----------
T_SPIN, T_FRONT = 2.4, 5.0
CARD_T = 1.35
T_CLIPS = len(cards) * CARD_T + 1.0
T_STATS, T_OUTRO = 5.0, 6.0
T_WIPE = 0.5
t0_front = T_SPIN
t0_clips = t0_front + T_FRONT
t0_stats = t0_clips + T_CLIPS
t0_outro = t0_stats + T_STATS
TOTAL = t0_outro + T_OUTRO
N = int(TOTAL * FPS)
print(f"duration {TOTAL:.1f}s, {N} frames", flush=True)

card_pos = []
rnd = random.Random(3)
for i in range(len(cards)):
    card_pos.append((W / 2 + rnd.uniform(-45, 45), 1010 + rnd.uniform(-40, 40), rnd.uniform(-7, 7) * (1 if i % 2 else -1)))

pile_cache = {}
def pile(n):
    if n not in pile_cache:
        base = pile(n - 1).copy() if n > 0 else clip_bg.copy()
        if n > 0:
            cx, cy, a = card_pos[n - 1]
            place(base, cards[n - 1], cx, cy, 0.98, a)
            place(base, featured_stamp, cx + 230, cy + 300, 0.85, a - 10, 0.95)
        pile_cache[n] = base
    return pile_cache[n]


def front_frame(t):
    z = 1.0 + 0.09 * ease_in_out(t / T_FRONT)
    # zoom toward headline region
    fx, fy = W * S / 2, (hl_box[1] + hl_box[3]) / 2
    cw_, ch_ = W * S / z, H * S / z
    x0 = min(max(fx - cw_ / 2, 0), W * S - cw_)
    y0 = min(max(fy - ch_ / 2 - (1 - 1 / z) * 0, 0), H * S - ch_)
    y0 = y0 * ease_in_out(t / T_FRONT)  # start from full page, drift to headline
    fr = front_big.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + cw_, y0 + ch_)).convert("RGBA")
    st = (t - 1.2) / 0.35
    if st > 0:
        sc = 1 + 1.4 * (1 - ease_out(st))
        sx_ = (60 * S + 230 * S - x0) * z / S
        sy_ = (PHOTO_Y + 40 * S - y0) * z / S
        place(fr, breaking_stamp, sx_, sy_, sc * 0.8, 7, min(1, st * 1.5) * 0.95)
    return fr


def spin_frame(t):
    p = ease_out(t / T_SPIN)
    sc = 0.04 + 0.96 * p
    ang = (1 - p) * 900
    base = desk.copy()
    small = front.resize((max(1, int(W * sc)), max(1, int(H * sc))), Image.BILINEAR).convert("RGBA")
    if sc < 0.995:
        small = shadowed(small, blur=int(10 + 20 * sc), off=(int(10 * sc), int(18 * sc)), alpha=150)
    place(base, small, W / 2, H / 2, 1.0, ang)
    return base


def clips_frame(t):
    i = min(int(t / CARD_T), len(cards))
    if i >= len(cards):
        return pile(len(cards)).copy()
    lt = (t - i * CARD_T) / CARD_T
    fr = pile(i).copy()
    cx, cy, a = card_pos[i]
    p = ease_out(lt / 0.45)
    sx = cx + (1 - p) * (W * 1.1 if i % 2 == 0 else -W * 1.1)
    sy = cy + (1 - p) * 260
    place(fr, cards[i], sx, sy, 0.98 + 0.25 * (1 - p), a + (1 - p) * (35 if i % 2 == 0 else -35))
    st = (lt - 0.42) / 0.18
    if st > 0:
        sc = 1 + 1.6 * (1 - ease_out(st))
        place(fr, featured_stamp, cx + 230, cy + 300, 0.85 * sc, a - 10, min(1, st * 2) * 0.95)
    return fr


def stats_frame(t):
    fr = stats_bg.copy()
    d = ImageDraw.Draw(fr)
    blocks = [
        (f"{int(TOTAL_PUBS * ease_out((t - 0.3) / 1.6))}", "PUBLICATIONS CARRIED THE STORY", 0.3),
        (f"{TOTAL_REACH / 1e7 * ease_out((t - 0.9) / 1.8):.1f} Cr+", "COMBINED POTENTIAL AUDIENCE", 0.9),
        (f"{fmt_num(int(TOP[0][1] * ease_out((t - 1.5) / 1.6)))}", f"TOP REACH · {TOP[0][0].upper()}", 1.5),
    ]
    y = 470
    for big, lab, st in blocks:
        p = ease_out((t - st) / 0.5)
        if p <= 0: y += 430; continue
        layer = Image.new("RGBA", (W, 400), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        center_text(ld, 10, big, BLACK(170), fill=RED, width=W)
        center_text(ld, 240, lab, OSB(40), fill=INK, width=W)
        rule(ld, 340, W - 340, 330, 3)
        a = layer.split()[3].point(lambda v: int(v * p)); layer.putalpha(a)
        fr.alpha_composite(layer, (0, int(y + (1 - p) * 60)))
        y += 430
    return fr


def outro_frame(t):
    z = 1.04 - 0.04 * ease_out(t / 2.0)
    fr = outro.resize((int(W * z), int(H * z)), Image.BILINEAR).crop(((int(W * z) - W) // 2, (int(H * z) - H) // 2, (int(W * z) - W) // 2 + W, (int(H * z) - H) // 2 + H))
    fade = max(0, (t - (T_OUTRO - 0.8)) / 0.8)
    if fade > 0:
        fr = Image.blend(fr, Image.new("RGBA", (W, H), (10, 8, 6, 255)), min(1, fade))
    return fr


SCENES = [(0, T_SPIN, spin_frame), (t0_front, T_FRONT, front_frame), (t0_clips, T_CLIPS, clips_frame),
          (t0_stats, T_STATS, stats_frame), (t0_outro, T_OUTRO, outro_frame)]


def frame_at(t):
    for idx, (st, du, fn) in enumerate(SCENES):
        if t < st + du or idx == len(SCENES) - 1:
            cur = fn(t - st).convert("RGBA")
            # slide-in wipe from previous scene (paper sheet sliding over)
            if idx >= 2 and t - st < T_WIPE:
                prev = SCENES[idx - 1][2](SCENES[idx - 1][1] - 1e-3).convert("RGBA")
                p = ease_in_out((t - st) / T_WIPE)
                x = int(W * (1 - p))
                base = prev.copy()
                base = Image.alpha_composite(base, Image.new("RGBA", (W, H), (0, 0, 0, int(120 * p))))
                sh = Image.new("RGBA", (60, H), (0, 0, 0, 0))
                sh_arr = np.zeros((H, 60, 4), np.uint8); sh_arr[..., 3] = np.linspace(0, 140, 60)[None, :].astype(np.uint8)
                base.alpha_composite(Image.fromarray(sh_arr), (max(0, x - 60), 0))
                base.paste(cur.crop((0, 0, W - x, H)), (x, 0))
                return base
            return cur


if len(sys.argv) > 4:  # preview: save stills at given times and exit
    for ts in sys.argv[4].split(","):
        frame_at(float(ts)).convert("RGB").save(f"{OUT}_{ts}.png")
    sys.exit(0)

# ---------- audio (synthesized: whoosh, stamp thuds, soft pad) ----------
SR = 44100
audio = np.zeros(int(TOTAL * SR) + SR)

def add(sig, at, gain=1.0):
    i = int(at * SR); audio[i:i + len(sig)] += sig[:len(audio) - i] * gain

def whoosh(dur=0.5, lo=300, hi=3000):
    n = int(dur * SR); x = np.random.randn(n)
    env = np.sin(np.linspace(0, math.pi, n)) ** 2
    # moving one-pole lowpass for a sweep
    out = np.zeros(n); y = 0
    cut = np.linspace(lo, hi, n)
    al = 1 - np.exp(-2 * math.pi * cut / SR)
    for k_ in range(n): y += al[k_] * (x[k_] - y); out[k_] = y
    return out * env * 0.5

def thud(dur=0.25):
    n = int(dur * SR); tt = np.arange(n) / SR
    s = np.sin(2 * math.pi * (90 * tt - 60 * tt * tt)) * np.exp(-tt * 22)
    s += box_blur(np.random.randn(n)[None, :], 3)[0] * np.exp(-tt * 60) * 0.6
    return s * 0.9

def pad(dur):
    n = int(dur * SR); tt = np.arange(n) / SR
    s = np.zeros(n)
    for f in (110, 164.81, 220, 277.18, 329.63):
        s += np.sin(2 * math.pi * f * tt + np.sin(2 * math.pi * 0.2 * tt) * 0.5)
    env = np.minimum(1, tt / 2.0) * np.minimum(1, (dur - tt) / 2.0)
    return s / 5 * env * 0.12

add(pad(TOTAL), 0)
add(whoosh(T_SPIN * 0.9, 200, 4000), 0.05, 0.9)
add(thud(), T_SPIN - 0.05, 1.0)
add(thud(), t0_front + 1.2 + 0.3, 0.9)
for i in range(len(cards)):
    add(whoosh(0.4, 600, 5000), t0_clips + i * CARD_T, 0.55)
    add(thud(0.2), t0_clips + i * CARD_T + 0.42 + 0.16, 0.7)
for st in (t0_stats, t0_outro):
    add(whoosh(0.45, 400, 4000), st, 0.6)
audio = audio / (np.abs(audio).max() + 1e-6) * 0.85
wav = OUT.rsplit(".", 1)[0] + ".wav"
with wave.open(wav, "w") as wf:
    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR)
    wf.writeframes((audio * 32767).astype(np.int16).tobytes())

# ---------- render ----------
ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                       "-r", str(FPS), "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                       "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", OUT],
                      stdin=subprocess.PIPE)
for n in range(N):
    fr = frame_at(n / FPS).convert("RGB")
    ff.stdin.write(fr.tobytes())
    if n % 90 == 0: print(f"frame {n}/{N}", flush=True)
ff.stdin.close(); ff.wait()
print("done", OUT)
