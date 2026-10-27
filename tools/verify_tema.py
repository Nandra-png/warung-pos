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

# ---------- 2b. animasi ganti tema ----------
# Dua probe terpisah, sengaja dipisah supaya tidak ada balapan dengan jam:
#   A. animasi TERPASANG?  -> baca getAnimations() tepat setelah diklik
#   B. LOGIKA ganti tema   -> paksa reduced-motion supaya tidak ada animasi,
#      jadi hasilnya deterministik dan bisa diuji kapan pun.
CHROME = next((p for p in [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
] if os.path.exists(p)), None)


def render(nama, probe, budget=6000, ekstra=()):
    """Render /kasir ke berkas lokal, suntik probe, lalu kembalikan DOM hasil dump."""
    r = c.get("/kasir")
    h = r.data.decode("utf-8", "replace")
    h = h.replace('href="/static/', f'href="file:///{BASE.replace(chr(92), "/")}/static/')
    # app.js harus ikut dimuat, kalau tidak handler klik tema tidak pernah terpasang
    h = h.replace('src="/static/', f'src="file:///{BASE.replace(chr(92), "/")}/static/')
    h = re.sub(r'href="(/[^"]*)"', 'href="#"', h)
    ph = os.path.join(OUT, nama)
    open(ph, "w", encoding="utf-8").write(h.replace("</body>", probe + "</body>"))
    args = [CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
            "--no-default-browser-check", "--allow-file-access-from-files",
            f"--virtual-time-budget={budget}", "--dump-dom", *ekstra,
            f"file:///{ph.replace(os.sep, '/')}"]
    return subprocess.run(args, capture_output=True, text=True, timeout=180).stdout or ""


def ambil(dump, tanda="__anim"):
    m = re.search(r'id="' + tanda + r'">(.*?)</div>', dump, re.S)
    if not m:
        return {}
    try:
        import json as _json
        return _json.loads(m.group(1).replace("&quot;", '"'))
    except Exception as exc:
        return {"galat": "parse: " + str(exc)}


# --- A. animasi benar-benar terpasang ---
PROBE_A = r"""
<script>
window.__anim = {};
function tulis() {
  let o = document.getElementById('__anim');
  if (!o) { o = document.createElement('div'); o.id = '__anim'; document.body.appendChild(o); }
  o.textContent = JSON.stringify(window.__anim);
}
window.addEventListener('load', function () {
  const tombol = [...document.querySelectorAll('[data-theme-cycle]')]
    .find((b) => b.getBoundingClientRect().width > 0);
  if (!tombol) { window.__anim.galat = 'tombol tema tidak ada'; tulis(); return; }
  const tirai = document.getElementById('themeWipe');
  window.__anim.warnaTirai = getComputedStyle(tirai).backgroundColor;
  window.__anim.varX_sebelum =
    getComputedStyle(document.documentElement).getPropertyValue('--x').trim() || '(kosong)';
  window.__anim.animasi_sebelum = tirai.getAnimations().length;
  tombol.click();
  window.__anim.varX_sesudah =
    getComputedStyle(document.documentElement).getPropertyValue('--x').trim() || '(kosong)';
  window.__anim.ikonLangsungGelap = tombol.classList.contains('is-dark');
  window.__anim.temaSaatKlik = document.documentElement.getAttribute('data-theme');
  tulis();
  // .on dipasang di requestAnimationFrame, jadi animasi baru ada di frame
  // berikutnya. rAF selalu dijalankan, beda dengan timer yang bisa terlewat.
  requestAnimationFrame(function () {
    window.__anim.animasi = tirai.getAnimations().map((a) => ({
      nama: a.animationName,
      durasi: a.effect && a.effect.getTiming ? a.effect.getTiming().duration : null,
      jalan: a.playState,
    }));
    tulis();
  });
});
</script>
"""
A = ambil(render("anim-a.html", PROBE_A))

if not A or A.get("galat"):
    cek("animasi: probe A terbaca", False, str(A.get("galat") or "kosong"))
else:
    cek("animasi: titik asal tirai diambil dari tombol (--x terisi)",
        A.get("varX_sesudah") not in (None, "", "(kosong)"), f"--x={A.get('varX_sesudah')}")
    cek("animasi: --x kosong sebelum diklik", A.get("varX_sebelum") == "(kosong)",
        str(A.get("varX_sebelum")))
    cek("animasi: tirai berwarna latar tema tujuan",
        "rgb(15, 17, 21)" in (A.get("warnaTirai") or ""), str(A.get("warnaTirai")))
    cek("animasi: tirai belum beranimasi sebelum diklik",
        A.get("animasi_sebelum") == 0, str(A.get("animasi_sebelum")))
    animasi = A.get("animasi") or []
    cek("animasi: tirai langsung beranimasi setelah diklik",
        any(a.get("nama") == "sebar-tirai-masuk" and a.get("jalan") == "running" for a in animasi),
        str(animasi))
    cek("animasi: durasi tirai 560ms",
        any(a.get("nama") == "sebar-tirai-masuk" and a.get("durasi") == 560 for a in animasi),
        str(animasi))
    # urutan yang diminta: ikon bergerak SEBELUM palet ditukar
    cek("animasi: ikon sudah jadi bulan saat palet masih terang",
        A.get("ikonLangsungGelap") is True and A.get("temaSaatKlik") == "light",
        f"ikonGelap={A.get('ikonLangsungGelap')} tema={A.get('temaSaatKlik')}")

