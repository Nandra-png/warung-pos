"""Ukur DOM/CSS nyata lewat CDP untuk membuktikan perbaikan responsif.

Setiap angka diambil dari getBoundingClientRect()/getComputedStyle() pada viewport
eksak, bukan dilihat dari gambar (model ini tanpa vision).

Cek yang dijalankan:
  1. kolom pencarian: teks tidak menimpa ikon kaca pembesar (padding-left efektif)
  2. bottom nav HP: tepat 5 item, tiap item >= 44px, tidak ada yang melipat
  3. tombol keranjang (FAB) tidak tertutup bottom nav
  4. rail ikon 768-1279px: tidak bisa di-scroll samping, profil tidak meluber,
     tiap link punya accessible name
  5. target sentuh >= 44px
"""
import json
import os
import re
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # skrip ini ada di tools/, akar repo satu level di atas
OUT = os.path.join(os.environ["LOCALAPPDATA"], "Temp", "wp_ukur")
os.makedirs(OUT, exist_ok=True)

sys.path.insert(0, BASE)
import app as appmod  # noqa: E402
appmod.init_db()  # clone baru belum punya warung_pos.db (di-gitignore)

appmod.app.config["TESTING"] = True
c = appmod.app.test_client()
c.post("/login", data={"username": "admin", "password": "admin123"})

CHROME = None
for cand in [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]:
    if os.path.exists(cand):
        CHROME = cand
        break

PROBE = r"""
<script>
window.__ukur = function () {
  const r = (el) => el ? el.getBoundingClientRect() : null;
  const vis = (el) => {
    if (!el) return false;
    const s = getComputedStyle(el);
    const b = el.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && b.width > 0 && b.height > 0;
  };
  const out = {};

  // 1. kolom pencarian
  const inp = document.querySelector('#globalSearch');
  const ico = document.querySelector('.search > svg.ico');
  if (inp && ico) {
    const cs = getComputedStyle(inp);
    const ib = r(inp), cb = r(ico);
    out.search_padding_left = parseFloat(cs.paddingLeft);
    out.search_ikon_kanan = Math.round(cb.right);
    out.search_teks_kiri = Math.round(ib.left + parseFloat(cs.paddingLeft));
    out.search_tumpang_tindih = Math.round(cb.right - (ib.left + parseFloat(cs.paddingLeft)));
  }

  // 2. bottom nav
  const navTampil = [...document.querySelectorAll('.side-link')].filter(vis);
  out.nav_jumlah = navTampil.length;
  out.nav_label = navTampil.map((a) => (a.querySelector('.txt') || {}).textContent || a.getAttribute('aria-label'));
  out.nav_lebar = navTampil.map((a) => Math.round(r(a).width));
  out.nav_tinggi = navTampil.map((a) => Math.round(r(a).height));
  out.nav_lipat = navTampil.filter((a) => {
    const t = a.querySelector('.txt');
    if (!t) return false;
    const s = getComputedStyle(t);
    return s.whiteSpace === 'normal';
  }).length;

  // 3. FAB vs nav
  const fab = document.querySelector('.fab-cart');
  const nav = document.querySelector('.sidebar');
  if (vis(fab) && nav) {
    const fb = r(fab), nb = r(nav);
    const tumpuk = Math.max(0, Math.min(fb.bottom, nb.bottom) - Math.max(fb.top, nb.top));
    out.fab_tinggi = Math.round(fb.height);
    out.fab_tertutup_nav = Math.round(tumpuk);
    out.fab_box = Math.round(fb.top) + '..' + Math.round(fb.bottom);
    out.nav_box = Math.round(nb.top) + '..' + Math.round(nb.bottom);
    out.fab_di_atas = tumpuk <= 0 && fb.bottom <= nb.top + 2;
  } else {
    out.fab = vis(fab) ? 'tampil' : 'tidak tampil';
  }

  // 4. rail ikon
  const sb = document.querySelector('.sidebar');
  if (sb) {
    out.rail_scroll_samping = sb.scrollWidth - sb.clientWidth;
    out.rail_lebar = Math.round(sb.clientWidth);
  }
  const prof = document.querySelector('.profile');
  if (vis(prof)) {
    const pb = r(prof);
    out.profil = Math.round(pb.left) + '..' + Math.round(pb.right);
    out.profil_meluber = Math.round(pb.right - (sb ? r(sb).right : pb.right));
  }
  out.nav_akses_nama = [...document.querySelectorAll('.side-link')]
    .filter(vis)
    .filter((a) => {
      const t = a.querySelector('.txt');
      const punyaTeks = t && getComputedStyle(t).display !== 'none' && t.textContent.trim();
      return !(a.getAttribute('aria-label') || a.getAttribute('title') || punyaTeks);
    }).length;

  // 5. target sentuh yang terlalu kecil
  // target sentuh: syarat 44px berlaku kalau layar sentuh (HP / rail tablet).
  const sentuh = window.matchMedia('(hover: none)').matches || window.innerWidth <= 1279;
  const minPx = sentuh ? 44 : 40;
  const kecil = [];
  document.querySelectorAll('.side-link, .icon-btn, .top-actions .btn, .qty-btn, .side-collapse, .close-btn, .fab-cart')
    .forEach((el) => {
      if (!vis(el)) return;
      const b = r(el);
      if (b.height < minPx || b.width < 24) {
        kecil.push((el.className || '').toString().split(' ')[0] + ':' +
                   Math.round(b.width) + 'x' + Math.round(b.height));
      }
    });
  out.target_kecil = kecil;
  out.target_min = minPx;

  out.viewport = window.innerWidth + 'x' + window.innerHeight;
  out.doc_scroll = document.documentElement.scrollWidth;

  const o = document.createElement('div');
  o.id = '__ukuran';
  o.textContent = JSON.stringify(out);
  document.body.appendChild(o);
};
window.addEventListener('load', () => setTimeout(window.__ukur, 900));
</script>
"""

