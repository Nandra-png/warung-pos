import os
import sqlite3
from datetime import datetime, date, timedelta
from functools import wraps

from flask import (
    Flask,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
    flash,
)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "warung_pos.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "warung-pos-dev-key")

SCHEMA = """
CREATE TABLE IF NOT EXISTS barang (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nama        TEXT    NOT NULL,
    harga_beli  INTEGER NOT NULL DEFAULT 0,
    harga_jual  INTEGER NOT NULL DEFAULT 0,
    stok        INTEGER NOT NULL DEFAULT 0,
    satuan      TEXT    NOT NULL DEFAULT 'pcs',
    created_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS transaksi (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kode        TEXT    NOT NULL UNIQUE,
    total       INTEGER NOT NULL DEFAULT 0,
    bayar       INTEGER NOT NULL DEFAULT 0,
    kembali     INTEGER NOT NULL DEFAULT 0,
    catatan     TEXT    DEFAULT '',
    created_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS transaksi_item (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    transaksi_id  INTEGER NOT NULL,
    barang_id     INTEGER,
    nama_barang   TEXT    NOT NULL,
    harga_satuan  INTEGER NOT NULL,
    harga_beli    INTEGER NOT NULL DEFAULT 0,
    qty           INTEGER NOT NULL,
    subtotal      INTEGER NOT NULL,
    FOREIGN KEY (transaksi_id) REFERENCES transaksi (id) ON DELETE CASCADE,
    FOREIGN KEY (barang_id)    REFERENCES barang (id)    ON DELETE SET NULL
);
"""

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        cur = conn.execute("SELECT COUNT(*) AS n FROM barang")
        if cur.fetchone()["n"] == 0:
            now = datetime.now().isoformat(timespec="seconds")
            contoh = [
                ("Beras 1kg", 11000, 13000, 40, "pcs"),
                ("Gula 1kg", 14000, 16000, 25, "pcs"),
                ("Minyak Goreng 1L", 15000, 18000, 18, "botol"),
                ("Mie Instan", 2800, 3500, 100, "pcs"),
                ("Kopi Sachet", 1500, 2000, 120, "pcs"),
                ("Telur 1kg", 26000, 29000, 15, "kg"),
            ]
            conn.executemany(
                "INSERT INTO barang (nama, harga_beli, harga_jual, stok, satuan, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                [(*row, now) for row in contoh],
            )
            conn.commit()
    finally:
        conn.close()

def rupiah(nilai):
    try:
        return "Rp " + f"{int(nilai):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "Rp 0"

app.jinja_env.filters["rupiah"] = rupiah

# ---------------------------------------------------------------------------
# Helper tampilan (read-only, tidak mengubah logika aplikasi)
# ---------------------------------------------------------------------------
HARI_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
BULAN_ID = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
            "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
BULAN_PANJANG = ["Januari", "Februari", "Maret", "April", "Mei", "Juni",
                 "Juli", "Agustus", "September", "Oktober", "November", "Desember"]


def _ke_datetime(nilai):
    if isinstance(nilai, str):
        try:
            return datetime.fromisoformat(nilai.replace("Z", ""))
        except ValueError:
            return None
    return nilai


def tanggal_id(nilai=None):
    """'2026-10-20T09:30:00' -> 'Sel, 20 Okt'"""
    d = _ke_datetime(nilai) or datetime.now()
    return f"{HARI_ID[d.weekday()][:3]}, {d.day} {BULAN_ID[d.month - 1]}"


def tanggal_panjang_id(nilai=None):
    d = _ke_datetime(nilai) or datetime.now()
    return f"{HARI_ID[d.weekday()]}, {d.day} {BULAN_PANJANG[d.month - 1]} {d.year}"


def jam_id(nilai=None):
    d = _ke_datetime(nilai) or datetime.now()
    return d.strftime("%H:%M")


def jam_menit_id(nilai=None):
    d = _ke_datetime(nilai) or datetime.now()
    return d.strftime("%H:%M")


app.jinja_env.filters["tanggal_id"] = tanggal_id
app.jinja_env.filters["tanggal_panjang_id"] = tanggal_panjang_id
app.jinja_env.filters["jam_id"] = jam_id
app.jinja_env.globals["now"] = datetime.now
app.jinja_env.globals["today"] = date.today

