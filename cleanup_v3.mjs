import { readFileSync, writeFileSync, readdirSync } from "fs";
import { join, basename } from "path";

const PAGES_DIR = "/home/runner/workspace/fern/docs/pages";

const MINOR = new Set(["a","an","the","and","but","or","for","nor","on","at","to","by","in","of","up","as","with","from","into","over","than"]);

function smartTitle(str) {
  const words = str.split(" ");
  return words.map((w, i) => {
    const isAllCaps = w === w.toUpperCase() && /[A-Z]/.test(w);
    if (!isAllCaps) return w;
    const low = w.toLowerCase();
    // Minor words in the middle → always lowercase
    if (i > 0 && i < words.length - 1 && MINOR.has(low)) return low;
    // Preserve ONLY hyphenated codes (IV-D) and dot-codes — no length threshold
    if (w.includes("-") || w.includes(".")) return w;
    // Everything else ALL CAPS → title-case
    return w[0].toUpperCase() + w.slice(1).toLowerCase();
  }).join(" ");
}

function cleanHeading(raw) {
  raw = raw.replace(/\s*\[[\d\.\s\-]+\]/g, "");
  raw = raw.replace(/  +/g, " ").trim();
  raw = raw.replace(/—/g, " - ");
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

const OVERVIEW = new Set([
  "preliminary-provisions.mdx","marriage.mdx","division-2.5-domestic-partners.mdx",
  "division-3-marriage.mdx","division-4-rights-during-marriage.mdx","division-5-conciliation.mdx",
  "division-6-dissolution.mdx","division-7-property.mdx","division-8-custody.mdx",
  "division-9-support.mdx","division-10-domestic-violence.mdx","division-11-minors.mdx",
  "division-12-parent-child.mdx","division-13-adoption.mdx","division-14-family-law-facilitator.mdx",
  "division-17-support-services.mdx","division-20-pilot-projects.mdx","home.mdx",
]);

let fixed = 0;

for (const fpath of getAllMdx(PAGES_DIR)) {
  const fname = basename(fpath);
  let c = readFileSync(fpath, "utf8");
  const orig = c;

  // 1. Fix ALL CAPS everywhere in frontmatter title/description
  c = c.replace(/^(title:\s*")([^"]+)(")/m,       (_, a, b, d) => a + cleanHeading(b) + d);
  c = c.replace(/^(description:\s*")([^"]+)(")/m, (_, a, b, d) => a + cleanHeading(b) + d);

  // 2. Fix ALL CAPS in markdown headings (overview pages only — section pages have no ## headings)
  if (OVERVIEW.has(fname)) {
    c = c.replace(/^(#{1,4})\s+(.+)$/gm, (_, h, body) => h + " " + cleanHeading(body));

    // 3. Remove the first H1 heading in overview page content (Fern renders title from frontmatter)
    //    Pattern: after the closing ---\n of frontmatter, strip any leading blank lines + H1 line
    c = c.replace(
      /^(---\n(?:[^\n]*\n)*---\n)\n*(# [^\n]+)\n+/m,
      "$1\n"
    );
  }

  if (c !== orig) {
    writeFileSync(fpath, c, "utf8");
    fixed++;
  }
}

console.log(`Fixed ${fixed} files`);
