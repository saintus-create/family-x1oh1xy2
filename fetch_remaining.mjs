#!/usr/bin/env node
/**
 * fetch_remaining.mjs
 * Fetches only the sections missing/empty in leginfo_sections.json.
 * Uses low concurrency (5 workers) + 200ms delay to avoid rate limiting.
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SECTIONS_FULL = path.join(__dirname, "family_code_sections_full.json");
const PAGES_DIR     = path.join(__dirname, "fern/docs/pages");
const OUTPUT        = path.join(__dirname, "leginfo_sections.json");
const CONCURRENCY   = 5;
const DELAY_MS      = 150;

const HEADERS = {
  "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
  "Accept-Language": "en-US,en;q=0.9",
  Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
};

function leginfoUrl(sec) {
  return `https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=FAM&sectionNum=${encodeURIComponent(sec)}.`;
}

function parseLeginfoHtml(html, secNum) {
  const bare = secNum.replace(/\.$/, "");
  const h6Re = new RegExp(`<h6[^>]*>\\s*<b>\\s*${bare.replace(/\./g, "\\.")}\\s*\\.?\\s*</b>\\s*</h6>`, "i");
  const h6Match = html.match(h6Re);
  let textBlocks = [];
  if (h6Match) {
    const afterH6 = html.slice(h6Match.index + h6Match[0].length);
    const nextH6 = afterH6.search(/<h6/i);
    const chunk = nextH6 > 0 ? afterH6.slice(0, nextH6) : afterH6.slice(0, 10000);
    const pRe = /<p[^>]*>([\s\S]*?)<\/p>/gi;
    let m;
    while ((m = pRe.exec(chunk)) !== null) {
      const t = m[1].replace(/<[^>]+>/g," ").replace(/&amp;/g,"&").replace(/&lt;/g,"<").replace(/&gt;/g,">").replace(/&nbsp;/g," ").replace(/&#(\d+);/g,(_,n)=>String.fromCharCode(parseInt(n))).replace(/\s+/g," ").trim();
      if (t) textBlocks.push(t);
    }
  }
  if (textBlocks.length > 0) return textBlocks.join("\n\n");

  const divMatch = html.match(/<div\s+id="codeLawSectionNoHead">([\s\S]*?)(?=<div[^>]+class="(?:codeLaw|pag)|$)/i);
  const raw = divMatch ? divMatch[1] : "";
  if (!raw) return null;
  let text = raw.replace(/<[^>]+>/g,"\n").replace(/&amp;/g,"&").replace(/&lt;/g,"<").replace(/&gt;/g,">").replace(/&nbsp;/g," ").replace(/&#(\d+);/g,(_,n)=>String.fromCharCode(parseInt(n)));
  const lines = text.split("\n").map(l=>l.trim()).filter(l=>{
    if (!l) return false;
    if (/^(FAMILY CODE|Family Code\s*$)/i.test(l)) return false;
    if (/^(DIVISION|PART|CHAPTER)\s+\d/i.test(l)) return false;
    if (/^[A-Z][A-Z\s,.'"\d\[\]()-]+\[\d+ - \d+\]\s*$/.test(l)) return false;
    if (/^\s*\d{1,4}\s*$/.test(l)) return false;
    return true;
  });
  const cleaned = lines.join("\n").replace(/\n{3,}/g,"\n\n").trim();
  return cleaned.length > 30 ? cleaned : null;
}

async function fetchOne(secNum, url) {
  await new Promise(r => setTimeout(r, Math.random() * DELAY_MS));
  try {
    const resp = await fetch(url, { headers: HEADERS, signal: AbortSignal.timeout(25000) });
    if (resp.status === 404) return { title:"", text:"", source_url:url };
    if (!resp.ok) return null;
    const html = await resp.text();
    const text = parseLeginfoHtml(html, secNum);
    if (!text) return { title:"", text:"", source_url:url };
    const first = text.split("\n").find(l=>l.trim());
    const title = first && first.length < 120 && !/^\(/.test(first.trim()) ? first.trim() : "";
    return { title, text, source_url: url };
  } catch(e) { return null; }
}

async function runPool(tasks, concurrency) {
  const results = new Array(tasks.length).fill(null);
  let idx = 0;
  async function worker() {
    while (idx < tasks.length) { const i = idx++; results[i] = await tasks[i](); }
  }
  await Promise.all(Array.from({ length: concurrency }, worker));
  return results;
}

async function main() {
  // Collect all sections
  const raw = JSON.parse(fs.readFileSync(SECTIONS_FULL,"utf8"));
  const secsArr = raw.sections || (Array.isArray(raw) ? raw : Object.values(raw));
  const allSections = {};
  for (const s of secsArr) {
    const num = String(s.sectionNumber||"").trim();
    if (num) allSections[num] = s.source_url || leginfoUrl(num);
  }
  for (const f of fs.readdirSync(PAGES_DIR)) {
    const m = f.match(/^.+-section-([\d.]+)\.mdx$/);
    if (m && !allSections[m[1]]) allSections[m[1]] = leginfoUrl(m[1]);
  }

  // Load cache
  let cache = {};
  if (fs.existsSync(OUTPUT)) {
    cache = JSON.parse(fs.readFileSync(OUTPUT,"utf8"));
  }

  // Only fetch what's missing or empty
  const todo = Object.entries(allSections).filter(([k]) => {
    const v = cache[k];
    return !v || !v.text || v.text.trim().length < 30;
  });

  console.log(`Total sections: ${Object.keys(allSections).length}`);
  console.log(`Already cached: ${Object.keys(cache).length - todo.length}`);
  console.log(`Need to fetch: ${todo.length} (concurrency=${CONCURRENCY})`);

  if (todo.length === 0) { console.log("All done."); return; }

  let done = 0, errors = 0;
  const checkpoint = () => fs.writeFileSync(OUTPUT, JSON.stringify(cache, null, 2));

  const tasks = todo.map(([num, url]) => async () => {
    const result = await fetchOne(num, url);
    if (result && result.text) { cache[num] = result; done++; }
    else { errors++; }
    const total = done + errors;
    if (total % 100 === 0) {
      console.log(`  ${total}/${todo.length} (${Math.round(total/todo.length*100)}%)  OK=${done}  err=${errors}`);
      checkpoint();
    }
  });

  await runPool(tasks, CONCURRENCY);
  checkpoint();
  const withText = Object.values(cache).filter(v=>v.text&&v.text.trim().length>50);
  console.log(`\nDone. OK=${done} err=${errors}  | Cache: ${withText.length} with text`);
}

main().catch(e => { console.error("FATAL:", e); process.exit(1); });