def row_to_dict(row):
    return {k: row[k] for k in row.keys()} if row else None


def tren_7_hari(db):
    """Omzet 7 hari terakhir, hari tanpa transaksi diisi 0 supaya grafik selalu 7 batang."""
    rows = db.execute(
        "SELECT date(created_at) tgl, COALESCE(SUM(total), 0) omzet, COUNT(*) jumlah"
        " FROM transaksi WHERE date(created_at) >= date('now', '-6 days')"
        " GROUP BY date(created_at)"
    ).fetchall()
    ada = {r["tgl"]: r for r in rows}
    hari_ini = date.today()
    seri = []
    for i in range(6, -1, -1):
        tgl = (hari_ini - timedelta(days=i)).isoformat()
        r = ada.get(tgl)
        seri.append({
            "tgl": tgl,
            "omzet": r["omzet"] if r else 0,
            "jumlah": r["jumlah"] if r else 0,
        })
    return seri

USERS = {
    os.environ.get("KASIR_USER", "admin"): os.environ.get("KASIR_PASS", "admin123"),
}

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


@app.context_processor
def inject_shell():
    """Angka kecil untuk shell UI (badge sidebar). Read-only, tidak menyentuh data."""
    kosong = {"nav_trx_hari": 0, "nav_stok_kritis": 0, "nav_total_barang": 0}
    if not session.get("user"):
        return kosong
    try:
        db = get_db()
        hari = date.today().isoformat()
        return {
            "nav_trx_hari": db.execute(
                "SELECT COUNT(*) c FROM transaksi WHERE date(created_at) = ?", (hari,)
            ).fetchone()["c"],
            "nav_stok_kritis": db.execute(
                "SELECT COUNT(*) c FROM barang WHERE stok <= 5"
            ).fetchone()["c"],
            "nav_total_barang": db.execute(
                "SELECT COUNT(*) c FROM barang"
            ).fetchone()["c"],
        }
    except Exception:
        return kosong

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username", "").strip()
        p = request.form.get("password", "")
        if USERS.get(u) == p:
            session["user"] = u
            flash(f"Selamat datang, {u}!", "success")
            return redirect(request.args.get("next") or url_for("index"))
        flash("Username atau password salah.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Kamu sudah keluar.", "success")
    return redirect(url_for("login"))

@app.route("/")
@login_required
def index():
    db = get_db()
    hari_ini = date.today().isoformat()

    total_barang = db.execute("SELECT COUNT(*) c FROM barang").fetchone()["c"]
    nilai_stok = db.execute(
        "SELECT COALESCE(SUM(harga_beli * stok), 0) v FROM barang"
    ).fetchone()["v"]
    stok_kritis = db.execute(
        "SELECT * FROM barang WHERE stok <= 5 ORDER BY stok ASC LIMIT 10"
    ).fetchall()

    trx_hari = db.execute(
        "SELECT COUNT(*) c, COALESCE(SUM(total),0) t FROM transaksi"
        " WHERE date(created_at) = ?",
        (hari_ini,),
    ).fetchone()

    terbaru = db.execute(
        "SELECT * FROM transaksi ORDER BY id DESC LIMIT 5"
    ).fetchall()

    # --- tambahan read-only untuk tampilan dashboard (grafik 7 hari + terlaris) ---
    tren = tren_7_hari(db)

    terlaris_hari = db.execute(
        "SELECT ti.nama_barang, SUM(ti.qty) qty, SUM(ti.subtotal) omzet"
        " FROM transaksi_item ti JOIN transaksi t ON t.id = ti.transaksi_id"
        " WHERE date(t.created_at) = ?"
        " GROUP BY ti.nama_barang ORDER BY qty DESC LIMIT 5",
        (hari_ini,),
    ).fetchall()

    return render_template(
        "index.html",
        total_barang=total_barang,
        nilai_stok=nilai_stok,
        stok_kritis=stok_kritis,
        trx_count=trx_hari["c"],
        trx_total=trx_hari["t"],
        terbaru=terbaru,
        hari_ini=hari_ini,
        tren=list(reversed(tren)),
        terlaris_hari=terlaris_hari,
    )

