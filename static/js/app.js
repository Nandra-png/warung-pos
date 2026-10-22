/* ==========================================================================
   Warung Pos - app.js
   Vanilla JS. Semua helper UI (tanpa framework).
   Fungsi backend TIDAK diubah: tetap memakai endpoint yang sudah ada.
   ========================================================================== */
(function () {
  'use strict';

  /* ---------------------------- Util angka ---------------------------- */
  const fmt = new Intl.NumberFormat('id-ID');

  function rupiah(n) {
    return 'Rp ' + fmt.format(Math.round(Number(n) || 0));
  }

  function angka(str) {
    return parseInt(String(str == null ? '' : str).replace(/[^\d]/g, ''), 10) || 0;
  }

  /* ---------------------------- Toast ---------------------------- */
  const ICON = {
    ok:   '<path d="M20 6 9 17l-5-5"/>',
    err:  '<circle cx="12" cy="12" r="9"/><path d="M12 7.5v5.5"/><path d="M12 16.5h.01"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5"/><path d="M12 7.8h.01"/>'
  };

  function toast(msg, tipe) {
    const wrap = document.getElementById('toastWrap');
    if (!wrap) { return; }
    const t = tipe || 'info';
    const el = document.createElement('div');
    el.className = 'toast ' + (t === 'success' ? 'ok' : t === 'error' ? 'err' : 'info');
    el.setAttribute('role', 'status');
    el.innerHTML =
      '<span class="dot-ico"><svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor"' +
      ' stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">' +
      (ICON[t === 'success' ? 'ok' : t === 'error' ? 'err' : 'info']) + '</svg></span>' +
      '<span class="msg"></span>' +
      '<button class="x" type="button" aria-label="Tutup notifikasi">' +
      '<svg class="ico sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"' +
      ' stroke-linecap="round" stroke-linejoin="round"><path d="M6 6l12 12M18 6 6 18"/></svg></button>';
    el.querySelector('.msg').textContent = msg;
    wrap.appendChild(el);

    const tutup = () => {
      el.classList.add('out');
      setTimeout(() => el.remove(), 190);
    };
    el.querySelector('.x').addEventListener('click', tutup);
    setTimeout(tutup, 4200);
  }

  /* ---------------------------- Modal / Drawer ---------------------------- */
  function buka(el) {
    if (!el) { return; }
    el.classList.remove('hidden');
    el.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    const f = el.querySelector('input, button, select, textarea, a[href]');
    if (f) { setTimeout(() => f.focus(), 80); }
    el.setAttribute('tabindex', '-1');
    el.focus();
  }

  function tutup(el) {
    if (!el) { return; }
    el.classList.add('hidden');
    el.setAttribute('aria-hidden', 'true');
    if (!document.querySelector('.modal:not(.hidden), .drawer:not(.hidden)')) {
      document.body.style.overflow = '';
    }
  }

  function ikatModal(selector) {
    document.querySelectorAll(selector).forEach((m) => {
      if (m.dataset.ikat === '1') { return; }
      m.dataset.ikat = '1';
      m.addEventListener('click', (e) => { if (e.target === m) { tutup(m); } });
      m.querySelectorAll('[data-tutup]').forEach((b) => {
        b.addEventListener('click', () => tutup(m));
      });
    });
  }

  /* ---------------------------- Tema ---------------------------- */
  function setTema(t) {
    document.documentElement.setAttribute('data-theme', t);
    try { localStorage.setItem('wp-theme', t); } catch (e) {}
    document.querySelectorAll('[data-theme-set]').forEach((b) => {
      b.classList.toggle('active', b.dataset.themeSet === t);
    });
  }

  function temaSekarang() {
    return document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
  }

  function initTema() {
    setTema(temaSekarang());
    document.querySelectorAll('[data-theme-set]').forEach((b) => {
      b.addEventListener('click', () => setTema(b.dataset.themeSet));
    });
    document.querySelectorAll('[data-theme-cycle]').forEach((b) => {
      b.addEventListener('click', () => setTema(temaSekarang() === 'dark' ? 'light' : 'dark'));
    });
  }

  /* ---------------------------- Global diklik ---------------------------- */
  function initGlobal() {
    // Ctrl/Cmd + K -> fokus pencarian
    document.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        const s = document.getElementById('globalSearch') || document.getElementById('cariBarang');
        if (s) { s.focus(); s.select(); }
      }
      if (e.key === 'Escape') {
        document.querySelectorAll('.modal:not(.hidden), .drawer:not(.hidden)')
          .forEach((m) => tutup(m));
      }
    });

    // data-toast -> tombol yang cuma memberi info
    document.querySelectorAll('[data-toast]').forEach((b) => {
      b.addEventListener('click', () => toast(b.dataset.toast, 'info'));
    });

    document.querySelectorAll('[data-help]').forEach((b) => {
      b.addEventListener('click', () => toast(
        'Panduan singkat: isi data di halaman Barang, jualan di Kasir, cek hasil di Riwayat dan Laporan.',
        'info'));
    });

    // Tombol topbar: Notifikasi, Ekspor, Catatan
    const notif = document.getElementById('btnNotif');
    if (notif) {
      notif.addEventListener('click', () => toast(notif.getAttribute('aria-label'), 'info'));
    }

    const bagikan = document.getElementById('btnBagikan');
    if (bagikan) {
      bagikan.addEventListener('click', async () => {
        // Tanpa endpoint baru: ekspor CSV dilakukan di halaman Laporan.
        const sudahDiLaporan = /\/laporan/.test(location.pathname);
        const tombolEkspor = document.getElementById('btnEkspor');
        if (tombolEkspor) { tombolEkspor.click(); return; }
        if (navigator.share) {
          try {
            await navigator.share({ title: 'Warung Pos', url: location.origin + '/laporan' });
            return;
          } catch (e) { /* user batal, lanjut ke salin tautan */ }
        }
        try {
          await navigator.clipboard.writeText(location.origin + '/laporan');
          toast(sudahDiLaporan ? 'Tautan laporan disalin.' : 'Tautan laporan disalin.', 'success');
        } catch (e) {
          toast('Buka halaman Laporan untuk mengekspor CSV.', 'info');
        }
      });
    }

    const catatan = document.getElementById('btnCatatan');
    if (catatan) {
      catatan.addEventListener('click', () => {
        const p = document.getElementById('cartPanel');
        if (p) { p.classList.add('open'); document.getElementById('cartBackdrop')?.classList.remove('hidden'); return; }
        const d = document.getElementById('trxDrawer');
        if (d) { WP.buka(d); document.getElementById('trxBackdrop')?.classList.remove('hidden'); return; }
        toast('Catatan transaksi diisi di halaman Kasir, kolom "Catatan (opsional)".', 'info');
      });
    }

    // Konfirmasi untuk form hapus (ganti confirm bawaan yang jelek)
    document.querySelectorAll('form[data-konfirmasi]').forEach((f) => {
      f.addEventListener('submit', (e) => {
        if (f.dataset.oke === '1') { return; }
        e.preventDefault();
        if (window.confirm(f.dataset.konfirmasi)) {
          f.dataset.oke = '1';
          f.submit();
        }
      });
    });

    // Drawer / modal yang sudah ada di HTML
    ikatModal('.modal, .drawer');
  }

  /* ---------------------------- Skeleton sementara ---------------------------- */
  function skeleton(container, jumlah, cls) {
    if (!container) { return; }
    let html = '';
    for (let i = 0; i < (jumlah || 6); i++) {
      html += '<div class="skeleton ' + (cls || 'sk-card') + '"></div>';
    }
    container.innerHTML = html;
  }

  /* ---------------------------- Keranjang (dipakai halaman kasir) ---------------------------- */
  const WP = {
    rupiah, angka, toast, buka, tutup, ikatModal, setTema, temaSekarang,
    skeleton, fmt
  };

  document.addEventListener('DOMContentLoaded', () => {
    initTema();
    initGlobal();
  });

  // jalan juga kalau script dimuat setelah DOM siap
  if (document.readyState !== 'loading') {
    initTema();
    initGlobal();
  }

  window.WP = WP;
})();
