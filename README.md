# warung-pos

jadi warungnya emak saya itu masih nyatet pake buku, terus suka kelupaan naruh bukunya terus bingung stoknya berapa, jadi saya coba bikin aplikasi kecil buat nyatet barang sama transaksinya

awalnya cuma buat emak saya, terus kepikiran sekalian aja saya taro di github biar ada isinya

## isinya apa

pake flask sama sqlite, simpel aja soalnya yang mau pake juga emak saya yang gak terlalu biasa komputer, jadi saya bikin yang tombolnya gede gede sama gak banyak menu

ada beberapa halaman:
- daftar barang, buat tambah barang sama liat stok
- kasir, buat jualan, pilih barang masukin jumlah nanti totalnya keitung sendiri
- riwayat, buat liat udah pernah jual apa aja
- laporan harian, buat liat pemasukan hari ini berapa

abis itu saya tambahin login juga, soalnya kata temen saya kalo gak ada login nanti sapaun bisa ngutak ngatik stoknya, jadi sekarang harus masuk dulu baru bisa pake

usernamenya admin passwordnya admin123, ini masih default sih belum bisa ganti, tapi bisa diubah lewat environment variable

## cara jalanin

```
pip install -r requirements.txt
```

terus

```
python app.py
```

buka `http://127.0.0.1:5000`, nanti diminta login dulu

## yang saya pikirin waktunya bikin

kemarin emak saya sempet salah masukin stok, harusnya 10 malah jadi 100, untungnya langsung keliatan, dari situ saya jadi mikir kalo inputnya harus saya cek, jangan sampe bisa masukin angka minus atau huruf di kolom harga, soalnya kalo minus nanti itungannya kacau

terus soal login tadi, awalnya saya gak kepikiran, terus saya coba buka halamannya di browser lain eh ternyata bisa masuk tanpa login, dari situ saya baru nambahin, sekarang kalo coba buka /barang langsung dibalikin ke halaman login

query ke database saya pake tanda tanya, bukan digabung, kebiasaan aja sih tapi katanya lebih aman

## yang belum saya kerjain

- passwordnya masih default, belum ada halaman buat ganti
- belom ada barcode, masih ketik manual
- belom bisa cetak struk
- laporannya cuma harian, belom bulanan
- tampilannya masih jelek, saya gak bisa desain hehe

## yang saya pelajarin

yang paling nempel itu soal validasi input, awalnya saya pikir ah cuma kolom harga doang paling isinya angka semua, eh ternyata pas saya coba masukin huruf malah error aplikasinya, dari situ saya ngerti kenapa input dari user itu gak boleh langsung dipercaya

terus saya juga jadi ngerti kenapa sqlite dipake kalo aplikasinya kecil, soalnya gampang banget, tinggal bikin file, gak perlu install server database

yang terakhir soal login tadi, saya baru ngerti kalo halaman yang keliatan aman bisa jadi bocor kalo gak dicek satu satu, saya hampir aja gak sadar

masih belajar btw, kalo ada yang salah mohon dikoreksi