UKURAN = [("laptop-1440", 1440, 900, "/kasir"), ("laptop-1100", 1100, 800, "/kasir"),
          ("tablet-1024", 1024, 768, "/kasir"), ("tablet-768", 768, 900, "/kasir"),
          ("hp-390", 390, 844, "/kasir"), ("hp-360", 360, 640, "/kasir"),
          ("hp-390-barang", 390, 844, "/barang"), ("hp-390-dashboard", 390, 844, "/")]

hasil = {}
for nama, w, h, url in UKURAN:
    r = c.get(url)
    html = r.data.decode("utf-8", "replace")
    html = html.replace('href="/static/', f'href="file:///{BASE.replace(chr(92), "/")}/static/')
    html = html.replace('src="/static/', f'src="file:///{BASE.replace(chr(92), "/")}/static/')
    html = re.sub(r'href="(/[^"]*)"', 'href="#"', html)
    html = html.replace("</body>", PROBE + "</body>")
    ph = os.path.join(OUT, f"{nama}.html")
    open(ph, "w", encoding="utf-8").write(html)

    dump = subprocess.run([
        CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
        "--no-default-browser-check", "--allow-file-access-from-files",
        "--virtual-time-budget=3000", "--dump-dom",
        f"--window-size={w},{h}", f"file:///{ph.replace(os.sep, '/')}",
    ], capture_output=True, text=True, timeout=180).stdout or ""

    m = re.search(r'id="__ukuran">(.*?)</div>', dump, re.S)
    if m:
        try:
            hasil[nama] = json.loads(m.group(1).replace("&quot;", '"'))
        except Exception as e:
            hasil[nama] = {"error": "parse: " + str(e)}
    else:
        hasil[nama] = {"error": "tidak terbaca"}

print("\n=== HASIL UKUR (angka nyata dari DOM) ===")
for nama, d in hasil.items():
    print(f"\n--- {nama} ---")
    for k, v in d.items():
        print(f"  {k}: {v}")

# ---------- evaluasi ----------
print("\n=== EVALUASI ===")
gagal = []


def uji(nama_uji, kondisi, detail=""):
    if not kondisi:
        gagal.append(nama_uji + (" (" + str(detail) + ")" if detail else ""))
    print(f"  [{'OK ' if kondisi else 'GAGAL'}] {nama_uji}" + (f"  {detail}" if detail else ""))


print("\n-- 1. pencarian tidak tumpang tindih ikon --")
for n, d in hasil.items():
    t = d.get("search_tumpang_tindih")
    if t is not None:
        uji(f"{n}: teks tidak menimpa ikon", t <= 0, f"jarak={abs(t)}px padl={d.get('search_padding_left')}")

print("\n-- 2. bottom nav HP --")
for n, d in hasil.items():
    if n.startswith("hp-"):
        uji(f"{n}: nav 5 item", d.get("nav_jumlah") == 5, f"{d.get('nav_jumlah')} item {d.get('nav_label')}")
        uji(f"{n}: tidak ada label melipat", d.get("nav_lipat") == 0, str(d.get("nav_lipat")))
        uji(f"{n}: nav >=44px", all(x >= 44 for x in (d.get("nav_tinggi") or [0])), str(d.get("nav_tinggi")))

print("\n-- 3. tombol keranjang tidak tertutup nav --")
for n, d in hasil.items():
    if n.startswith("hp-") and "fab_di_atas" in d:
        uji(f"{n}: FAB di atas nav", d["fab_di_atas"], f"tertutup={d.get('fab_tertutup_nav')}px")

print("\n-- 4. rail ikon 768-1279px --")
for n in ("tablet-768", "tablet-1024", "laptop-1100"):
    d = hasil.get(n, {})
    if "rail_scroll_samping" in d:
        uji(f"{n}: rail tidak bisa digeser samping", d["rail_scroll_samping"] <= 0, f"{d['rail_scroll_samping']}px")
    if "profil_meluber" in d:
        uji(f"{n}: profil tidak meluber", d["profil_meluber"] <= 0, str(d.get("profil")))

print("\n-- 5. accessible name & target sentuh --")
for n, d in hasil.items():
    uji(f"{n}: semua nav punya nama", d.get("nav_akses_nama") == 0, str(d.get("nav_akses_nama")))
    kecil = d.get("target_kecil") or []
    uji(f"{n}: target >=44px", not kecil, str(kecil))

print(f"\n{'SEMUA LULUS' if not gagal else str(len(gagal)) + ' GAGAL: ' + '; '.join(gagal)}")
