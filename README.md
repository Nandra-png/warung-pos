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
- basic styling
