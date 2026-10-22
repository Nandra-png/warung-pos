"""Verifikasi tema + regresi: hitung warna terpakai dari CSS, cek tema default.

1. Tema default harus LIGHT walau OS headless bilang dark.
2. Semua token warna brief harus ada persis di blok :root light.
3. Tidak boleh ada emoji, em-dash, atau markup Jinja bocor di HTML ter-render.
4. Grafik tren harus selalu 7 batang.
"""
import os
import re
import subprocess
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # skrip ini ada di tools/, akar repo satu level di atas
sys.path.insert(0, BASE)
import app as appmod  # noqa: E402
appmod.init_db()  # clone baru belum punya warung_pos.db (di-gitignore)

appmod.app.config["TESTING"] = True
c = appmod.app.test_client()
c.post("/login", data={"username": "admin", "password": "admin123"})

hasil = []


def cek(nama, ok, info=""):
    hasil.append((nama, bool(ok), info))


# ---------- 1. token warna brief ada di :root ----------
css = open(os.path.join(BASE, "static", "css", "style.css"), encoding="utf-8").read()
root = css.split(":root {", 1)[1].split("}", 1)[0]
WAJIB = {
    "--bg-app": "#F5F6FA",
    "--bg-card": "#FFFFFF",
    "--accent": "#EF4444",
    "--accent-soft": "#FEECEC",
    "--text-primary": "#111827",
    "--text-secondary": "#6B7280",
    "--text-muted": "#9CA3AF",
    "--border": "#EEF0F4",
    "--success": "#16A34A",
    "--warning": "#F59E0B",
}
for tok, warna in WAJIB.items():
    pola = re.compile(re.escape(tok) + r"\s*:\s*" + re.escape(warna), re.I)
    cek(f"token {tok} = {warna}", pola.search(root), "")

# dark theme pakai palet alternatif sesuai brief
dark = css.split('[data-theme="dark"] {', 1)[1].split("}", 1)[0]
for tok, warna in {"--bg-app": "#0F1115", "--bg-card": "#181B22", "--border": "#262A33"}.items():
    cek(f"dark {tok} = {warna}",
        re.search(re.escape(tok) + r"\s*:\s*" + re.escape(warna), dark, re.I), "")

# ---------- 2. tema default LIGHT walau OS dark ----------
# headless Edge melaporkan prefers-color-scheme dark; render tanpa localStorage harus tetap light
OUT = os.path.join(os.environ["LOCALAPPDATA"], "Temp", "wp_theme")
os.makedirs(OUT, exist_ok=True)
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

r = c.get("/kasir")
html = r.data.decode("utf-8", "replace")
html = html.replace('href="/static/', f'href="file:///{BASE.replace(chr(92), "/")}/static/')
ph = os.path.join(OUT, "cek-tema.html")
open(ph, "w", encoding="utf-8").write(
    html.replace("</body>",
                 "<script>window.addEventListener('load',function(){setTimeout(function(){"
                 "var o=document.createElement('div');o.id='__tema';"
                 "o.textContent=document.documentElement.getAttribute('data-theme')+'|'+"
                 "getComputedStyle(document.body).backgroundColor+'|'+"
                 "getComputedStyle(document.querySelector('.sidebar')).backgroundColor;"
                 "document.body.appendChild(o);},600);});</script></body>"))

dump = subprocess.run([
    EDGE, "--headless=new", "--disable-gpu", "--no-first-run",
    "--no-default-browser-check", "--allow-file-access-from-files",
    "--virtual-time-budget=2500", "--dump-dom",
    f"file:///{ph.replace(os.sep, '/')}",
], capture_output=True, text=True, timeout=120).stdout or ""

m = re.search(r'id="__tema">([^<]*)<', dump)
info = m.group(1) if m else "tidak-terbaca"
cek("tema default = light (meski OS headless dark)",
    info.startswith("light|"), info)
cek("bg-app terpakai = rgb(245, 246, 250)", "rgb(245, 246, 250)" in info, info)
cek("sidebar terpakai = rgb(255, 255, 255)", "rgb(255, 255, 255)" in info, info)

# ---------- 3. halaman bersih ----------
BERSIH = ["/", "/kasir", "/barang", "/riwayat", "/laporan", "/transaksi/1"]
EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\u2190-\u21FF\u2B00-\u2BFF]")
for url in BERSIH:
    h = c.get(url).data.decode("utf-8", "replace")
    cek(f"{url} tanpa emoji", not EMOJI.search(h), "")
    cek(f"{url} tanpa em-dash", "\u2014" not in h and "\u2013" not in h, "")
    cek(f"{url} tanpa Jinja bocor", "{{" not in h and "{%" not in h, "")
    cek(f"{url} tanpa teks None", ">None<" not in h and "undefined<" not in h, "")

# ---------- 4. grafik tren selalu 7 batang ----------
for url in ["/", "/laporan"]:
    h = c.get(url).data.decode("utf-8", "replace")
    n = h.count('class="bar-wrap"') + h.count('class="bar-wrap ')
    cek(f"{url} grafik 7 batang", n == 7, f"batang={n}")

# ---------- 5. 7 hari terakhir selalu berurutan & hari ini terakhir ----------
from app import tren_7_hari  # noqa: E402
with appmod.app.app_context():
    seri = tren_7_hari(appmod.get_db())
cek("tren_7_hari panjang 7", len(seri) == 7, str(len(seri)))
cek("tren_7_hari urut naik", all(seri[i]["tgl"] < seri[i + 1]["tgl"] for i in range(6)), "")
from datetime import date as _d  # noqa: E402
cek("tren_7_hari berakhir hari ini", seri[-1]["tgl"] == _d.today().isoformat(), seri[-1]["tgl"])

# ---------- laporan ----------
print("\n=== VERIFIKASI TEMA & REGRESI ===")
gagal = 0
for nama, ok, info in hasil:
    if not ok:
        gagal += 1
    print(f"  [{'OK ' if ok else 'GAGAL'}] {nama}" + (f"  -> {info}" if info and not ok else ""))
print(f"\n{'SEMUA LULUS' if gagal == 0 else str(gagal) + ' GAGAL'}")
