# warung-pos

Point of sale for a small shop. Tracks stock and sales. Flask + SQLite.

```
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`, login first.

Default credentials `admin` / `admin123`. Override with `KASIR_USER` and `KASIR_PASS` env vars.

## Pages

```
/login              login
/barang             stock list
/barang/tambah      add item
/kasir              checkout
/riwayat            transaction history
/laporan            daily report
```

Everything except `/login` is wrapped in `@login_required`. Logged-out requests bounce to `/login?next=...`.

## How it works

Price and stock must parse as positive numbers, item name can't be empty. Invalid input re-renders the form with an error message.

Checkout runs inside a transaction, so stock and the sale record update together. If one fails, nothing is written.

Queries use `?` placeholders, no concatenation.

## Test

Log in, then add an item:

```bash
curl -c cookie.txt -X POST http://localhost:5000/login -d "username=admin&password=admin123"
```

```bash
curl -b cookie.txt -X POST http://localhost:5000/barang/tambah -d "nama=Indomie&harga_beli=2500&harga_jual=3500&stok=50"
```

Request `/barang` without the cookie. Returns 302 to `/login`.

## Todo

- no change-password page
- no barcode scanning, manual entry only
- no receipt printing
- daily report only, no monthly

## Tampilan (redesign UI)

Seluruh tampilan dirombak mengikuti gaya soft-UI: banyak ruang putih, sudut membulat,
satu warna aksen merah koral. HTML/CSS/JS saja, logika backend tidak diubah.

- Palet dari CSS variables di `:root` (`static/css/style.css`): `--accent: #EF4444`,
  `--bg-app: #F5F6FA`, `--bg-card: #FFFFFF`, `--accent-soft: #FEECEC`, dst.
- Font Inter, ikon SVG inline Lucide (stroke 1.75) dari `templates/_icons.html`. Tidak ada emoji.
- Tema Terang/Gelap, default Terang, pilihan disimpan di `localStorage`.
- Ganti tema beranimasi tiga babak, dijalankan `gantiTema()` di `static/js/app.js`:
  1. **Tirai masuk**: blok warna tema tujuan menyebar dari tombol yang diklik sampai
     menutupi penuh layar; tepinya buram lalu menajam.
  2. **Panggung orb**: di tengah layar matahari tenggelam dan berubah jadi bulan sabit
     (atau kebalikannya). Palet ditukar di tengah babak ini, saat layar masih tertutup.
  3. **Tirai keluar**: blok yang sama ditarik dari titik yang sama, jadi tidak ada sambungan.
     Orb hilang dengan redup + kabur.
- Bentuk sabit dibuat dengan satu `<mask>` berisi dua lingkaran (satu putih = badan bulan,
  satu hitam = potongan), teknik yang sama dengan referensi `Animasi_Siang_Malam.html`.
  Potongan digeser 36 satuan diagonal sehingga bulan terlihat ~48 persen, bukan bolong.
- `prefers-reduced-motion: reduce` melewati seluruh animasi: tema langsung berganti.
- Shell `templates/base.html`: sidebar + topbar + toast, dipakai semua halaman.

```
templates/
  base.html        shell: sidebar + topbar + toast + blok tema
  _icons.html      makro ikon SVG inline (Lucide, stroke 1.75). Bukan emoji.
  index.html       dashboard (statistik + grafik 7 hari + stok menipis)
  kasir.html       kasir (grid barang + panel keranjang)
  barang.html      daftar barang (tabel + drawer tambah/edit)
  riwayat.html     riwayat + drawer detail struk
  laporan.html     laporan (ringkasan + terlaris + tren + ekspor CSV)
  detail.html      struk siap cetak
  login.html       login (tanpa sidebar)
  404.html         halaman tidak ditemukan
static/
  css/style.css    seluruh tampilan (CSS variables, light + dark)
  js/app.js        helper UI: toast, modal, drawer, tema, format Rupiah
tools/             skrip uji (lihat bagian Skrip uji di bawah)
```

API tambahan (read-only, dipakai drawer riwayat):

```
/api/transaksi/<id>         detail satu transaksi + itemnya (JSON)
```

### Lebar layar

Sudah diuji tanpa scroll samping di 1920, 1536, 1366, 1280, 1024, 768, 390, dan 360 px.

- `> 1366px` tata letak penuh: sidebar 240px, konten + panel keranjang 360px.
- `<= 1366px` versi rapat: padding dan kartu produk mengecil, tetap 3 kolom.
- `<= 1279px` sidebar jadi rel ikon (72px), panel keranjang jadi drawer kanan
  yang dibuka lewat tombol mengambang "Keranjang (n)".
- `<= 767px` sidebar jadi bottom navigation (5 menu utama), grid barang 2 kolom,
  keranjang jadi bottom sheet, tabel menyembunyikan kolom sekunder.
- `<= 360px` grid barang 1 kolom.
- Tinggi layar `<= 700px` (laptop pendek) daftar barang dan keranjang ikut dipadatkan.

Target sentuh minimal 44px di perangkat tanpa hover.

### Kustomisasi

Warna aksen seluruh aplikasi diganti dari satu tempat: variabel `--accent`.

```css
:root {
  --accent: #EF4444;        /* ganti jadi #2563EB untuk biru, dsb. */
  --accent-soft: #FEECEC;   /* versi muda untuk latar tombol/ikon sekunder */
  --accent-hover: #DC2626;  /* versi gelap untuk state hover */
}
```

Warna mode gelap ada di blok `[data-theme="dark"]` pada file yang sama.

### Skrip uji

```bash
python tools/smoke_test.py        # semua route, POST kasir (JSON + form), CRUD barang
python tools/verify_tema.py       # token warna, tema default, bersih dari emoji/Jinja bocor, grafik 7 batang
python tools/verify_responsif.py  # ukur DOM nyata: nav HP, tombol keranjang, rail ikon, target 44px
python tools/snapshot_hp.py       # render HP 390/360 px + tablet 768 px, cek scroll samping
node   tools/verify_animasi.mjs   # animasi ganti tema, pakai Chrome headless + jam NYATA via CDP
node   tools/shot_animasi.mjs http://127.0.0.1:5000/kasir "$LOCALAPPDATA/Temp/wp-animasi"
node   tools/shot_animasi.mjs http://127.0.0.1:5000/kasir "$LOCALAPPDATA/Temp/wp-animasi" reduced
```

`verify_animasi.mjs` wajib dijalankan dengan **servernya hidup** (`python app.py`), karena
ia menyambung ke URL aplikasi, bukan ke berkas lokal. Skrip ini membaca `getAnimations()`
dan `getComputedStyle()` pada jam nyata: `--virtual-time-budget` milik Chrome headless
membuat animasi CSS tidak pernah selesai, jadi angka berbasis waktu tidak bisa dipercaya di
mode itu. Ia juga menghitung sendiri berkas PNG tangkapan layar (tanpa pustaka luar) untuk
membuktikan bentuk bulan sabit dari PIXEL, bukan cuma dari angka transform.

`shot_animasi.mjs` menyimpan rangkaian tangkapan layar tiap babak ke folder yang diberikan,
dan dengan argumen ketiga `reduced` ia menguji jalur `prefers-reduced-motion` memakai
`Emulation.setEmulatedMedia`.

`verify_responsif.py` dan `snapshot_hp.py` memakai Chrome/Edge headless dan mengukur
`getBoundingClientRect()`/`getComputedStyle()` pada viewport eksak, jadi hasilnya angka
nyata. Semua skrip membuat `warung_pos.db` sendiri kalau belum ada, dan mengembalikan
database ke kondisi semula setelah selesai.
