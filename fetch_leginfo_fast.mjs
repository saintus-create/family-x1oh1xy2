#!/usr/bin/env node
/**
 * fetch_leginfo_fast.mjs
 * Fetches all California Family Code sections from leginfo.legislature.ca.gov
 * using Node built-in fetch (no external deps), 50 concurrent requests.
 * Saves results to leginfo_sections.json for use by unify_family_docs.py.
 */

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const SECTIONS_FULL = path.join(__dirname, "family_code_sections_full.json");
const PAGES_DIR = path.join(__dirname, "fern/docs/pages");
const OUTPUT = path.join(__dirname, "leginfo_sections.json");
const CONCURRENCY = 40;

const HEADERS = {
  "User-Agent":
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
  "Accept-Language": "en-US,en;q=0.9",
  Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
};

function leginfoUrl(sec) {
  return `https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=FAM&sectionNum=${encodeURIComponent(sec)}.`;
}

/**
 * Parse statute text from leginfo HTML.
 * Finds the <h6> heading for the section, then collects all <p> text following it.
 */
function parseLeginfoHtml(html, secNum) {
  // Strategy 1: find <h6> with this section number, grab following <p> tags
  const bare = secNum.replace(/\.$/, "");
  // Pattern: <h6 ...><b>6203.  </b></h6> or similar
  const h6Re = new RegExp(
    `<h6[^>]*>\\s*<b>\\s*${bare.replace(".", "\\.")}\\s*\\.?\\s*</b>\\s*</h6>`,
    "i"
  );
  const h6Match = html.match(h6Re);

  let textBlocks = [];

  if (h6Match) {
    // Grab all <p> tags after the h6 in the same container
    const afterH6 = html.slice(h6Match.index + h6Match[0].length);
    // Stop at next <h6> (next section) or end of codeLawSectionNoHead div
    const nextH6 = afterH6.search(/<h6/i);
    const chunk = nextH6 > 0 ? afterH6.slice(0, nextH6) : afterH6.slice(0, 8000);
    // Extract all <p> tags
    const pRe = /<p[^>]*>([\s\S]*?)<\/p>/gi;
    let m;
    while ((m = pRe.exec(chunk)) !== null) {
      const t = m[1]
        .replace(/<[^>]+>/g, " ")
        .replace(/&amp;/g, "&")
        .replace(/&lt;/g, "<")
        .replace(/&gt;/g, ">")
        .replace(/&nbsp;/g, " ")
        .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(parseInt(n)))
        .replace(/\s+/g, " ")
        .trim();
      if (t) textBlocks.push(t);
    }
  }

  if (textBlocks.length > 0) {
    return textBlocks.join("\n\n");
  }

  // Strategy 2: extract from codeLawSectionNoHead div, clean header noise
  const divMatch = html.match(/<div\s+id="codeLawSectionNoHead">([\s\S]*?)(?=<\/div>\s*<div\s+class="(?:codeLaw|pagination)|$)/i);
  const raw = divMatch
    ? divMatch[1]
    : (html.match(/<div[^>]*id="codeLawSection[^"]*">([\s\S]*?)<\/div>/i) || [,""])[1];

  if (!raw) return null;

  // Strip all HTML tags, decode entities
  let text = raw
    .replace(/<[^>]+>/g, "\n")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&nbsp;/g, " ")
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(parseInt(n)));

  // Filter out header/noise lines
  const lines = text.split("\n").map((l) => l.trim()).filter((l) => {
    if (!l) return false;
    if (/^(FAMILY CODE|CAL\.\s*FAM\.\s*CODE|Family Code\s*$)/i.test(l)) return false;
    if (/^(DIVISION|PART|CHAPTER)\s+\d/i.test(l)) return false;
    if (/^[A-Z][A-Z\s,.'"\d\[\]()-]+\[\d+ - \d+\]\s*$/.test(l)) return false;
    if (/^\s*\d{1,4}\s*$/.test(l)) return false;
    if (/^(Added by Stats\.|Amended by Stats\.|\(Added by|\(Amended by)/i.test(l)) return false;
    return true;
  });

  const cleaned = lines.join("\n").replace(/\n{3,}/g, "\n\n").trim();
  return cleaned.length > 30 ? cleaned : null;
}

async function fetchSection(secNum, url) {
  try {
    const resp = await fetch(url, { headers: HEADERS, signal: AbortSignal.timeout(20000) });
    if (resp.status === 404) return { title: "", text: "", source_url: url };
    if (!resp.ok) return null;
    const html = await resp.text();
    const text = parseLeginfoHtml(html, secNum);
    if (!text) return { title: "", text: "", source_url: url };

    // Extract title from first short non-subsection line
    const first = text.split("\n").find((l) => l.trim());
    const title =
      first && first.length < 120 && !/^\(/.test(first.trim()) ? first.trim() : "";

    return { title, text, source_url: url };
  } catch (e) {
    return null; // network error → will be retried
  }
}

async function runPool(tasks, concurrency) {
  const results = new Array(tasks.length).fill(null);
  let idx = 0;

  async function worker() {
    while (idx < tasks.length) {
      const i = idx++;
      results[i] = await tasks[i]();
    }
  }

  await Promise.all(Array.from({ length: concurrency }, worker));
  return results;
}

async function main() {
  console.log("=".repeat(60));
  console.log("  leginfo fast-fetch  (Node.js, " + CONCURRENCY + " concurrent)");
  console.log("=".repeat(60));

  // 1. Collect all section numbers
  const raw = JSON.parse(fs.readFileSync(SECTIONS_FULL, "utf8"));
  const secsArr = raw.sections || (Array.isArray(raw) ? raw : Object.values(raw));

  const allSections = {}; // sec_num → url
  for (const s of secsArr) {
    const num = String(s.sectionNumber || "").trim();
    const url = s.source_url || leginfoUrl(num);
    if (num) allSections[num] = url;
  }

  // Also pull from MDX filenames
  for (const f of fs.readdirSync(PAGES_DIR)) {
    const m = f.match(/^.+-section-([\d.]+)\.mdx$/);
    if (m && !allSections[m[1]]) {
      allSections[m[1]] = leginfoUrl(m[1]);
    }
  }

  console.log(`\nTotal sections: ${Object.keys(allSections).length}`);

  // 2. Load existing cache
  let cache = {};
  if (fs.existsSync(OUTPUT)) {
    cache = JSON.parse(fs.readFileSync(OUTPUT, "utf8"));
    // Keep only entries with actual text
    cache = Object.fromEntries(
      Object.entries(cache).filter(([, v]) => v && v.text && v.text.trim().length > 30)
    );
    console.log(`Cache: ${Object.keys(cache).length} sections already fetched.`);
  }

  const todo = Object.entries(allSections).filter(([k]) => !cache[k]);
  console.log(`Need to fetch: ${todo.length}\n`);

  if (todo.length === 0) {
    console.log("All done — nothing to fetch.");
    return;
  }

  // 3. Parallel fetch
  let done = 0;
  let errors = 0;
  const retry = []; // sections that returned null

  const checkpoint = () => {
    fs.writeFileSync(OUTPUT, JSON.stringify(cache, null, 2));
  };

  const tasks = todo.map(([num, url]) => async () => {
    const result = await fetchSection(num, url);
    if (result) {
      cache[num] = result;
      done++;
    } else {
      retry.push([num, url]);
      errors++;
    }
    const total = done + errors;
    if (total % 200 === 0) {
      const pct = Math.round((total / todo.length) * 100);
      console.log(`  ${total}/${todo.length} (${pct}%)  OK=${done}  err=${errors}`);
      checkpoint();
    }
  });

  await runPool(tasks, CONCURRENCY);
  checkpoint();
  console.log(`\nFirst pass: ${done} OK, ${errors} errors`);

  // 4. One retry pass for network errors
  if (retry.length > 0) {
    console.log(`\nRetrying ${retry.length} failed sections…`);
    await new Promise((r) => setTimeout(r, 2000));
    const retry2 = [];
    const retryTasks = retry.map(([num, url]) => async () => {
      const result = await fetchSection(num, url);
      if (result) {
        cache[num] = result;
        done++;
      } else {
        retry2.push([num, url]);
      }
    });
    await runPool(retryTasks, Math.ceil(CONCURRENCY / 2));
    checkpoint();
    console.log(`After retry: ${retry.length - retry2.length} recovered, ${retry2.length} still failed`);
  }

  // 5. Summary
  const withText = Object.values(cache).filter((v) => v.text && v.text.trim().length > 50);
  console.log(`\nCache saved → ${OUTPUT}`);
  console.log(`Total cached: ${Object.keys(cache).length} | With text: ${withText.length}`);
  console.log("\nNow run:  python3 build_and_push.py  to rebuild pages and push.");
}

main().catch((e) => {
  console.error("FATAL:", e);
  process.exit(1);
});