@app.route("/barang")
@login_required
def barang_list():
    q = request.args.get("q", "").strip()
    db = get_db()
    if q:
        rows = db.execute(
            "SELECT * FROM barang WHERE nama LIKE ? ORDER BY nama",
            (f"%{q}%",),
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM barang ORDER BY nama").fetchall()
    return render_template("barang.html", barang_list=rows, q=q)

@app.route("/barang/tambah", methods=["POST"])
@login_required
def barang_tambah():
    nama = request.form.get("nama", "").strip()
    if not nama:
        flash("Nama barang wajib diisi.", "error")
        return redirect(url_for("barang_list"))

    try:
        harga_beli = int(request.form.get("harga_beli") or 0)
        harga_jual = int(request.form.get("harga_jual") or 0)
        stok = int(request.form.get("stok") or 0)
    except ValueError:
        flash("Harga dan stok harus berupa angka.", "error")
        return redirect(url_for("barang_list"))

    if harga_beli < 0 or harga_jual < 0 or stok < 0:
        flash("Nilai tidak boleh negatif.", "error")
        return redirect(url_for("barang_list"))

    satuan = request.form.get("satuan", "pcs").strip() or "pcs"
    db = get_db()
    db.execute(
        "INSERT INTO barang (nama, harga_beli, harga_jual, stok, satuan, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (nama, harga_beli, harga_jual, stok, satuan,
         datetime.now().isoformat(timespec="seconds")),
    )
    db.commit()
    flash(f"Barang '{nama}' ditambahkan.", "success")
    return redirect(url_for("barang_list"))

@app.route("/barang/<int:bid>/edit", methods=["POST"])
@login_required
def barang_edit(bid):
    db = get_db()
    row = db.execute("SELECT * FROM barang WHERE id = ?", (bid,)).fetchone()
    if not row:
        flash("Barang tidak ditemukan.", "error")
        return redirect(url_for("barang_list"))

    nama = request.form.get("nama", "").strip() or row["nama"]
    try:
        harga_beli = int(request.form.get("harga_beli") or row["harga_beli"])
        harga_jual = int(request.form.get("harga_jual") or row["harga_jual"])
        stok = int(request.form.get("stok") or row["stok"])
    except ValueError:
        flash("Harga dan stok harus berupa angka.", "error")
        return redirect(url_for("barang_list"))

    satuan = request.form.get("satuan", row["satuan"]).strip() or row["satuan"]
    db.execute(
        "UPDATE barang SET nama=?, harga_beli=?, harga_jual=?, stok=?, satuan=?"
        " WHERE id=?",
        (nama, harga_beli, harga_jual, stok, satuan, bid),
    )
    db.commit()
    flash(f"Barang '{nama}' diperbarui.", "success")
    return redirect(url_for("barang_list"))

@app.route("/barang/<int:bid>/hapus", methods=["POST"])
@login_required
def barang_hapus(bid):
    db = get_db()
    row = db.execute("SELECT nama FROM barang WHERE id = ?", (bid,)).fetchone()
    if not row:
        flash("Barang tidak ditemukan.", "error")
        return redirect(url_for("barang_list"))
    db.execute("DELETE FROM barang WHERE id = ?", (bid,))
    db.commit()
    flash(f"Barang '{row['nama']}' dihapus.", "success")
    return redirect(url_for("barang_list"))

@app.route("/kasir")
@login_required
def kasir():
    db = get_db()
    rows = db.execute("SELECT * FROM barang ORDER BY nama").fetchall()
    return render_template("kasir.html", barang_list=rows)

@app.route("/api/barang")
@login_required
def api_barang():
    db = get_db()
    rows = db.execute("SELECT * FROM barang ORDER BY nama").fetchall()
    return jsonify([row_to_dict(r) for r in rows])

def generate_kode(db):
    hari = datetime.now().strftime("%Y%m%d")
    row = db.execute(
        "SELECT COUNT(*) c FROM transaksi WHERE kode LIKE ?", (f"TRX-{hari}-%",)
    ).fetchone()
    return f"TRX-{hari}-{row['c'] + 1:03d}"

