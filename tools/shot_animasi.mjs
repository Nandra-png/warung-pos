/* Tangkap tangkapan layar tiga babak animasi + jalur reduced-motion.
   Dipakai untuk bukti nyata (bukan klaim): matahari, bulan sabit di tengah
   layar, dan hasil akhir setelah tema berganti.

   Pakai: node tools/shot_animasi.mjs [url] [dir-keluar]
*/
import { spawn } from 'node:child_process';
import { existsSync, mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const URL_APP = process.argv[2] || 'http://127.0.0.1:5000/kasir';
const OUT = process.argv[3] || join(tmpdir(), 'wp-animasi');
mkdirSync(OUT, { recursive: true });

const PORT = 9332;
const CHROME = [
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
  'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
].find((p) => existsSync(p));
if (!CHROME) { console.error('Tidak ada Chrome/Edge'); process.exit(2); }

const tunggu = (ms) => new Promise((r) => setTimeout(r, ms));
const profil = mkdtempSync(join(tmpdir(), 'wp-shot-'));

function args(extra = []) {
  return ['--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    '--no-sandbox', `--remote-debugging-port=${PORT}`, `--user-data-dir=${profil}`,
    '--window-size=1280,900', ...extra, 'about:blank'];
}

class Cdp {
  constructor(url) {
    this.ws = new WebSocket(url); this.id = 0; this.tunggu = new Map();
    this.siap = new Promise((res, rej) => {
      this.ws.addEventListener('open', res); this.ws.addEventListener('error', rej);
    });
    this.ws.addEventListener('message', (ev) => {
      const m = JSON.parse(ev.data);
      if (m.id && this.tunggu.has(m.id)) {
        const { res, rej } = this.tunggu.get(m.id); this.tunggu.delete(m.id);
        m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result);
      }
    });
  }
  async kirim(method, params = {}) {
    await this.siap; const id = ++this.id;
    const p = new Promise((res, rej) => this.tunggu.set(id, { res, rej }));
    this.ws.send(JSON.stringify({ id, method, params })); return p;
  }
  async eval(expr) {
    const r = await this.kirim('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
    if (r.exceptionDetails) { throw new Error(r.exceptionDetails.exception?.description || 'galat'); }
    return r.result.value;
  }
  async simpan(nama) {
    const r = await this.kirim('Page.captureScreenshot', { format: 'png' });
    const p = join(OUT, nama + '.png');
    writeFileSync(p, Buffer.from(r.data, 'base64'));
    return p;
  }
  tutup() { try { this.ws.close(); } catch {} }
}

async function targetWs() {
  for (let i = 0; i < 60; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json/list`);
      const page = (await r.json()).find((t) => t.type === 'page' && t.webSocketDebuggerUrl);
      if (page) { return page.webSocketDebuggerUrl; }
    } catch { /* belum siap */ }
    await tunggu(250);
  }
  throw new Error('CDP tidak siap');
}

const MAKSUD = process.argv[4] || 'tangkap';

let chrome;
let kode = 0;
try {
  chrome = spawn(CHROME, args(), { stdio: 'ignore' });
  const cdp = new Cdp(await targetWs());
  await cdp.kirim('Page.enable');
  await cdp.kirim('Runtime.enable');
  await cdp.kirim('Emulation.setDeviceMetricsOverride', {
    width: 1280, height: 860, deviceScaleFactor: 1, mobile: false,
  });

  await cdp.kirim('Page.navigate', { url: new URL('/login', URL_APP).href });
  await tunggu(2500);
  await cdp.eval(`(() => { const u=document.querySelector('input[name="username"]'),p=document.querySelector('input[name="password"]');
    if(u)u.value='admin'; if(p)p.value='admin123'; if(u&&u.form)u.form.submit(); return true; })()`);
  await tunggu(2200);

  await cdp.kirim('Page.navigate', { url: URL_APP });
  await tunggu(2600);
  await cdp.eval(`localStorage.setItem('wp-theme','light'); location.reload(); true`);
  await tunggu(2800);

  if (MAKSUD === 'reduced') {
    // jalur prefers-reduced-motion: tema harus langsung ganti, tanpa tirai
    // Emulasi media dipakai supaya benar-benar diuji, bukan diasumsikan.
    await cdp.kirim('Emulation.setEmulatedMedia', {
      features: [{ name: 'prefers-reduced-motion', value: 'reduce' }],
    });
    await tunggu(200);
    console.log('mode reduced-motion (via Emulation.setEmulatedMedia)');
    const a = await cdp.eval(`(() => {
      const b=[...document.querySelectorAll('[data-theme-cycle]')].find(x=>x.getBoundingClientRect().width>0);
      const tirai=document.getElementById('themeWipe');
      const cocok = matchMedia('(prefers-reduced-motion: reduce)').matches;
      b.click();
      const tiraiAnim = tirai.getAnimations().filter(x=>x.animationName&&x.animationName!=='none').length;
      return JSON.stringify({ mediaCocok: cocok,
        tema: document.documentElement.getAttribute('data-theme'),
        tiraiAnim, tiraiKelas: tirai.className,
        panggungDisplay: getComputedStyle(document.getElementById('temaPanggung')).display,
        panggungTerlihat: getComputedStyle(document.getElementById('temaPanggung')).visibility,
        tiraiTerlihat: getComputedStyle(tirai).visibility });
    })()`).then(JSON.parse);
    console.log(JSON.stringify(a, null, 2));
    await cdp.simpan('reduced-setelah-klik');
    cdp.tutup();
  } else {
    // tangkap tiga babak
    const jejak = [];
    await cdp.eval(`(() => { const b=[...document.querySelectorAll('[data-theme-cycle]')].find(x=>x.getBoundingClientRect().width>0);
      window.__t=performance.now(); b.click(); return true; })()`);
    // garis waktu nyata: tirai masuk 0-560, matahari 560-1180, bulan 1040-1600,
  // potongan 1080-1780 (di sini bentuk sabitnya penuh), pudar ~2080, keluar ~2560
  const jadwal = [[0, '01-klik'], [800, '02-matahari-tenggelam'], [1050, '03-bulan-muncul'],
      [1800, '04-bulan-sabit'], [2150, '05-bulan-pudar'], [2500, '06-tirai-keluar'], [3300, '07-selesai']];
    let t0 = Date.now();
    for (const [ms, nama] of jadwal) {
      const sisa = ms - (Date.now() - t0);
      if (sisa > 0) { await tunggu(sisa); }
      const p = await cdp.simpan(nama);
      const st = await cdp.eval(`JSON.stringify({tema:document.documentElement.getAttribute('data-theme'),
        tirai:document.getElementById('themeWipe').className,
        pang:document.getElementById('temaPanggung').className})`).then(JSON.parse);
      jejak.push({ ms, nama, ...st });
      console.log(`  ${String(ms).padStart(4)}ms ${nama.padEnd(24)} tema=${st.tema} tirai=[${st.tirai}] pang=[${st.pang}]  ${p}`);
    }
    cdp.tutup();
  }
} catch (e) {
  console.error('GALAT:', e.message); kode = 1;
} finally {
  try { chrome.kill(); } catch {}
  await tunggu(300);
  try { rmSync(profil, { recursive: true, force: true }); } catch {}
}
console.log('keluaran:', OUT);
process.exit(kode);
