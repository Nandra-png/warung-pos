/* Uji animasi ganti tema dengan JAM NYATA lewat CDP.
   Chrome headless + --virtual-time-budget membuat animasi CSS tidak pernah
   selesai, jadi semua pengukuran berbasis waktu harus pakai jam asli.
   Skrip ini menyalakan Chrome sendiri, menyambung lewat WebSocket native
   Node 24, lalu membaca keadaan DOM pada titik-titik waktu nyata.

   Pakai: node tools/verify_animasi.mjs [url]
*/
import { spawn } from 'node:child_process';
import { existsSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import zlib from 'node:zlib';

/* ---------------------------------------------------------------------------
   Pembaca PNG seadanya, cukup untuk screenshot Chrome (8-bit RGB/RGBA).
   Dipakai supaya bentuk sabit bisa dibuktikan dari PIXEL, bukan cuma dari
   angka transform. Tanpa pustaka luar: byte-nya dibaca langsung.
   --------------------------------------------------------------------------- */
function bacaPng(buf) {
  let p = 8, w = 0, h = 0, ct = 0;
  const idat = [];
  while (p < buf.length) {
    const len = buf.readUInt32BE(p);
    const tipe = buf.toString('ascii', p + 4, p + 8);
    const isi = buf.subarray(p + 8, p + 8 + len);
    if (tipe === 'IHDR') { w = isi.readUInt32BE(0); h = isi.readUInt32BE(4); ct = isi[9]; }
    else if (tipe === 'IDAT') { idat.push(isi); }
    else if (tipe === 'IEND') { break; }
    p += 12 + len;
  }
  const bpp = ct === 6 ? 4 : ct === 2 ? 3 : ct === 0 ? 1 : 4;
  const mentah = zlib.inflateSync(Buffer.concat(idat));
  const lebarBaris = w * bpp;
  const keluar = Buffer.alloc(h * lebarBaris);
  let pos = 0;
  for (let y = 0; y < h; y++) {
    const filter = mentah[pos++];
    const baris = mentah.subarray(pos, pos + lebarBaris);
    pos += lebarBaris;
    const kini = keluar.subarray(y * lebarBaris, (y + 1) * lebarBaris);
    const atas = y > 0 ? keluar.subarray((y - 1) * lebarBaris, y * lebarBaris) : null;
    for (let i = 0; i < lebarBaris; i++) {
      const a = i >= bpp ? kini[i - bpp] : 0;
      const b = atas ? atas[i] : 0;
      const c = (atas && i >= bpp) ? atas[i - bpp] : 0;
      let v = baris[i];
      if (filter === 1) { v += a; }
      else if (filter === 2) { v += b; }
      else if (filter === 3) { v += (a + b) >> 1; }
      else if (filter === 4) {
        const pa = Math.abs(b - c), pb = Math.abs(a - c), pc = Math.abs(a + b - 2 * c);
        v += (pa <= pb && pa <= pc) ? a : (pb <= pc ? b : c);
      }
      kini[i] = v & 0xff;
    }
  }
  return { w, h, bpp, data: keluar };
}

function piksel(img, x, y) {
  const i = (y * img.w + x) * img.bpp;
  return [img.data[i], img.data[i + 1], img.data[i + 2]];
}

/* Hitung berapa persen lingkaran (cakram) yang tertutup badan orb.
   Latar diambil dari sudut-sudut kotak pembatas (pasti di luar cakram), lalu
   piksel yang JAUH berbeda dari latar dihitung sebagai badan orb.
   Cara ini andal di tema terang maupun gelap, dan untuk matahari (merah)
   maupun bulan (krem). Angka inilah yang membedakan SABIT dari BOLONG:
     bolong (potongan di tengah) -> jauh lebih kecil
     sabit                       -> sekitar separuh
     purnama                     -> hampir penuh */
function bagianTerang(img, cx, cy, r) {
  const x0 = Math.max(0, Math.floor(cx - r)), x1 = Math.min(img.w - 1, Math.ceil(cx + r));
  const y0 = Math.max(0, Math.floor(cy - r)), y1 = Math.min(img.h - 1, Math.ceil(cy + r));
  // latar: rata-rata empat sudut kotak pembatas
  const sudut = [[x0, y0], [x1, y0], [x0, y1], [x1, y1]].map(([x, y]) => piksel(img, x, y));
  const latar = [0, 1, 2].map((i) => sudut.reduce((s, p) => s + p[i], 0) / sudut.length);
  let dalam = 0, orb = 0;
  for (let y = y0; y <= y1; y++) {
    for (let x = x0; x <= x1; x++) {
      if ((x - cx) ** 2 + (y - cy) ** 2 > r * r) { continue; }
      dalam++;
      const [R, G, B] = piksel(img, x, y);
      const jarak = Math.abs(R - latar[0]) + Math.abs(G - latar[1]) + Math.abs(B - latar[2]);
      if (jarak > 90) { orb++; }
    }
  }
  return dalam ? orb / dalam : 0;
}

const URL_APP = process.argv[2] || 'http://127.0.0.1:5000/kasir';
const PORT = 9331;

const CHROME = [
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
  'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
].find((p) => existsSync(p));

if (!CHROME) { console.error('Tidak ada Chrome/Edge'); process.exit(2); }

const profil = mkdtempSync(join(tmpdir(), 'wp-cdp-'));
const chrome = spawn(CHROME, [
  '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--no-sandbox', `--remote-debugging-port=${PORT}`, `--user-data-dir=${profil}`,
  '--window-size=1280,900', 'about:blank',
], { stdio: 'ignore' });

const tunggu = (ms) => new Promise((r) => setTimeout(r, ms));

async function targetWs() {
  for (let i = 0; i < 60; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json/list`);
      const list = await r.json();
      const page = list.find((t) => t.type === 'page' && t.webSocketDebuggerUrl);
      if (page) { return page.webSocketDebuggerUrl; }
    } catch { /* belum siap */ }
    await tunggu(250);
  }
  throw new Error('CDP tidak siap');
}

class Cdp {
  constructor(url) {
    this.ws = new WebSocket(url);
    this.id = 0;
    this.tunggu = new Map();
    this.siap = new Promise((res, rej) => {
      this.ws.addEventListener('open', res);
      this.ws.addEventListener('error', rej);
    });
    this.ws.addEventListener('message', (ev) => {
      const m = JSON.parse(ev.data);
      if (m.id && this.tunggu.has(m.id)) {
        const { res, rej } = this.tunggu.get(m.id);
        this.tunggu.delete(m.id);
        m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result);
      }
    });
  }
  async kirim(method, params = {}) {
    await this.siap;
    const id = ++this.id;
    const p = new Promise((res, rej) => this.tunggu.set(id, { res, rej }));
    this.ws.send(JSON.stringify({ id, method, params }));
    return p;
  }
  async eval(expr) {
    const r = await this.kirim('Runtime.evaluate', {
      expression: expr, returnByValue: true, awaitPromise: true,
    });
    if (r.exceptionDetails) {
      throw new Error(r.exceptionDetails.exception?.description || 'galat eval');
    }
    return r.result.value;
  }
  async layar() {
    const r = await this.kirim('Page.captureScreenshot', { format: 'png' });
    return r.data;   // base64
  }
  tutup() { try { this.ws.close(); } catch {} }
}

// ---- probe: dijalankan di halaman, mengembalikan keadaan animasi terkini ----
const PROBE = `(() => {
  const g = (id) => document.getElementById(id);
  const tirai = g('themeWipe'), pang = g('temaPanggung');
  const cs = (el) => el ? getComputedStyle(el) : null;
  const anim = (el) => {
    const semua = [];
    const kumpul = (n) => { if (n.getAnimations) { semua.push(...n.getAnimations()); }
      if (n.querySelectorAll) { n.querySelectorAll('*').forEach(kumpul); } };
    if (el) { kumpul(el); }
    return semua.filter((a) => a.animationName && a.animationName !== 'none')
      .map((a) => a.animationName + ':' + a.playState);
  };
  const op = (sel) => {
    const el = pang ? pang.querySelector(sel) : null;
    return el ? parseFloat(cs(el).opacity).toFixed(2) : null;
  };
  const tf = (sel) => {
    const el = pang ? pang.querySelector(sel) : null;
    if (!el) return null;
    const t = cs(el).transform;
    if (!t || t === 'none') return 'none';
    try { const m = new DOMMatrixReadOnly(t); return [m.a, Math.round(m.e), Math.round(m.f)].join(','); }
    catch { return 'err'; }
  };
  return JSON.stringify({
    tema: document.documentElement.getAttribute('data-theme'),
    tiraiKelas: tirai ? tirai.className : null,
    tiraiBg: cs(tirai) ? cs(tirai).backgroundColor : null,
    tiraiTerlihat: cs(tirai) ? cs(tirai).visibility : null,
    tiraiFilter: cs(tirai) ? cs(tirai).filter : null,
    tiraiAnim: anim(tirai),
    pangKelas: pang ? pang.className : null,
    pangTerlihat: cs(pang) ? cs(pang).visibility : null,
    pangOpasitas: cs(pang) ? cs(pang).opacity : null,
    pangAnim: anim(pang),
    matahariOp: op('.pg-matahari'),
    bulanOp: op('.pg-bulan'),
    bintangOp: op('.pg-bintang'),
    sinarOp: op('.pg-sinar'),
    bulanTf: tf('.pg-bulan'),
    cutTf: tf('.pg-bulan-cut'),
    x: cs(document.documentElement).getPropertyValue('--x').trim(),
    y: cs(document.documentElement).getPropertyValue('--y').trim(),
    orbIsDark: !!document.querySelector('.tema-orb.is-dark'),
    ariaChecked: (document.querySelector('[data-theme-cycle]') || {}).getAttribute
      ? document.querySelector('[data-theme-cycle]').getAttribute('aria-checked') : null,
    tersimpan: (() => { try { return localStorage.getItem('wp-theme'); } catch { return null; } })(),
  });
})()`;

const hasil = [];
function cek(nama, ok, info = '') {
  hasil.push({ nama, ok: !!ok, info });
  console.log(`  [${ok ? 'OK ' : 'GAGAL'}] ${nama}${info ? '  -> ' + info : ''}`);
}

async function jalankan() {
  const cdp = new Cdp(await targetWs());
  await cdp.kirim('Page.enable');
  await cdp.kirim('Runtime.enable');

  // login dulu supaya /kasir tidak redirect
  await cdp.kirim('Page.navigate', { url: new URL('/login', URL_APP).href });
  await tunggu(2500);
  await cdp.eval(`(() => {
    const u = document.querySelector('input[name="username"]');
    const p = document.querySelector('input[name="password"]');
    const f = u && u.form;
    if (u) u.value = 'admin'; if (p) p.value = 'admin123';
    if (f) f.submit();
    return true;
  })()`);
  await tunggu(2200);

  await cdp.kirim('Page.navigate', { url: URL_APP });
  await tunggu(2500);
  // pastikan mulai dari tema terang
  await cdp.eval(`localStorage.setItem('wp-theme','light'); location.reload(); true`);
  await tunggu(2600);

  const baca = () => cdp.eval(PROBE).then(JSON.parse);

  const awal = await baca();
  console.log('\n=== AWAL ===');
  console.log('  ', JSON.stringify(awal));

  cek('awal: tema terang', awal.tema === 'light', awal.tema);
  cek('awal: tirai belum tampil', awal.tiraiTerlihat === 'hidden', awal.tiraiTerlihat);
  cek('awal: panggung belum tampil', awal.pangTerlihat === 'hidden', awal.pangTerlihat);
  cek('awal: matahari tampak penuh', awal.matahariOp === '1.00', awal.matahariOp);
  cek('awal: bulan tersembunyi', awal.bulanOp === '0.00', awal.bulanOp);

  // ---- klik tombol tema -> ukur di sepanjang waktu (jam nyata) ----
  const t0 = Date.now();
  const jejak = [];
  await cdp.eval(`(() => {
    const b = [...document.querySelectorAll('[data-theme-cycle]')]
      .find(x => x.getBoundingClientRect().width > 0);
    window.__t0 = performance.now();
    b.click();
    return true;
  })()`);

  // sampel rapat pada ~4 detik pertama: cukup untuk ketiga babak
  const targetMs = [0, 120, 250, 400, 550, 700, 900, 1100, 1300, 1500, 1700, 2000, 2300,
    2600, 2900, 3200, 3500, 3900, 4300];
  for (const ms of targetMs) {
    const selisih = ms - (Date.now() - t0);
    if (selisih > 0) await tunggu(selisih);
    jejak.push({ ms, ...(await baca()) });
  }

  console.log('\n=== JEJAK (jam nyata, ms sejak klik) ===');
  for (const j of jejak) {
    console.log(`  ${String(j.ms).padStart(4)}ms  tema=${String(j.tema).padEnd(5)}` +
      ` tirai=${String(j.tiraiKelas).padEnd(20)}${String(j.tiraiTerlihat).padEnd(8)}` +
      ` pang=${String(j.pangKelas).padEnd(14)}${String(j.pangTerlihat).padEnd(8)}` +
      ` matahari=${j.matahariOp} bulan=${j.bulanOp} cut=${j.cutTf}`);
  }

  // ---------- penilaian ----------
  console.log('\n=== EVALUASI ===');

  // 1. babak 1: tirai masuk dari tombol, berwarna tujuan (gelap)
  const adaMasuk = jejak.some((j) => j.tiraiKelas.includes('masuk') && j.tiraiAnim.some((a) => a.startsWith('sebar-tirai-masuk')));
  cek('babak 1: tirai masuk beranimasi (sebar-tirai-masuk)', adaMasuk);
  cek('babak 1: tirai berwarna tema tujuan (gelap)', jejak.some((j) => j.tiraiBg === 'rgb(15, 17, 21)'),
    jejak.find((j) => j.tiraiBg)?.tiraiBg);
  cek('babak 1: tepi tirai sempat buram', jejak.some((j) => j.tiraiFilter && j.tiraiFilter !== 'none'),
    jejak.find((j) => j.tiraiFilter)?.tiraiFilter);
  cek('babak 1: titik asal dari tombol (--x terisi)', jejak.every((j) => /px$/.test(j.x)), jejak[0].x);

  // 2. babak 2: panggung orb muncul, matahari tenggelam, bulan naik
  const adaPanggung = jejak.some((j) => j.pangKelas.includes('ke-gelap') && j.pangTerlihat === 'visible');
  cek('babak 2: panggung orb tampil di tengah', adaPanggung);
  cek('babak 2: animasi panggung jalan', jejak.some((j) => j.pangAnim.length > 0), JSON.stringify(jejak.find((j) => j.pangAnim.length)?.pangAnim));
  const matahariTurun = jejak.some((j) => Number(j.matahariOp) < 0.9 && Number(j.matahariOp) > 0.02);
  cek('babak 2: matahari tenggelam (opasitas turun)', matahariTurun,
    jejak.map((j) => j.matahariOp).join(' '));
  cek('babak 2: bulan naik menggantikan', jejak.some((j) => Number(j.bulanOp) > 0.5),
    jejak.map((j) => j.bulanOp).join(' '));
  // potongan bergeser sehingga bulan berubah dari purnama ke sabit.
  // Bandingkan nilai AWAL vs nilai yang paling jauh bergeser (bukan yang terakhir,
  // karena setelah animasi selesai potongan sudah kembali ke posisi semula).
  const geseranCut = jejak.map((j) => j.cutTf).filter((v) => v && v !== 'none');
  const palingJauh = geseranCut.reduce((a, b) => {
    const d = (v) => Math.abs(Number(v.split(',')[1] || 0)) + Math.abs(Number(v.split(',')[2] || 0));
    return d(b) > d(a) ? b : a;
  }, geseranCut[0] || 'none');
  cek('babak 2: potongan bergeser (bulan jadi sabit)', geseranCut[0] !== palingJauh,
    `${geseranCut[0]} -> ${palingJauh}`);
  cek('babak 2: bintang menyala saat gelap', jejak.some((j) => Number(j.bintangOp) > 0.5),
    jejak.map((j) => j.bintangOp).join(' '));

  // ---------- bukti PIXEL: bentuknya sabit, bukan bolong ----------
  // Animasi sengaja TIDAK dipakai di sini. Dua keadaan geometri diset langsung
  // lewat inline style, jadi hasilnya deterministik dan tidak balapan dengan jam.
  // Diukur dari screenshot: berapa persen cakram orb yang tertutup warna terang.
  //   potongan di tengah cakram  -> ~1 persen   (BOLONG, ini yang salah)
  //   potongan bergeser masuk    -> ~50 persen  (SABIT, ini yang benar)
  //   potongan jauh di luar      -> ~99 persen  (purnama)
  const geometri = await cdp.eval(`(() => {
    const p = document.getElementById('temaPanggung');
    const b = p.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    return JSON.stringify({ cx: (b.left + b.width / 2) * dpr, cy: (b.top + b.height / 2) * dpr,
                            r: (b.width / 2) * dpr * (22 / 60), dpr });
  })()`).then(JSON.parse);

  // halaman dijaga GELAP: latar gelap membuat badan orb menonjol, hitungan bersih
  const setBentuk = (geser) => cdp.eval(`(() => {
    document.documentElement.setAttribute('data-theme','dark');
    document.querySelectorAll('[data-theme-cycle]').forEach(b => b.classList.add('is-dark'));
    const p = document.getElementById('temaPanggung');
    p.className = 'tema-panggung on';
    p.style.opacity = '1'; p.style.filter = 'none';
    const q = (s) => p.querySelector(s);
    q('.pg-bulan').style.opacity = '1';
    q('.pg-matahari').style.opacity = '0';
    q('.pg-bintang').style.opacity = '0';
    q('.pg-bulan-cut').style.transform = ${JSON.stringify(geser)};
    return true;
  })()`);

  async function ukurBentuk(label) {
    await tunggu(140);
    const png = Buffer.from(await cdp.layar(), 'base64');
    const img = bacaPng(png);
    const bagian = bagianTerang(img, geometri.cx, geometri.cy, geometri.r);
    const tengah = piksel(img, Math.round(geometri.cx), Math.round(geometri.cy));
    const potongan = piksel(img, Math.round(geometri.cx + geometri.r * 0.6),
                            Math.round(geometri.cy - geometri.r * 0.6));
    const mt = await cdp.eval(`(() => {
      const p = document.getElementById('temaPanggung');
      const g = (s) => { const e = p.querySelector(s); return e ? getComputedStyle(e).transform + '|op=' + getComputedStyle(e).opacity : '-'; };
      return [g('.pg-bulan-cut'), g('.pg-bulan'), g('.pg-matahari')].join(' ;; ');
    })()`);
    return { label, bagian, tengah, potongan, mt };
  }

  await setBentuk('translate(0px, 0px)');
  const bentukPurnama = await ukurBentuk('potongan di luar (purnama)');
  await setBentuk('translate(-36px, 36px)');   // titik akhir animasi
  const bentukSabit = await ukurBentuk('potongan masuk (sabit)');
  // keadaan salah, sengaja diukur sebagai pembanding: potongan tepat di pusat
  await setBentuk('translate(-46px, 46px)');
  const bentukBolong = await ukurBentuk('potongan di pusat (BOLONG)');

  console.log('\n=== BUKTI PIXEL: bagian cakram orb yang terang ===');
  for (const b of [bentukPurnama, bentukSabit, bentukBolong]) {
    console.log(`  ${b.label.padEnd(30)} ${(b.bagian * 100).toFixed(1)}%  ` +
      `tengah=${b.tengah} titik-potongan=${b.potongan}`);
    console.log(`      ${b.mt}`);
  }
  cek('piksel: potongan jauh = purnama (>85%)', bentukPurnama.bagian > 0.85,
    (bentukPurnama.bagian * 100).toFixed(1) + '%');
  cek('piksel: potongan masuk = SABIT (30-75%)',
    bentukSabit.bagian > 0.30 && bentukSabit.bagian < 0.75,
    (bentukSabit.bagian * 100).toFixed(1) + '%');
  // Bulan sabit harus JAUH lebih tebal dari keadaan bolong. Angka "bolong"
  // tidak nol karena tepi anti-alias + drop-shadow ikut terbaca.
  cek('piksel: sabit minimal 2x lebih tebal dari bolong',
    bentukSabit.bagian > bentukBolong.bagian * 2,
    `sabit ${(bentukSabit.bagian * 100).toFixed(1)}% vs bolong ${(bentukBolong.bagian * 100).toFixed(1)}%`);
  cek('piksel: cakram makin tertutup saat potongan masuk',
    bentukSabit.bagian < bentukPurnama.bagian - 0.15,
    `${(bentukPurnama.bagian * 100).toFixed(1)}% -> ${(bentukSabit.bagian * 100).toFixed(1)}%`);

  // bersihkan panggung setelah pengukuran pixel
  await cdp.eval(`(() => {
    const p = document.getElementById('temaPanggung');
    p.className = 'tema-panggung';
    p.style.opacity = ''; p.style.filter = '';
    ['.pg-bulan', '.pg-matahari', '.pg-bintang', '.pg-bulan-cut']
      .forEach((s) => { const el = p.querySelector(s); if (el) { el.style.opacity = ''; el.style.transform = ''; } });
    document.documentElement.setAttribute('data-theme','dark');
    document.querySelectorAll('[data-theme-cycle]').forEach(b => b.classList.add('is-dark'));
    return true;
  })()`);

  // ---------- bukti PIXEL: ikon orb KECIL juga sabit, bukan bolong ----------
  // Di sinilah bug aslinya: dulu potongan ditaruh tepat di pusat cakram,
  // jadi ikonnya tampak bolong. Sekarang diukur dari screenshot tombolnya.
  const geoKecil = await cdp.eval(`(() => {
    const b = [...document.querySelectorAll('[data-theme-cycle]')]
      .find(x => x.getBoundingClientRect().width > 0);
    const s = b.querySelector('.orb').getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const pxPerUnit = (s.width / 24) * dpr;   // viewBox orb kecil = 24
    return JSON.stringify({
      cx: (s.left + 12 * (s.width / 24)) * dpr,
      cy: (s.top + 12 * (s.height / 24)) * dpr,
      r: 6.07 * pxPerUnit * 0.86,             // 0.86: buang tepi anti-alias
      pxPerUnit, dpr,
    });
  })()`).then(JSON.parse);

  async function ukurOrbKecil(gelap) {
    await cdp.eval(`(() => {
      document.documentElement.setAttribute('data-theme','${gelap ? 'dark' : 'light'}');
      document.querySelectorAll('[data-theme-cycle]').forEach(b => b.classList.toggle('is-dark', ${gelap}));
      return true;
    })()`);
    await tunggu(700);   // beri waktu transisi orb selesai
    const png = Buffer.from(await cdp.layar(), 'base64');
    const img = bacaPng(png);
    return bagianTerang(img, geoKecil.cx, geoKecil.cy, geoKecil.r);
  }

  const orbKecilTerang = await ukurOrbKecil(false);
  const orbKecilGelap = await ukurOrbKecil(true);
  console.log('\n=== BUKTI PIXEL: ikon orb kecil ===');
  console.log(`  terang (matahari)  ${(orbKecilTerang * 100).toFixed(1)}%`);
  console.log(`  gelap  (bulan)     ${(orbKecilGelap * 100).toFixed(1)}%`);
  cek('piksel orb kecil: matahari tampak penuh (>80%)', orbKecilTerang > 0.80,
    (orbKecilTerang * 100).toFixed(1) + '%');
  cek('piksel orb kecil: bulan masih terlihat 30-75% (sabit, bukan bolong)',
    orbKecilGelap > 0.30 && orbKecilGelap < 0.75,
    (orbKecilGelap * 100).toFixed(1) + '%');

  // 3. palet ditukar saat tirai menutupi penuh
  const idxGelap = jejak.findIndex((j) => j.tema === 'dark');
  const idxTiraiMasukSelesai = jejak.findIndex((j) => j.tiraiKelas.includes('keluar'));
  cek('palet ditukar jadi gelap', idxGelap >= 0, `pada ms=${jejak[idxGelap]?.ms}`);
  cek('palet ditukar SEBELUM tirai keluar',
    idxGelap >= 0 && idxTiraiMasukSelesai >= 0 && idxGelap < idxTiraiMasukSelesai,
    `gelap@${jejak[idxGelap]?.ms}ms keluar@${jejak[idxTiraiMasukSelesai]?.ms}ms`);

  // 4. babak 3: tirai keluar, orb memudar
  cek('babak 3: tirai keluar beranimasi (push-tirai-keluar)',
    jejak.some((j) => j.tiraiKelas.includes('keluar') && j.tiraiAnim.some((a) => a.startsWith('push-tirai-keluar'))));
  cek('babak 3: orb memudar (pudar)', jejak.some((j) => j.pangKelas.includes('pudar')));

  const akhir = await baca();
  console.log('\n=== AKHIR ===');
  console.log('  ', JSON.stringify(akhir));
  cek('akhir: tema gelap', akhir.tema === 'dark', akhir.tema);
  cek('akhir: tirai sudah bersih', akhir.tiraiTerlihat === 'hidden' && !akhir.tiraiKelas.includes('on'), akhir.tiraiKelas);
  cek('akhir: panggung sudah bersih', akhir.pangTerlihat === 'hidden' && !akhir.pangKelas.includes('on'), akhir.pangKelas);
  cek('akhir: pilihan tersimpan', akhir.tersimpan === 'dark', akhir.tersimpan);
  cek('akhir: aria-checked true', akhir.ariaChecked === 'true', akhir.ariaChecked);
  cek('akhir: ikon tombol jadi gelap', akhir.orbIsDark === true, String(akhir.orbIsDark));

  // ---- klik balik ke terang ----
  // tunggu animasi pertama benar-benar selesai dulu (klik kedua saat masih
  // jalan akan diabaikan oleh penjaga temaAnimasiJalan).
  for (let i = 0; i < 40; i++) {
    const s = await baca();
    if (s.tiraiTerlihat === 'hidden' && s.pangTerlihat === 'hidden') { break; }
    await tunggu(200);
  }
  await cdp.eval(`(() => {
    const b = [...document.querySelectorAll('[data-theme-cycle]')]
      .find(x => x.getBoundingClientRect().width > 0);
    b.click(); return true;
  })()`);
  await tunggu(900);
  const balik = await baca();
  cek('arah terang: panggung dipicu arah ke-terang',
    balik.pangKelas.includes('ke-terang'),
    `kelas=${balik.pangKelas} tema=${balik.tema}`);
  await tunggu(3600);
  const terang = await baca();
  console.log('\n=== SETELAH BALIK KE TERANG ===');
  console.log('  ', JSON.stringify(terang));
  cek('akhir: tema terang lagi', terang.tema === 'light', terang.tema);
  cek('akhir: matahari kembali penuh', terang.matahariOp === '1.00', terang.matahariOp);
  cek('akhir: bulan tersembunyi lagi', terang.bulanOp === '0.00', terang.bulanOp);
  cek('akhir: layar tidak ditinggal tertutup', terang.tiraiTerlihat === 'hidden', terang.tiraiKelas);

  // ---- klik ganda cepat: layar TIDAK boleh tertinggal tertutup ----
  // Ini risiko terbesar dari animasi bertahap: dua rangkaian saling menimpa
  // dan tirai berhenti di tengah sehingga halaman tampak gelap/putih total.
  await cdp.eval(`(() => {
    const b = [...document.querySelectorAll('[data-theme-cycle]')]
      .find(x => x.getBoundingClientRect().width > 0);
    b.click(); b.click(); b.click();
    return true;
  })()`);
  await tunggu(6000);
  const ganda = await baca();
  console.log('\n=== SETELAH KLIK GANDA CEPAT ===');
  console.log('  ', JSON.stringify(ganda));
  cek('klik ganda: layar bersih (tidak tertinggal tertutup)',
    ganda.tiraiTerlihat === 'hidden' && !ganda.tiraiKelas.includes('on'),
    `tirai=${ganda.tiraiKelas} vis=${ganda.tiraiTerlihat}`);
  cek('klik ganda: panggung bersih',
    ganda.pangTerlihat === 'hidden' && !ganda.pangKelas.includes('on'), ganda.pangKelas);
  cek('klik ganda: tema berpindah tepat sekali (jadi gelap)',
    ganda.tema === 'dark', ganda.tema);
  cek('klik ganda: ikon orb cocok dengan tema',
    ganda.orbIsDark === (ganda.tema === 'dark'), `${ganda.orbIsDark} vs ${ganda.tema}`);

  cdp.tutup();
  const gagal = hasil.filter((h) => !h.ok);
  console.log(`\n${gagal.length === 0 ? 'SEMUA LULUS' : gagal.length + ' GAGAL'} (${hasil.length} cek)`);
  return gagal.length;
}

let kode = 1;
try {
  kode = await jalankan();
} catch (e) {
  console.error('GALAT:', e.message);
} finally {
  try { chrome.kill(); } catch {}
  await tunggu(300);
  try { rmSync(profil, { recursive: true, force: true }); } catch {}
}
process.exit(kode);