@app.route("/kasir/simpan", methods=["POST"])
@login_required
def kasir_simpan():
    if request.is_json:
        data = request.get_json(silent=True) or {}
    else:
        data = request.form.to_dict()
        data["items"] = request.form.getlist("barang_id")
        data["qty"] = request.form.getlist("qty")

    items = data.get("items") or []
    qtys = data.get("qty") or []

    parsed = []
    if isinstance(items, list) and items and isinstance(items[0], dict):
        for it in items:
            parsed.append((int(it.get("barang_id")), int(it.get("qty") or 0)))
    else:
        for bid, q in zip(items, qtys):
            parsed.append((int(bid), int(q or 0)))

    parsed = [(b, q) for b, q in parsed if q > 0]
    if not parsed:
        return jsonify({"ok": False, "error": "Tidak ada barang yang dipilih."}), 400

    db = get_db()
    keranjang = []
    total = 0
    for bid, qty in parsed:
        row = db.execute("SELECT * FROM barang WHERE id = ?", (bid,)).fetchone()
        if not row:
            return jsonify({"ok": False, "error": f"Barang id {bid} tidak ada."}), 400
        if row["stok"] < qty:
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": f"Stok '{row['nama']}' tidak cukup "
                        f"(tersisa {row['stok']}).",
                    }
                ),
                400,
            )
        subtotal = row["harga_jual"] * qty
        total += subtotal
        keranjang.append(
            {
                "barang_id": row["id"],
                "nama": row["nama"],
                "harga_satuan": row["harga_jual"],
                "harga_beli": row["harga_beli"],
                "qty": qty,
                "subtotal": subtotal,
            }
        )

    try:
        bayar = int(data.get("bayar") or total)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Nominal bayar tidak valid."}), 400

    if bayar < total:
        return jsonify({"ok": False, "error": "Uang bayar kurang dari total."}), 400

    kembali = bayar - total
    kode = generate_kode(db)
    now = datetime.now().isoformat(timespec="seconds")

    cur = db.execute(
        "INSERT INTO transaksi (kode, total, bayar, kembali, catatan, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (kode, total, bayar, kembali, data.get("catatan", "") or "", now),
    )
    trx_id = cur.lastrowid

    for it in keranjang:
        db.execute(
            "INSERT INTO transaksi_item"
            " (transaksi_id, barang_id, nama_barang, harga_satuan, harga_beli,"
            "  qty, subtotal)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                trx_id,
                it["barang_id"],
                it["nama"],
                it["harga_satuan"],
                it["harga_beli"],
                it["qty"],
                it["subtotal"],
            ),
        )
        db.execute(
            "UPDATE barang SET stok = stok - ? WHERE id = ?",
            (it["qty"], it["barang_id"]),
        )
    db.commit()

    return jsonify(
        {
            "ok": True,
            "id": trx_id,
            "kode": kode,
            "total": total,
            "bayar": bayar,
            "kembali": kembali,
            "items": keranjang,
            "struk_url": url_for("transaksi_detail", tid=trx_id),
        }
    )