# --- B. logika ganti tema, tanpa animasi supaya deterministik ---
PROBE_B = r"""
<script>
window.__anim = {};
window.addEventListener('load', function () {
  // transisi dimatikan supaya getComputedStyle langsung memberi nilai akhir,
  // tidak tertahan di nilai awal transisi 0.01ms
  document.documentElement.classList.add('no-transition');
  const out = {};
  const baca = () => {
    const b = [...document.querySelectorAll('[data-theme-cycle]')]
      .find((x) => x.getBoundingClientRect().width > 0);
    const disc = b ? b.querySelector('.orb-disc') : null;
    const bite = b ? b.querySelector('.orb-bite') : null;
    const rays = b ? b.querySelector('.orb-rays') : null;
    const tf = (el) => {
      if (!el) { return null; }
      const t = getComputedStyle(el).transform;
      if (!t || t === 'none') { return [1, 0]; }
      try { const m = new DOMMatrixReadOnly(t); return [m.a, m.e]; } catch (e) { return [1, 0]; }
    };
    return {
      tema: document.documentElement.getAttribute('data-theme'),
      tersimpan: (function () { try { return localStorage.getItem('wp-theme'); } catch (e) { return null; } })(),
      orbGelap: b ? b.classList.contains('is-dark') : null,
      ariaChecked: b ? b.getAttribute('aria-checked') : null,
      ariaLabel: b ? b.getAttribute('aria-label') : null,
      skala: tf(disc),
      geserBulan: tf(bite),
      sinar: rays ? getComputedStyle(rays).opacity : null,
      tiraiAktif: (document.getElementById('themeWipe') || {}).className || '',
    };
  };
  const tombol = [...document.querySelectorAll('[data-theme-cycle]')]
    .find((x) => x.getBoundingClientRect().width > 0);
  out.awal = baca();
  tombol.click();
  out.setelahKlik1 = baca();
  tombol.click();
  out.setelahKlik2 = baca();
  const o = document.createElement('div');
  o.id = '__anim'; o.textContent = JSON.stringify(out);
  document.body.appendChild(o);
});
</script>
"""
# prefers-reduced-motion: reduce -> app.js melewati animasi, jadi klik langsung
# mengubah tema. Ini menguji logika intinya tanpa bergantung pada jam animasi.
B = ambil(render("anim-b.html", PROBE_B, budget=4000,
                 ekstra=("--force-prefers-reduced-motion",)))

if not B or B.get("galat"):
    cek("animasi: probe B terbaca", False, str(B.get("galat") or "kosong"))
else:
    awal, k1, k2 = B.get("awal", {}), B.get("setelahKlik1", {}), B.get("setelahKlik2", {})

    cek("tema: awalnya terang", awal.get("tema") == "light", str(awal.get("tema")))
    cek("tema: klik pertama jadi gelap", k1.get("tema") == "dark", str(k1.get("tema")))
    cek("tema: klik kedua balik terang", k2.get("tema") == "light", str(k2.get("tema")))
    cek("tema: pilihan tersimpan di localStorage setelah dipilih",
        k1.get("tersimpan") == "dark" and k2.get("tersimpan") == "light",
        f"{k1.get('tersimpan')} -> {k2.get('tersimpan')}")

    # ikon orb: keadaan tujuan saat gelap
    cek("ikon: cakram mengecil saat gelap (matahari jadi bulan)",
        (k1.get("skala") or [1])[0] < 0.99, str(k1.get("skala")))
    cek("ikon: sisi bulan bergeser menutup cakram",
        abs((k1.get("geserBulan") or [0, 0])[1]) > 5, str(k1.get("geserBulan")))
    cek("ikon: sinar matahari meredup habis",
        float(k1.get("sinar") or 1) < 0.05, str(k1.get("sinar")))
    cek("ikon: kembali ke matahari saat terang",
        abs((k2.get("skala") or [0])[0] - 1) < 0.01 and float(k2.get("sinar") or 0) > 0.95,
        f"skala={k2.get('skala')} sinar={k2.get('sinar')}")

    # aksesibilitas
    cek("a11y: aria-checked ikut berubah",
        awal.get("ariaChecked") == "false" and k1.get("ariaChecked") == "true",
        f"{awal.get('ariaChecked')} -> {k1.get('ariaChecked')}")
    cek("a11y: aria-label jadi ajakan ke tema terang",
        "terang" in (k1.get("ariaLabel") or "").lower(), str(k1.get("ariaLabel")))
    cek("a11y: reduced-motion mematikan tirai",
        "on" not in (k1.get("tiraiAktif") or ""), str(k1.get("tiraiAktif")))

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
