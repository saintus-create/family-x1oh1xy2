import { readFileSync, writeFileSync, readdirSync, statSync } from "fs";
import { join, basename } from "path";

const ROOT = "/home/runner/workspace";
const DOCS_YML  = `${ROOT}/fern/docs.yml`;
const PAGES_DIR = `${ROOT}/fern/docs/pages`;
const STYLES    = `${ROOT}/fern/styles.css`;

// ─────────────────────────────────────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────────────────────────────────────
const MINOR = new Set(["a","an","the","and","but","or","for","nor","on","at","to","by","in","of","up","as","with","from","into","over","than"]);

function smartTitle(str) {
  const words = str.split(" ");
  return words.map((w, i) => {
    const low = w.toLowerCase();
    const isAllCaps = w === w.toUpperCase() && /[A-Z]/.test(w);
    if (!isAllCaps) return w; // already mixed-case, leave alone

    // Minor words in the middle → always lowercase
    if (i > 0 && i < words.length - 1 && MINOR.has(low)) return low;

    // Preserve known legal acronyms/codes (short ≤5 OR hyphenated/dotted)
    if (w.length <= 5 || w.includes("-") || w.includes(".")) return w;

    // Title-case everything else
    return w[0].toUpperCase() + w.slice(1).toLowerCase();
  }).join(" ");
}

function cleanHeading(raw) {
  raw = raw.replace(/\s*\[[\d\.\s\-]+\]/g, "");   // remove [range] brackets
  raw = raw.replace(/  +/g, " ").trim();            // collapse spaces
  raw = raw.replace(/—/g, " - ");                   // em-dash → hyphen
  return smartTitle(raw);
}

function getAllMdx(dir) {
  const files = [];
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, e.name);
    if (e.isDirectory()) files.push(...getAllMdx(full));
    else if (e.name.endsWith(".mdx")) files.push(full);
  }
  return files;
}

// ─────────────────────────────────────────────────────────────────────────────
// 1. docs.yml
// ─────────────────────────────────────────────────────────────────────────────
console.log("[1] Updating docs.yml...");
let yml = readFileSync(DOCS_YML, "utf8");

// Nuke every injected bottom block (colors/theme/landing-page/css)
yml = yml.replace(/\ncolors:\n  accent-primary:[\s\S]*$/m, "");
yml = yml.replace(/\ncss:\n(  - [^\n]+\n?)+/g, "\n");
yml = yml.replace(/\ntheme:\n(  [^\n]+\n?)+/g, "\n");
yml = yml.replace(/\nlanding-page:\n(  [^\n]+\n?)+/g, "\n");
yml = yml.replace(/\ntypography:\n(  [^\n]+\n?)+/g, "\n");

// Remove any existing colors: block (will re-add clean one)
yml = yml.replace(/\ncolors:\n(  [^\n]+\n)+/g, "\n");

// Build the replacement header block (colors + typography)
const CONFIG_BLOCK = [
  "",
  "colors:",
  '  accentPrimary:',
  '    light: "#1E4A8A"',
  '    dark: "#6B9FD4"',
  '  background:',
  '    light: "#F5F4F0"',
  '    dark: "#1C2332"',
  "",
  "typography:",
  "  headingsFont:",
  "    name: Instrument Serif",
  "",
].join("\n");

yml = yml.replace("title: California Family Code\n", "title: California Family Code\n" + CONFIG_BLOCK);

// Add icon: book-open to division-level sections (10-space indent + collapsed: true follows)
yml = yml.replace(
  /(          - section: "[^"]+"\n)(            collapsed: true)/g,
  (_, s, c) => {
    if (s.includes("icon:")) return s + c; // skip if already has icon
    return s + "            icon: book-open\n" + c;
  }
);

// Add icon: scale to Case Annotations (only if not already there)
if (!yml.includes("icon: scale")) {
  yml = yml.replace(
    /(      - section: Case Annotations\n)(        contents:)/g,
    "$1        icon: scale\n$2"
  );
}

// Add separators between major division sections inside "Divisions"
// Each top-level division is "          - section: " at 10-space indent
// We insert "          - separator" before each one except the first
let divisionCount = 0;
yml = yml.replace(/(      - section: Divisions\n        contents:\n)([\s\S]*?)(?=\n      - section: Case Annotations)/m, (_, header, body) => {
  const fixed = body.replace(/^(          - section: "[^"]+")/gm, (match) => {
    divisionCount++;
    if (divisionCount === 1) return match;
    return `          - separator\n${match}`;
  });
  return header + fixed;
});
console.log(`   Added ${divisionCount - 1} separators between divisions`);

// Em-dashes in navigation section labels
yml = yml.replace(/—/g, " - ");

writeFileSync(DOCS_YML, yml, "utf8");
console.log("   docs.yml done");

// ─────────────────────────────────────────────────────────────────────────────
// 2. ALL MDX files — universal passes
// ─────────────────────────────────────────────────────────────────────────────
console.log("[2] Processing all MDX pages...");

const OVERVIEW = new Set(["preliminary-provisions.mdx","marriage.mdx","division-2.5-domestic-partners.mdx","division-3-marriage.mdx","division-4-rights-during-marriage.mdx","division-5-conciliation.mdx","division-6-dissolution.mdx","division-7-property.mdx","division-8-custody.mdx","division-9-support.mdx","division-10-domestic-violence.mdx","division-11-minors.mdx","division-12-parent-child.mdx","division-13-adoption.mdx","division-14-family-law-facilitator.mdx","division-17-support-services.mdx","division-20-pilot-projects.mdx"]);