@app.route("/riwayat")
@login_required
def riwayat():
    db = get_db()
    tanggal = request.args.get("tanggal", "").strip()
    if tanggal:
        rows = db.execute(
            "SELECT * FROM transaksi WHERE date(created_at) = ? ORDER BY id DESC",
            (tanggal,),
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM transaksi ORDER BY id DESC LIMIT 100").fetchall()

    total = sum(r["total"] for r in rows)
    return render_template(
        "riwayat.html", transaksi=rows, tanggal=tanggal, total=total
    )

@app.route("/transaksi/<int:tid>")
@login_required
def transaksi_detail(tid):
    db = get_db()
    trx = db.execute("SELECT * FROM transaksi WHERE id = ?", (tid,)).fetchone()
    if not trx:
        flash("Transaksi tidak ditemukan.", "error")
        return redirect(url_for("riwayat"))
    items = db.execute(
        "SELECT * FROM transaksi_item WHERE transaksi_id = ? ORDER BY id", (tid,)
    ).fetchall()
    return render_template("detail.html", trx=trx, items=items)

@app.route("/api/transaksi/<int:tid>")
@login_required
def api_transaksi_detail(tid):
    """Endpoint BARU (read-only) khusus drawer detail struk di halaman Riwayat."""
    db = get_db()
    trx = db.execute("SELECT * FROM transaksi WHERE id = ?", (tid,)).fetchone()
    if not trx:
        return jsonify({"ok": False, "error": "Transaksi tidak ditemukan."}), 404
    items = db.execute(
        "SELECT * FROM transaksi_item WHERE transaksi_id = ? ORDER BY id", (tid,)
    ).fetchall()
    return jsonify(
        {
            "ok": True,
            "trx": row_to_dict(trx),
            "items": [row_to_dict(i) for i in items],
            "detail_url": url_for("transaksi_detail", tid=tid),
        }
    )


@app.route("/transaksi/<int:tid>/hapus", methods=["POST"])
@login_required
def transaksi_hapus(tid):
    db = get_db()
    trx = db.execute("SELECT * FROM transaksi WHERE id = ?", (tid,)).fetchone()
    if not trx:
        flash("Transaksi tidak ditemukan.", "error")
        return redirect(url_for("riwayat"))

    items = db.execute(
        "SELECT * FROM transaksi_item WHERE transaksi_id = ?", (tid,)
    ).fetchall()
    for it in items:
        if it["barang_id"]:
            db.execute(
                "UPDATE barang SET stok = stok + ? WHERE id = ?",
                (it["qty"], it["barang_id"]),
            )
    db.execute("DELETE FROM transaksi_item WHERE transaksi_id = ?", (tid,))
    db.execute("DELETE FROM transaksi WHERE id = ?", (tid,))
    db.commit()
    flash(f"Transaksi {trx['kode']} dihapus, stok dikembalikan.", "success")
    return redirect(url_for("riwayat"))

@app.route("/laporan")
@app.route("/laporan/<tanggal>")
@login_required
def laporan(tanggal=None):
    if tanggal is None:
        tanggal = request.args.get("tanggal") or date.today().isoformat()

    db = get_db()
    ringkas = db.execute(
        "SELECT COUNT(*) jumlah, COALESCE(SUM(total),0) omzet,"
        " COALESCE(SUM(bayar),0) bayar, COALESCE(SUM(kembali),0) kembali"
        " FROM transaksi WHERE date(created_at) = ?",
        (tanggal,),
    ).fetchone()

    laba_row = db.execute(
        "SELECT COALESCE(SUM((ti.harga_satuan - ti.harga_beli) * ti.qty), 0) laba"
        " FROM transaksi_item ti JOIN transaksi t ON t.id = ti.transaksi_id"
        " WHERE date(t.created_at) = ?",
        (tanggal,),
    ).fetchone()

    terlaris = db.execute(
        "SELECT ti.nama_barang, SUM(ti.qty) qty, SUM(ti.subtotal) omzet"
        " FROM transaksi_item ti JOIN transaksi t ON t.id = ti.transaksi_id"
        " WHERE date(t.created_at) = ?"
        " GROUP BY ti.nama_barang ORDER BY qty DESC LIMIT 10",
        (tanggal,),
    ).fetchall()

    daftar = db.execute(
        "SELECT * FROM transaksi WHERE date(created_at) = ? ORDER BY id DESC",
        (tanggal,),
    ).fetchall()

    tren = tren_7_hari(db)

    return render_template(
        "laporan.html",
        tanggal=tanggal,
        ringkas=ringkas,
        laba=laba_row["laba"],
        terlaris=terlaris,
        daftar=daftar,
        tren=tren,
    )

@app.route("/api/laporan/<tanggal>")
@login_required
def api_laporan(tanggal):
    db = get_db()
    ringkas = db.execute(
        "SELECT COUNT(*) jumlah, COALESCE(SUM(total),0) omzet FROM transaksi"
        " WHERE date(created_at) = ?",
        (tanggal,),
    ).fetchone()
    laba = db.execute(
        "SELECT COALESCE(SUM((ti.harga_satuan - ti.harga_beli) * ti.qty), 0) laba"
        " FROM transaksi_item ti JOIN transaksi t ON t.id = ti.transaksi_id"
        " WHERE date(t.created_at) = ?",
        (tanggal,),
    ).fetchone()
    return jsonify(
        {
            "tanggal": tanggal,
            "jumlah_transaksi": ringkas["jumlah"],
            "omzet": ringkas["omzet"],
            "laba": laba["laba"],
        }
    )

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404

if __name__ == "__main__":
    init_db()
    print(f"[kasir] Database : {DB_PATH}")
    print("[kasir] Buka    : http://127.0.0.1:5000  (admin / admin123)")
    app.run(debug=True, host="127.0.0.1", port=5000)
