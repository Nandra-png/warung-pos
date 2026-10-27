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

  // Setiap orb punya <g class="orb-rays"> dan <circle class="orb-bite">.
  // Keadaan animasinya ditentukan class .is-dark pada TOMBOL, bukan data-theme,
  // supaya ikon bisa berubah lebih dulu sebelum palet halaman berganti.
  function sinkronOrb(t) {
    const gelap = t === 'dark';
    document.querySelectorAll('[data-theme-cycle], [data-theme-set]').forEach((b) => {
      b.classList.toggle('is-dark', gelap);
      if (b.hasAttribute('role') && b.getAttribute('role') === 'switch') {
        b.setAttribute('aria-checked', gelap ? 'true' : 'false');
      }
      b.classList.toggle('active', b.dataset.themeSet === t);
      b.setAttribute('aria-label', gelap ? 'Ganti ke tema terang' : 'Ganti ke tema gelap');
      b.setAttribute('title', gelap ? 'Ganti ke tema terang' : 'Ganti ke tema gelap');
    });
    const meta = document.querySelector('meta[name="color-scheme"]');
    if (meta) { meta.setAttribute('content', gelap ? 'dark light' : 'light dark'); }
  }

  function terapkanTema(t) {
    document.documentElement.setAttribute('data-theme', t);
    try { localStorage.setItem('wp-theme', t); } catch (e) {}
    sinkronOrb(t);
  }

  const kurangiGerak = () =>
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // true selama animasi ganti tema berjalan. Dipakai supaya kejadian lain
  // (mis. pageshow) tidak menimpa ikon orb di tengah animasi.
  let temaAnimasiJalan = false;

  // Titik asal animasi: tengah tombol yang diklik. --x/--y dipakai clip-path CSS.
  function titikAsal(el) {
    const b = el && el.getBoundingClientRect ? el.getBoundingClientRect() : null;
    const r = document.documentElement;
    r.style.setProperty('--x', ((b ? b.left + b.width / 2 : window.innerWidth / 2)) + 'px');
    r.style.setProperty('--y', ((b ? b.top + b.height / 2 : window.innerHeight)) + 'px');
  }

  const tunggu = (ms) => new Promise((r) => setTimeout(r, ms));

  /* Kumpulkan animasi KEYFRAME di dalam sebuah elemen, termasuk anak-anaknya.
     getAnimations() pada induk saja tidak cukup: div panggung hanya punya
     transisi (opacity), sedangkan animasi aslinya menempel pada elemen SVG
     di dalamnya. Transisi disaring keluar lewat animationName. */
  function animasiKeyframe(el) {
    const semua = [];
    const kumpul = (node) => {
      if (!node.getAnimations) { return; }
      semua.push(...node.getAnimations());
      if (node.querySelectorAll) { node.querySelectorAll('*').forEach(kumpul); }
    };
    kumpul(el);
    return semua.filter((a) => a.animationName && a.animationName !== 'none');
  }

  // Tunggu sampai semua animasi keyframe di dalam elemen selesai.
  // animationend tidak dipakai: kalau elemen keburu disembunyikan, kejadian itu
  // bisa tidak datang. batas waktu tetap ada sebagai pengaman terakhir.
  function tungguAnimasi(el, batas) {
    const daftar = animasiKeyframe(el);
    if (!daftar.length) { return tunggu(batas); }
    return Promise.race([
      Promise.all(daftar.map((a) => a.finished.catch(() => {}))),
      tunggu(batas),
    ]);
  }

  // Lepas class animasi dengan memaksa reflow, supaya bisa dipicu ulang
  // berturut-turut.
  function resetAnimasi(el, kelas) {
    el.classList.remove(...kelas, 'on', 'pudar');
    void el.offsetWidth;
  }

  /* -------------------------------------------------------------------------
     Urutan animasi ganti tema. Tiga babak, sesuai permintaan:

       1. TIRAI MASUK   blok warna tema TUJUAN menyebar dari tombol yang diklik
                        sampai menutupi penuh layar. Tepinya buram lalu menajam.
                        Warnanya = warna latar tema tujuan, jadi layar sudah
                        berwarna tema baru saat tertutup penuh.
       2. PANGGUNG      di tengah layar orb besar tampil: matahari tenggelam
                        dan berubah jadi bulan SABIT (bentuk sabit dibuat dengan
                        <mask> dua lingkaran, bukan bulat bolong), atau
                        kebalikannya saat kembali ke terang.
                        Palet ditukar di TENGAH babak ini, saat layar masih
                        tertutup penuh, jadi pergantiannya tidak terlihat.
       3. TIRAI KELUAR  blok yang sama diambil dari TITIK YANG SAMA, jadi tidak
                        ada sambungan yang kelihatan. Orb ikut hilang dengan
                        redup + kabur.

     Kalau browser minta kurangi gerak, semua dilewati: tema langsung ganti.
     ------------------------------------------------------------------------- */
  async function gantiTema(t, tombol) {
    if (t === temaSekarang()) { return; }
    // Klik kedua saat animasi masih jalan harus diabaikan. Kalau tidak, dua
    // rangkaian animasi saling menimpa dan layar bisa ditinggal tertutup tirai.
    if (temaAnimasiJalan) { return; }
    const gelap = t === 'dark';

    if (kurangiGerak()) { terapkanTema(t); return; }

    const tirai = document.getElementById('themeWipe');
    const panggung = document.getElementById('temaPanggung');
    if (!tirai || !panggung) { terapkanTema(t); return; }

    titikAsal(tombol);
    // warna tirai = warna latar tema TUJUAN, jadi pergantian palet tidak terlihat.
    // Nilainya harus sama persis dengan --bg-app di tiap tema (lihat :root dan
    // [data-theme="dark"] di style.css). Dibaca dari CSS variable saat itu juga
    // tidak bisa: saat tirai masuk, tema masih yang LAMA.
    tirai.style.setProperty('--wipe-bg', gelap ? '#0F1115' : '#F5F6FA');

    temaAnimasiJalan = true;
    // ikon kecil di tombol sudah mulai berubah sejak sekarang
    sinkronOrb(t);

    try {
      // ---- babak 1: tirai masuk ----
      resetAnimasi(tirai, ['masuk', 'keluar']);
      tirai.classList.add('masuk', 'on');
      await tungguAnimasi(tirai, 900);

      // ---- babak 2: panggung orb di tengah, palet ditukar di tengahnya ----
      resetAnimasi(panggung, ['ke-gelap', 'ke-terang']);
      panggung.classList.add(gelap ? 'ke-gelap' : 'ke-terang', 'on');
      await tunggu(480);
      terapkanTema(t);              // layar masih tertutup penuh, jadi tidak terlihat
      await tungguAnimasi(panggung, 1700);

      // orb hilang dengan redup + kabur
      panggung.classList.add('pudar');
      await tunggu(300);

      // ---- babak 3: tirai keluar dari titik yang sama ----
      tirai.classList.remove('masuk');
      tirai.classList.add('keluar');
      await tungguAnimasi(tirai, 900);
    } finally {
      // apa pun yang terjadi, layar tidak boleh ditinggal tertutup
      resetAnimasi(panggung, ['ke-gelap', 'ke-terang']);
      resetAnimasi(tirai, ['masuk', 'keluar']);
      tirai.style.removeProperty('--wipe-bg');
      terapkanTema(t);
      temaAnimasiJalan = false;
    }
  }

  function setTema(t, tombol) {
    if (!tombol) { terapkanTema(t); return; }
    gantiTema(t, tombol);
  }

  function temaSekarang() {
    return document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
  }

  function initTema() {
    sinkronOrb(temaSekarang());

    document.querySelectorAll('[data-theme-set]').forEach((b) => {
      b.addEventListener('click', () => gantiTema(b.dataset.themeSet, b));
    });
    document.querySelectorAll('[data-theme-cycle]').forEach((b) => {
      b.addEventListener('click', () => {
        gantiTema(temaSekarang() === 'dark' ? 'light' : 'dark', b);
      });
    });

    // Halaman dipulihkan dari cache (tombol kembali browser): pastikan ikon orb
    // cocok lagi dengan tema aktif. Hanya saat persisted, karena pageshow juga
    // menyala pada muat pertama dan itu bisa menimpa ikon di tengah animasi.
    window.addEventListener('pageshow', (e) => {
      if (e.persisted && !temaAnimasiJalan) { sinkronOrb(temaSekarang()); }
    });

    // class no-transition hanya untuk bebas-kedip saat pertama render
    requestAnimationFrame(() => {
      requestAnimationFrame(() => document.documentElement.classList.remove('no-transition'));
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
