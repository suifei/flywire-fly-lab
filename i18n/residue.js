#!/usr/bin/env node
// 英文模式下，页面上还剩多少中文。真浏览器（puppeteer-core + 系统 Chrome）以 ?lang=en 打开三个页面，把各个模式 / 面板点一遍，
//   收两样东西：① DOM 里仍然含中文的可见文字与属性（不含 data-no-i18n / textarea 等不该翻的）；② 翻译层遇到但查不到的句子（I18N.missing，含 canvas 上画的）。
// 用法：node i18n/residue.js [--max N]  → results/i18n_residue.json；--max N：残留的不同句子超过 N 条就退出码 1（CI 用）。
//   补译文：把 results/i18n_residue.json 的 strings 翻好写进 i18n/en_extra.json，再 python3 i18n/build_dict.py 并重建页面。
const fs = require("fs"), path = require("path"), ROOT = path.resolve(__dirname, "..");
function loadPuppeteer() { for (const p of ["puppeteer-core", "puppeteer", path.join(ROOT, "studio/capture/node_modules/puppeteer-core")]) { try { return require(p); } catch (e) {} } return null; }
const chrome = () => [process.env.CHROME_PATH, "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium-browser"].filter(Boolean).find(p => { try { return fs.existsSync(p); } catch (e) { return false; } });
const sleep = ms => new Promise(r => setTimeout(r, ms)), MAX = process.argv.includes("--max") ? +process.argv[process.argv.indexOf("--max") + 1] : Infinity;
const norm = s => s.replace(/[-+]?\d+(?:[.,:]\d+)*/g, "{#}").replace(/\s+/g, " ").trim();
async function scan(page) { return page.evaluate(() => { const CJK = /[㐀-鿿]/, out = [], vis = el => { for (let e = el; e && e.nodeType === 1; e = e.parentElement) { if (e.hasAttribute("data-no-i18n") || ["SCRIPT", "STYLE", "TEXTAREA", "NOSCRIPT", "CODE", "PRE"].includes(e.tagName)) return false; } return true; };
    const w = document.createTreeWalker(document.body, 4); let n; while ((n = w.nextNode())) { const v = n.nodeValue; if (v && CJK.test(v) && vis(n.parentElement)) out.push(v.trim()); }
    for (const el of document.querySelectorAll("[title],[placeholder],[aria-label],[alt]")) for (const a of ["title", "placeholder", "aria-label", "alt"]) { const v = el.getAttribute(a); if (v && CJK.test(v) && vis(el)) out.push(v.trim()); }
    if (CJK.test(document.title)) out.push(document.title); return { dom: out, missing: window.I18N ? [...window.I18N.missing.keys()] : ["（没有 I18N）"], lang: window.I18N && window.I18N.lang }; }); }
const clickAll = async (page, sels, wait) => { for (const s of sels) { try { const ok = await page.evaluate(q => { const e = document.querySelector(q); if (!e || e.hidden) return false; e.click(); return true; }, s); if (ok) await sleep(wait); } catch (e) {} } };
(async () => {
  const puppeteer = loadPuppeteer(), exe = chrome(); if (!puppeteer || !exe) { console.log("跳过：没有 puppeteer-core 或 Chrome"); process.exit(process.env.CI ? 1 : 0); }
  const browser = await puppeteer.launch({ executablePath: exe, headless: "new", args: ["--no-sandbox", "--disable-dev-shm-usage", "--allow-file-access-from-files", "--lang=en-US"] });
  const agg = new Map(), per = {}, errs = [];
  const add = (page, list) => { for (const s of list) { const k = norm(s); if (!k) continue; const e = agg.get(k) || { s, n: 0, pages: new Set() }; e.n++; e.pages.add(page); agg.set(k, e); } };
  async function visit(name, url, actions) { const page = await browser.newPage(); await page.setViewport({ width: 1400, height: 1000 }); page.on("pageerror", e => errs.push(name + ": " + e.message));
    await page.goto("file://" + path.join(ROOT, url) + (url.includes("?") ? "&" : "?") + "lang=en", { waitUntil: "load", timeout: 180000 }); await sleep(2500); if (actions) await actions(page);
    const r = await scan(page); add(name, r.dom); add(name, r.missing); per[name] = { lang: r.lang, dom: r.dom.length, missing: r.missing.length }; await page.close(); }
  await visit("index", "docs/index.html");
  await visit("eco", "docs/ecobox.html?fresh=1&seed=42&speed=-1", async p => { await sleep(3000);
    for (const t of ["rules", "fly", "log", "cards", "replay", "compare", "save"]) await clickAll(p, [`#tabs button[data-tab="${t}"]`], 700);
    await p.evaluate(() => window.__eco && window.__eco.start("evo", {}, 7)); await sleep(5000); for (const t of ["log", "cards", "replay", "fly"]) await clickAll(p, [`#tabs button[data-tab="${t}"]`], 700); });
  await visit("game-nature", "docs/game.html?scene=nature", async p => { await sleep(6000); await clickAll(p, ["#viewLife"], 5000); await clickAll(p, ["#viewGomoku"], 4000); await clickAll(p, ["#viewCourt"], 4000); });
  await visit("game-court", "docs/game.html?scene=court", async p => { await sleep(6000); await clickAll(p, ["#viewLife"], 4000); await clickAll(p, ["#viewCourt"], 3000); });
  await browser.close();
  const list = [...agg.values()].sort((a, b) => b.n - a.n).map(e => ({ s: e.s, n: e.n, pages: [...e.pages] }));
  const out = { unique: list.length, chars: list.reduce((t, e) => t + e.s.length, 0), per_page: per, page_errors: errs, strings: list };
  fs.writeFileSync(path.join(ROOT, "results/i18n_residue.json"), JSON.stringify(out, null, 1));
  console.log(`英文模式残留：${list.length} 种句子，${out.chars} 个字符；`, JSON.stringify(per)); for (const e of list.slice(0, 25)) console.log(`  ${String(e.n).padStart(4)}×  ${e.s.slice(0, 90)}`); if (errs.length) console.log("页面报错：", errs.slice(0, 5));
  process.exit(list.length > MAX || errs.length ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
