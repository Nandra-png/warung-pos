"""Uji lebar HP sungguhan: bungkus halaman di iframe dengan lebar eksak.

Edge headless punya lebar jendela minimum ~500px, jadi --window-size=390 tidak
benar-benar memberi viewport 390px. Iframe memberi viewport eksak.
"""
import os
import re
import subprocess
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # skrip ini ada di tools/, akar repo satu level di atas
STATIC = os.path.join(BASE, "static").replace("\\", "/")
OUT = os.path.join(os.environ["LOCALAPPDATA"], "Temp", "wp_hp")
os.makedirs(OUT, exist_ok=True)

sys.path.insert(0, BASE)
import app as appmod  # noqa: E402

appmod.app.config["TESTING"] = True
c = appmod.app.test_client()
c.post("/login", data={"username": "admin", "password": "admin123"})

LEBAR = [("hp-390", 390, 844), ("hp-360", 360, 640), ("tablet-768", 768, 900)]
HALAMAN = [("kasir", "/kasir"), ("dashboard", "/"), ("barang", "/barang"),
           ("riwayat", "/riwayat"), ("laporan", "/laporan")]

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

KERANGKA = """<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
  html,body{{margin:0;padding:0;background:#fff;}}
  iframe{{border:0;display:block;width:{w}px;height:{h}px;}}
</style></head><body>
<iframe src="{src}" width="{w}" height="{h}"></iframe>
<script>
window.addEventListener('load', function () {{
  var f = document.querySelector('iframe');
  function ukur() {{
    try {{
      var d = f.contentDocument.documentElement;
      var nakal = [];
      f.contentDocument.querySelectorAll('body *').forEach(function (el) {{
        var r = el.getBoundingClientRect();
        if (r.width > 0 && (r.right > d.clientWidth + 2 || r.left < -2)) {{
          var t = (el.tagName || '').toLowerCase();
          if (['svg','path','circle','rect','div','span'].indexOf(t) > -1 &&
              !(el.className || '').toString().match(/^chip|^table|^thead|^tbody|^tr/)) return;
          nakal.push(t + '.' + (el.className || '').toString().split(' ')[0] +
                     '[' + Math.round(r.left) + '..' + Math.round(r.right) + ']');
        }}
      }});
      var o = document.createElement('div');
      o.id = '__ovf';
      o.textContent = d.scrollWidth + '|' + d.clientWidth + '|' + (nakal.slice(0, 5).join(',') || 'bersih');
      document.body.appendChild(o);
    }} catch (e) {{
      var o = document.createElement('div');
      o.id = '__ovf'; o.textContent = 'err:' + e.message;
      document.body.appendChild(o);
    }}
  }}
  setTimeout(ukur, 800);
}});
</script></body></html>
"""

hasil = []
for nama, w, h in LEBAR:
    for hp, url in HALAMAN:
        r = c.get(url)
        html = r.data.decode("utf-8", "replace")
        html = html.replace('href="/static/', f'href="file:///{STATIC}/')
        html = html.replace('src="/static/', f'src="file:///{STATIC}/')
        html = re.sub(r'href="(/[^"]*)"', 'href="#"', html)

        dalam = os.path.join(OUT, f"dalam-{nama}-{hp}.html")
        open(dalam, "w", encoding="utf-8").write(html)

        luar = os.path.join(OUT, f"luar-{nama}-{hp}.html")
        open(luar, "w", encoding="utf-8").write(
            KERANGKA.format(w=w, h=h, src="dalam-" + nama + "-" + hp + ".html"))

        # cek overflow + screenshot; jendela lebih lebar dari iframe
        png = os.path.join(OUT, f"{nama}-{hp}.png")
        dump = subprocess.run([
            EDGE, "--headless=new", "--disable-gpu", "--no-first-run",
            "--no-default-browser-check", "--allow-file-access-from-files",
            "--hide-scrollbars", "--virtual-time-budget=3000",
            f"--window-size={w + 40},{h + 40}", "--dump-dom",
            f"file:///{luar.replace(os.sep, '/')}",
        ], capture_output=True, text=True, timeout=120).stdout or ""

        subprocess.run([
            EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars",
            "--no-first-run", "--no-default-browser-check",
            "--allow-file-access-from-files",
            f"--screenshot={png}", f"--window-size={w + 40},{h + 40}",
            "--virtual-time-budget=3000",
            f"file:///{luar.replace(os.sep, '/')}",
        ], capture_output=True, text=True, timeout=120)

        m = re.search(r'id="__ovf">([^<]*)<', dump)
        info = m.group(1) if m else "tidak-terbaca"
        hasil.append((nama, hp, info, os.path.exists(png), os.path.getsize(png) if os.path.exists(png) else 0))

print(f"\n=== VIEWPORT EKSAK lewat iframe ===")
print("aman kalau scrollWidth == clientWidth\n")
gagal = 0
for nama, hp, info, ok, size in hasil:
    b = info.split("|")
    aman = len(b) == 3 and b[0] == b[1]
    if not aman:
        gagal += 1
    print(f"  [{'AMAN ' if aman else 'LEBAR'}] {nama:10s} {hp:10s} {info}  png={size}")

print(f"\n{'Semua muat tanpa scroll samping.' if gagal == 0 else str(gagal) + ' masih meluber.'}")
print("Folder:", OUT)
