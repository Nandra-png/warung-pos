"""Smoke test: render semua halaman + uji POST kasir di salinan DB."""
import json
import os
import shutil
import sys
import traceback

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # skrip ini ada di tools/, akar repo satu level di atas
DB = os.path.join(BASE, "warung_pos.db")
BAK = DB + ".smoketest.bak"

sys.path.insert(0, BASE)
import app as appmod
appmod.init_db()  # clone baru belum punya warung_pos.db (di-gitignore)

shutil.copy2(DB, BAK)
try:
    appmod.app.config["TESTING"] = True
    c = appmod.app.test_client()

    hasil = []

    # --- login ---
    r = c.get("/login")
    hasil.append(("GET /login", r.status_code, b"Warung Pos" in r.data))

    r = c.post("/login", data={"username": "admin", "password": "admin123"},
               follow_redirects=False)
    hasil.append(("POST /login", r.status_code, r.headers.get("Location")))

    halaman = [
        ("/", 200, b"Dashboard"),
        ("/kasir", 200, b"Keranjang"),
        ("/barang", 200, b"Data Barang"),
        ("/riwayat", 200, b"Riwayat"),
        ("/laporan", 200, b"Laporan"),
        ("/api/barang", 200, b"harga_jual"),
        ("/tidak-ada-halaman", 404, b"Halaman yang kamu cari"),
    ]
    for url, kode, perlu in halaman:
        r = c.get(url)
        ok = r.status_code == kode and perlu in r.data
        hasil.append((f"GET {url}", r.status_code, ok))
        if not ok:
            print("  BODY:", r.data[:300])

    # --- cek penanda UI penting di /kasir ---
    r = c.get("/kasir")
    html = r.data.decode("utf-8", "replace")
    for tanda in ["produk-grid", "chips", "cart-summary", "quick-amounts",
                  "btnSimpan", "fab-cart", "side-link", "tema-orb",
                  "themeWipe", "temaPanggung", "pg-bulan-cut",
                  "data-theme", "Inter", "Ctrl K"]:
        ada = tanda in html
        hasil.append((f"  penanda kasir: {tanda}", "-", ada))

    # --- POST /kasir/simpan (JSON) ---
    r = c.post("/kasir/simpan", json={
        "items": [{"barang_id": 1, "qty": 2}, {"barang_id": 3, "qty": 1}],
        "bayar": 50000,
        "catatan": "smoke test",
    })
    data = json.loads(r.data)
    hasil.append(("POST /kasir/simpan", r.status_code, data.get("ok")))
    print("  ->", json.dumps(data, ensure_ascii=False)[:260])

    # struk & API transaksi diuji setelah transaksi ada (pakai id hasil POST)
    tid = data.get("id")
    hasil.append(("transaksi id terisi", "-", bool(tid)))
    if tid:
        r = c.get(f"/transaksi/{tid}")
        hasil.append((f"GET /transaksi/{tid} (struk)", r.status_code,
                      r.status_code == 200 and b"Struk" in r.data))
        r = c.get(f"/api/transaksi/{tid}")
        hasil.append((f"GET /api/transaksi/{tid}", r.status_code,
                      r.status_code == 200 and b"ok" in r.data))
    # id yang tidak ada harus 404, bukan 500
    r = c.get("/api/transaksi/999999")
    hasil.append(("GET /api/transaksi/999999 -> 404", r.status_code, r.status_code == 404))
    r = c.get("/transaksi/999999", follow_redirects=False)
    hasil.append(("GET /transaksi/999999 -> redirect", r.status_code, r.status_code == 302))

    # --- POST /kasir/simpan (form, jalur lama) ---
    r = c.post("/kasir/simpan", data={
        "barang_id": ["2"], "qty": ["1"], "bayar": "20000", "catatan": "form test",
    })
    data2 = json.loads(r.data)
    hasil.append(("POST /kasir/simpan (form)", r.status_code, data2.get("ok")))

    # --- CRUD barang (form) ---
    # id barang baru diambil dari hasil tambah, JANGAN di-hardcode:
    # database bisa sudah berisi barang lain, dan tes tidak boleh menyentuhnya.
    r = c.post("/barang/tambah", data={
        "nama": "Smoke Test Item", "harga_beli": "1000",
        "harga_jual": "1500", "stok": "7", "satuan": "pcs",
    }, follow_redirects=True)
    hasil.append(("POST /barang/tambah", r.status_code, b"Smoke Test Item" in r.data))

    daftar = json.loads(c.get("/api/barang").data)
    baru = [b for b in daftar if b["nama"] == "Smoke Test Item"]
    bid = baru[0]["id"] if baru else None
    hasil.append(("barang baru punya id", "-", bid is not None))

    if bid:
        r = c.post(f"/barang/{bid}/edit", data={
            "nama": "Smoke Test Item Edit", "harga_beli": "1100",
            "harga_jual": "1600", "stok": "9", "satuan": "pcs",
        }, follow_redirects=True)
        hasil.append((f"POST /barang/{bid}/edit", r.status_code,
                      b"Smoke Test Item Edit" in r.data))

    r = c.post("/barang/99/hapus", follow_redirects=True)
    hasil.append(("POST /barang/99/hapus (id tak ada)", r.status_code,
                  b"tidak ditemukan" in r.data))

    if bid:
        r = c.post(f"/barang/{bid}/hapus", follow_redirects=True)
        sisa = json.loads(c.get("/api/barang").data)
        hasil.append((f"POST /barang/{bid}/hapus", r.status_code,
                      b"dihapus" in r.data and
                      all("Smoke Test Item" not in b["nama"] for b in sisa)))
        # barang lain harus utuh
        hasil.append(("barang lain tidak tersentuh", "-",
                      len(sisa) == len(daftar) - 1))

    # --- stok turun setelah transaksi? ---
    r = c.get("/api/barang")
    stok = {b["id"]: b["stok"] for b in json.loads(r.data)}
    print("  stok akhir:", stok)

    # --- route lama masih ada ---
    # laporan harian: pakai tanggal hari ini (bukan tanggal hardcode)
    import datetime
    hari_ini = datetime.date.today().isoformat()
    r = c.get(f"/api/laporan/{hari_ini}")
    hasil.append((f"GET /api/laporan/{hari_ini}", r.status_code,
                  r.status_code == 200 and b"omzet" in r.data))

    print("\n--- daftar route ---")
    for rule in sorted(appmod.app.url_map.iter_rules(), key=lambda x: str(x)):
        print(f"  {str(rule):40s} {sorted(rule.methods - {'HEAD','OPTIONS'})}")

    print("\n--- hasil smoke test ---")
    gagal = 0
    for nama, code, ok in hasil:
        tanda = "OK " if ok else "GAGAL"
        if not ok:
            gagal += 1
        print(f"  [{tanda}] {nama} (status={code})")
    print(f"\n{'SEMUA LULUS' if gagal == 0 else str(gagal) + ' GAGAL'}")

except Exception:
    traceback.print_exc()
finally:
    shutil.copy2(BAK, DB)
    os.remove(BAK)
    print("\nDB dikembalikan ke kondisi semula.")
