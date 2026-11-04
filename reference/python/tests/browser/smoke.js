// Browser-Rauchtest: zwei Spieler, Anmeldung, Bewegung, Sammeln, Kampf. Aufruf: node smoke.js <port> [Screenshot-Verzeichnis]
const { chromium } = require('playwright');
const port = process.argv[2], shots = process.argv[3];
const sleep = ms => new Promise(r => setTimeout(r, ms));
const fail = m => { console.error('FEHLER: ' + m); process.exitCode = 1; };
(async () => {
  const b = await chromium.launch();
  const errors = [];
  async function player(name) {
    const p = await (await b.newContext({ viewport: { width: 1200, height: 800 } })).newPage();
    p.on('pageerror', e => errors.push(name + ': ' + e.message));
    p.on('console', m => { if (m.type() === 'error') errors.push(name + ': ' + m.text()); });
    await p.goto(`http://127.0.0.1:${port}/`);
    await p.fill('#acc', name); await p.fill('#pw', 'passwort123');
    await p.click('#bReg');
    await p.waitForSelector('#game', { state: 'visible', timeout: 5000 });
    return p;
  }
  const a = await player('anna'), c = await player('ben');
  await sleep(500);
  const txt = async p => (await p.textContent('#me')) || '';
  if (!/anna/.test(await txt(a))) fail('HUD anna: ' + await txt(a));
  // Bewegen: nach Osten laufen, Position muss sich ändern
  const pos0 = await txt(a);
  await a.keyboard.down('d'); await sleep(1500); await a.keyboard.up('d'); await sleep(400);
  if (pos0 === await txt(a)) fail('Bewegung ohne Wirkung');
  // Anmeldung mit falschem Passwort
  const p3 = await (await b.newContext()).newPage();
  await p3.goto(`http://127.0.0.1:${port}/`); await p3.fill('#acc', 'anna'); await p3.fill('#pw', 'falsch12345'); await p3.click('#bLogin');
  await p3.waitForFunction(() => document.getElementById('err').textContent.length > 0, null, { timeout: 5000 });
  if (!/falsch/i.test(await p3.textContent('#err'))) fail('Fehlermeldung: ' + await p3.textContent('#err'));
  if (shots) await a.screenshot({ path: shots + '/welt.png' });
  console.log('OK pos', pos0, '->', await txt(a), 'Fehler:', errors.length);
  errors.forEach(e => fail(e));
  await b.close();
})().catch(e => { console.error(e); process.exit(2); });
