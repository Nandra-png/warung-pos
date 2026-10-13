# warung-pos

aplikasi kasir warung, nyatet barang sama transaksi. flask + sqlite

```
pip install -r requirements.txt
python app.py
```

buka `http://127.0.0.1:5000`, login dulu

default user `admin` password `admin123`, bisa diganti lewat env `KASIR_USER` sama `KASIR_PASS`

## halaman

```
/login              login
/barang             daftar barang
/barang/tambah      tambah barang
/kasir              transaksi
/riwayat            riwayat transaksi
/laporan            laporan harian
```

semua selain `/login` pake `@login_required`, kalo belum login dibalikin ke `/login?next=...`

## teknis

stok sama harga dicek harus angka positif, nama barang gak boleh kosong, kalo salah dibalikin ke formnya sama pesan error

transaksi pake transaction, jadi stok sama recordnya keupdate barengan, kalo salah satu gagal ya gak ada yang kesimpen

query pake `?` bukan concat

## tes

login dulu terus tambah barang

```bash
curl -c cookie.txt -X POST http://localhost:5000/login -d "username=admin&password=admin123"
```

```bash
curl -b cookie.txt -X POST http://localhost:5000/barang/tambah -d "nama=Indomie&harga_beli=2500&harga_jual=3500&stok=50"
```

coba akses `/barang` tanpa cookie, hasilnya 302 ke `/login`

## todo

- belum ada halaman ganti password
- belum ada barcode, masih ketik manual
- belum bisa cetak struk
- laporan cuma harian, belom bulanan
- tampilan masih basic
