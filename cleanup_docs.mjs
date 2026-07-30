import { readFileSync, writeFileSync, readdirSync, statSync } from "fs";
import { join, basename } from "path";

const ROOT = "/home/runner/workspace";
const DOCS_YML  = `${ROOT}/fern/docs.yml`;
const PAGES_DIR = `${ROOT}/fern/docs/pages`;
const STYLES    = `${ROOT}/fern/styles.css`;

console.log("[1] Updating docs.yml...");
let text = readFileSync(DOCS_YML, "utf8");
text = text.replace(/\ncolors:\n  accent-primary:[\s\S]*$/m, "");
text = text.replace(/\ncss:\n(  - [^\n]+\n?)+/g, "\n");
text = text.replace(/\ntheme:\n(  [^\n]+\n?)+/g, "\n");
text = text.replace(/\nlanding-page:\n(  [^\n]+\n?)+/g, "\n");
text = text.replace(/\ncolors:\n(  [^\n]+\n)+/g, "\n");
const COLORS = "\ncolors:\n  accentPrimary:\n    light: \"#1E4A8A\"\n    dark:  \"#6B9FD4\"\n  background:\n    light: \"#F5F4F0\"\n    dark:  \"#1C2332\"\n";
text = text.replace("title: California Family Code\n", "title: California Family Code\n" + COLORS);
text = text.replace(/(          - section: "[^"]+"\n)(            collapsed: true)/g, (_, s, c) => s + "            icon: book-open\n" + c);
text = text.replace(/(      - section: Case Annotations\n)(        contents:)/g, "$1        icon: scale\n$2");
writeFileSync(DOCS_YML, text, "utf8");
console.log("   docs.yml done");

console.log("[2] Fixing overview pages...");
const MINOR = new Set(["a","an","the","and","but","or","for","nor","on","at","to","by","in","of","up","as","with"]);
function smartTitle(str) {
  return str.split(" ").map((w, i, arr) => {
    if (/^[A-Z][A-Z0-9\-\.]*$/.test(w) && (w.length <= 5 || w.includes("-") || w.includes("."))) return w;
    if (w === w.toUpperCase() && w.length > 1) {
      const low = w.toLowerCase();
      if (i > 0 && i < arr.length - 1 && MINOR.has(low)) return low;
      return w[0].toUpperCase() + w.slice(1).toLowerCase();
    }
    return w;
  }).join(" ");
}
function cleanHeading(raw) {
  raw = raw.replace(/\s*\[[\d\.\s\-]+\]/g, "");
  raw = raw.replace(/  +/g, " ").trim();
  return smartTitle(raw);
}
const OVERVIEW = ["preliminary-provisions.mdx","marriage.mdx","division-2.5-domestic-partners.mdx","division-3-marriage.mdx","division-4-rights-during-marriage.mdx","division-5-conciliation.mdx","division-6-dissolution.mdx","division-7-property.mdx","division-8-custody.mdx","division-9-support.mdx","division-10-domestic-violence.mdx","division-11-minors.mdx","division-12-parent-child.mdx","division-13-adoption.mdx","division-14-family-law-facilitator.mdx","division-17-support-services.mdx","division-20-pilot-projects.mdx"];
let fixed = 0;
for (const name of OVERVIEW) {
  const p = `${PAGES_DIR}/${name}`;
  try { statSync(p); } catch { continue; }
  let c = readFileSync(p, "utf8");
  c = c.replace(/^(title:\s*")([^"]+)(")/m, (_, a, b, d) => a + cleanHeading(b) + d);
  c = c.replace(/^(description:\s*")([^"]+)(")/m, (_, a, b, d) => a + cleanHeading(b) + d);
  c = c.replace(/^(#{1,4})\s+(.+)$/gm, (_, h, body) => h + " " + cleanHeading(body));
  writeFileSync(p, c, "utf8");
  fixed++;
}
console.log(`   fixed ${fixed} overview pages`);

console.log("[3] Cleaning section pages...");
function getAllMdx(dir) {
  const files = [];
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, e.name);
    if (e.isDirectory()) files.push(...getAllMdx(full));
    else if (e.name.endsWith(".mdx")) files.push(full);
  }
  return files;
}
const skipNames = new Set([...OVERVIEW, "home.mdx"]);
const allMdx = getAllMdx(PAGES_DIR).filter(f => !skipNames.has(basename(f)));
let cleaned = 0;
for (const p of allMdx) {
  let c = readFileSync(p, "utf8");
  const orig = c;
  c = c.replace(/<nav[^>]*class=["']fl-breadcrumb["'][^>]*>[\s\S]*?<\/nav>\s*\n?/g, "");
  c = c.replace(/<span[^>]*class=["']subsec["'][^>]*>([^<]*)<\/span>/g, "$1");
  c = c.replace(/<small>(\[Source\][^<]*)<\/small>/g, "$1");
  c = c.replace(/<span[^>]*class=["']statute-link["'][^>]*>([^<]*)<\/span>/g, "$1");
  c = c.replace(/<span[^>]*class=["']case-statutes["'][^>]*>([^<]*)<\/span>/g, "$1");
  c = c.replace(/<div[^>]*class=["']case-callout["'][^>]*>([\s\S]*?)<\/div>/g, "$1");
  if (c !== orig) { writeFileSync(p, c, "utf8"); cleaned++; }
}
console.log(`   cleaned ${cleaned} section pages`);

console.log("[4] Clearing styles.css...");
writeFileSync(STYLES, "/* California Family Code — no custom styles */\n", "utf8");
console.log("\nAll done.");
