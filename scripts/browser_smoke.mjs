// Rauchtest des Browser-Clients mit echtem Chromium (headless) über das DevTools-Protokoll (Node >= 22, keine Abhängigkeiten).
// Aufruf: node scripts/browser_smoke.mjs <chrome-pfad> <port>   (Server vorher starten: python3 -m mmo_game.net <port> --data <ordner>)
import { spawn } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [chromePath, port] = [process.argv[2], process.argv[3] || "17900"];
const dbg = 9333 + Math.floor(Math.random() * 500);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const chrome = spawn(chromePath, ["--headless=new", "--no-sandbox", "--disable-gpu", `--remote-debugging-port=${dbg}`, `--user-data-dir=${mkdtempSync(join(tmpdir(), "smoke-"))}`, "about:blank"], { stdio: "ignore" });
let failed = 0;
const check = (ok, msg) => { console.log((ok ? "ok      " : "FEHLER  ") + msg); if (!ok) failed++; };
try {
  let target;
  for (let i = 0; i < 50 && !target; i++) { try { target = await (await fetch(`http://127.0.0.1:${dbg}/json/new?about:blank`, { method: "PUT" })).json(); } catch { await sleep(200); } }
  if (!target) throw new Error("Chromium nicht erreichbar");
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((r) => (ws.onopen = r));
  let id = 0; const pending = new Map(); const problems = [];
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
    if (m.method === "Runtime.exceptionThrown") problems.push("Ausnahme: " + (m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text));
    if (m.method === "Runtime.consoleAPICalled" && m.params.type === "error") problems.push("console.error: " + m.params.args.map((a) => a.value ?? a.description).join(" "));
  };
  const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
  const ev = async (expr) => { const r = await send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true }); if (r.result.exceptionDetails) throw new Error(r.result.exceptionDetails.exception?.description || "evaluate"); return r.result.result.value; };
  await send("Runtime.enable"); await send("Page.enable");
  await send("Page.navigate", { url: `http://127.0.0.1:${port}/` }); await sleep(1500);
  check(await ev("!!document.getElementById('login')"), "Seite geladen, Anmeldung sichtbar");
  const acct = "smoke" + Math.floor(Math.random() * 1e6);
  await ev(`document.getElementById('acc').value='${acct}';document.getElementById('pw').value='geheim-passwort-1';document.getElementById('bReg').click()`);
  for (let i = 0; i < 40; i++) { if (await ev("getComputedStyle(document.getElementById('game')).display!=='none'")) break; await sleep(250); }
  check(await ev("getComputedStyle(document.getElementById('game')).display!=='none'"), "Konto angelegt, Spielansicht offen: " + await ev("document.getElementById('err').textContent"));
  await sleep(800);
  // alle Fenster öffnen und aktualisieren lassen
  const wins = await ev("[...document.querySelectorAll('details.win')].map(d=>d.id)");
  for (const w of wins) { await ev(`(()=>{const d=document.getElementById('${w}');d.open=true;d.dispatchEvent(new Event('toggle'))})()`); await sleep(350); }
  check(wins.length >= 8, `${wins.length} Fenster geöffnet: ${wins.join(", ")}`);
  const bad = await ev("[...document.querySelectorAll('details.win')].filter(d=>/undefined|NaN|\\[object/.test(d.innerText)).map(d=>d.id)");
  check(bad.length === 0, "Kein 'undefined'/'NaN'/'[object' in den Fenstertexten" + (bad.length ? ": " + bad : ""));
  // Szenario über die Seiten-API: Siedlung, Gilde, Chat, Titel, Zweig – danach muss die Darstellung stimmen
  const api = async (cmd, args = {}) => ev(`call(${JSON.stringify(cmd)},Object.assign({char:me},${JSON.stringify(args)})).then(r=>r.ok?'ok':(r.error&&r.error.message)||'fehler')`);
  const r1 = await api("guild.found", { name: "Rauchgilde", tag: "RG" }); check(r1 === "ok", "Gilde gegründet" + (r1 === "ok" ? "" : ": " + r1));
  const r2 = await api("guild.say", { text: "Rauchtest-Nachricht" }); check(r2 === "ok", "Gildennachricht gesendet" + (r2 === "ok" ? "" : ": " + r2));
  await ev("refreshGuild()"); await sleep(500);
  check((await ev("document.getElementById('guildBox').innerText")).includes("Rauchtest-Nachricht"), "Gildenchat zeigt die Nachricht im Fenster");
  await ev("refreshTown()"); await sleep(500);
  const town = await ev("document.getElementById('townBox').innerText");
  check(town.includes("Gebührenrabatt Markt") && town.includes("Hauptstadt"), "Siedlungsfenster zeigt Rabatt und Orte");
  await ev("initMarket()"); await sleep(500);
  check((await ev("document.getElementById('mOrders').innerText")).includes("Gebühr beim Verkauf"), "Marktfenster zeigt Gebühr und Auftragsgrenze");
  await ev("refreshChron()"); await sleep(500);
  check((await ev("document.getElementById('chronBox').innerText")).includes("Ruhmpunkte"), "Chronikfenster zeigt Ruhmpunkte");
  await ev("refreshGear()"); await sleep(500);
  check((await ev("document.getElementById('gearBox').innerText")).includes("Gesamtwirkung"), "Ausrüstungsfenster zeigt die Gesamtwirkung");
  // Titelwahl über echte Klicks: Ort gründen -> Chronik-Titel -> Knopf klicken -> Anzeige prüfen
  const r3 = await api("settlement.found", { site: "moorufer", name: "Rauchheim" }); check(r3 === "ok", "Ort gegründet" + (r3 === "ok" ? "" : ": " + r3));
  await ev("refreshChron()"); await sleep(600);
  check((await ev("document.getElementById('chronBox').innerText")).includes("Anzeigetitel wählen"), "Chronik bietet die Titelwahl an");
  await ev("[...document.querySelectorAll('#chronBox button')].find(b=>b.textContent.includes('Gründer von Rauchheim')).click()"); await sleep(800);
  const chron = await ev("document.getElementById('chronBox').innerText");
  check(chron.includes("Angezeigter Titel") && chron.includes("✔ Gründer von Rauchheim"), "Titel per Klick gewählt und angezeigt");
  // Grundstück kaufen und per Klick als offenes Angebot einstellen (prompt wird mit Antworten belegt)
  const r4 = await api("plot.buy", { site: "moorufer", n: 1 }); check(r4 === "ok", "Grundstück gekauft" + (r4 === "ok" ? "" : ": " + r4));
  await ev("window.__answers=['','150'];window.prompt=()=>window.__answers.shift();window.confirm=()=>true;refreshTown()"); await sleep(600);
  await ev("[...document.querySelectorAll('#townBox button')].find(b=>b.textContent==='Verkaufen').click()"); await sleep(900);
  const town2 = await ev("document.getElementById('townBox').innerText");
  check(town2.includes("Angebot zurückziehen"), "Offenes Grundstücksangebot per Klick erstellt (Knopf wechselt zu 'Angebot zurückziehen')");
  await ev("[...document.querySelectorAll('#townBox button')].find(b=>b.textContent==='Angebot zurückziehen').click()"); await sleep(800);
  check((await ev("document.getElementById('townBox').innerText")).includes("Verkaufen"), "Angebot per Klick zurückgezogen");
  check(problems.length === 0, "Keine JS-Ausnahmen/console.error" + (problems.length ? ":\n  " + problems.slice(0, 5).join("\n  ") : ""));
} catch (e) { console.log("FEHLER  " + e.message); failed++; }
finally { chrome.kill(); }
console.log(failed ? `\n${failed} Prüfung(en) fehlgeschlagen` : "\nRauchtest bestanden");
process.exit(failed ? 1 : 0);