const allMdx = getAllMdx(PAGES_DIR);
let totalCleaned = 0;

for (const fpath of allMdx) {
  const fname = basename(fpath);
  let c = readFileSync(fpath, "utf8");
  const orig = c;

  // ── Universal: em-dashes ──────────────────────────────────────────────────
  c = c.replace(/—/g, " - ");

  // ── Universal: remove leftover custom HTML blocks ─────────────────────────
  c = c.replace(/<nav[^>]*class=["']fl-breadcrumb["'][^>]*>[\s\S]*?<\/nav>\s*\n?/g, "");
  c = c.replace(/<div[^>]*class=["']fl-section-nav["'][^>]*>[\s\S]*?<\/div>\s*\n?/g, "");
  c = c.replace(/<span[^>]*class=["']subsec["'][^>]*>([^<]*)<\/span>/g, "$1");
  c = c.replace(/<span[^>]*class=["']statute-link["'][^>]*>([^<]*)<\/span>/g, "$1");
  c = c.replace(/<span[^>]*class=["']case-statutes["'][^>]*>([^<]*)<\/span>/g, "$1");

  // <small>[Source](url)</small>  →  [Source](url)
  c = c.replace(/<small>(\[Source\][^<]*)<\/small>/g, "$1");

  // <div class="source-note">...**Source:** Family Code · [View on ...](url)...</div>
  // Extract just the leginfo link and render as a plain source line
  c = c.replace(
    /<div[^>]*class=["']source-note["'][^>]*>[\s\S]*?\[View on[^\]]*\]\(([^)]+)\)[\s\S]*?<\/div>\s*\n?/g,
    (_, url) => `\n[Source](${url})\n`
  );
  // Fallback: remove any remaining source-note divs
  c = c.replace(/<div[^>]*class=["']source-note["'][^>]*>[\s\S]*?<\/div>\s*\n?/g, "");

  // Unwrap case-callout divs
  c = c.replace(/<div[^>]*class=["']case-callout["'][^>]*>([\s\S]*?)<\/div>/g, "$1");

  // ── "Added/Amended/Enacted by Stats." → blockquote callout ───────────────
  // Pattern 1: italic wrapped  _(...Amended by Stats. ...)_
  c = c.replace(/_\(((?:Added|Amended|Enacted|Repealed|Operative) by Stats\.[^_]+)\)_/g,
    (_, cite) => `\n\n> *${cite.trim()}*`);

  // Pattern 2: bare sentence at end of paragraph
  c = c.replace(
    /\. ((Added|Amended|Enacted|Repealed|Operative) by Stats\. [^\n]+(?:Effective[^\n.]+\.|Operative[^\n.]+\.)?)/g,
    (_, cite) => `.\n\n> *${cite.trim()}*`
  );

  // ── Fix frontmatter ALL CAPS title / description ──────────────────────────
  c = c.replace(/^(title:\s*")([^"]+)(")/m,  (_, a, b, d) => a + cleanHeading(b) + d);
  c = c.replace(/^(description:\s*")([^"]+)(")/m, (_, a, b, d) => a + cleanHeading(b) + d);

  // ── Remove duplicate first heading (Fern renders frontmatter title as H1) ─
  // Match: blank line(s) + # heading + optional blank line + optional short title repeat
  // For section pages: "# 6200\n\n" or "# 1\n\nTitle of code\n\n"
  // For overview pages: "# Division 10 ...\n\n"
  // Strategy: remove first H1 after frontmatter close
  c = c.replace(
    /^(---\n[\s\S]*?\n---\n)\n*(# [^\n]+)\n\n?([^\n#>][^\n]{0,80})\n\n/m,
    (full, fm, h1, nextLine) => {
      // If nextLine looks like a short section title (not statute text starting with letters/numbers that make long sentences)
      // i.e., it's the "description" repeated as body text
      const descMatch = fm.match(/^description:\s*"([^"]+)"/m);
      const desc = descMatch ? descMatch[1] : "";
      const cleanedDesc = cleanHeading(desc);
      const cleanedNext = cleanHeading(nextLine.trim());
      if (cleanedNext === cleanedDesc || nextLine.trim().length < 80) {
        return fm + "\n";
      }
      return fm + "\n" + h1 + "\n\n" + nextLine + "\n\n";
    }
  );

  // Simpler fallback: just remove first H1 with no following content confusion
  // (catches cases where heading is immediately followed by blank line then ##)
  c = c.replace(
    /^(---\n[\s\S]*?\n---\n)\n*(# [^\n]+)\n\n(?=##)/m,
    "$1\n"
  );

  // ── Overview pages: fix ALL CAPS in markdown headings ────────────────────
  if (fname === "home.mdx" || OVERVIEW.has(fname)) {
    c = c.replace(/^(#{1,4})\s+(.+)$/gm, (_, h, body) => h + " " + cleanHeading(body));
  }

  if (c !== orig) {
    writeFileSync(fpath, c, "utf8");
    totalCleaned++;
  }
}
console.log(`   processed ${allMdx.length} files, changed ${totalCleaned}`);

// ─────────────────────────────────────────────────────────────────────────────
// 3. styles.css — clear completely
// ─────────────────────────────────────────────────────────────────────────────
writeFileSync(STYLES, "/* California Family Code */\n", "utf8");

console.log("\nDone.");
