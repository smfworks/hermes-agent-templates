#!/usr/bin/env node
// Accessibility scanner: axe-core in headless Chromium, desktop 1280x900.
// Usage: node axe_scan.js [--json out.json] URL [URL...]
//
// Port of SPEC.md Appendix A.1 (Grok Bot axe/scan.js), identical logic and output:
// per URL prints "### <url> -> <final url>", a JSON line of violation node counts
// by impact, the violations sorted critical->minor with up to 3 nodes each
// (selector | html snippet | failure summary), then LINKS (up to 8 same-origin).
// Allowed additions only: --json <path> (per-URL results incl. selectors, HTML
// snippets and failure summaries), and Chromium discovery via CHROME_PATH or
// Playwright/distro Chromium. Never assumes /usr/bin/google-chrome.

const p = require('puppeteer-core'),
      fs = require('fs'),
      os = require('os'),
      path = require('path'),
      { spawnSync } = require('child_process'),
      src = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8');

const IMPACTS = ['critical', 'serious', 'moderate', 'minor'];

// Chromium discovery: CHROME_PATH first, then Playwright's bundled Chromium,
// then distro chromium. No hardcoded Google Chrome path anywhere.
function findChrome() {
  if (process.env.CHROME_PATH) {
    const p_ = process.env.CHROME_PATH;
    if (fs.existsSync(p_)) return p_;
    console.error(`CHROME_PATH is set but not found: ${p_}`);
    process.exit(1);
  }
  const pwRoot = path.join(os.homedir(), '.cache', 'ms-playwright');
  if (fs.existsSync(pwRoot)) {
    for (const d of fs.readdirSync(pwRoot).sort().reverse()) {
      if (!d.startsWith('chromium')) continue;
      for (const sub of ['chrome-linux64', 'chrome-linux']) {
        const candidate = path.join(pwRoot, d, sub, 'chrome');
        if (fs.existsSync(candidate)) return candidate;
      }
    }
  }
  for (const name of ['chromium', 'chromium-browser']) {
    const w = spawnSync('which', [name], { encoding: 'utf8' });
    if (w.status === 0 && w.stdout.trim()) return w.stdout.trim();
  }
  for (const candidate of ['/usr/bin/chromium', '/usr/bin/chromium-browser']) {
    if (fs.existsSync(candidate)) return candidate;
  }
  console.error('No Chromium found. Set CHROME_PATH to a Chromium/Chrome binary ' +
                '(e.g. ~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome or /usr/bin/chromium).');
  process.exit(1);
}

const argv = process.argv.slice(2);
let jsonPath = null;
const urls = [];
for (let i = 0; i < argv.length; i++) {
  if (argv[i] === '--json') {
    jsonPath = argv[i + 1] || null;
    if (!jsonPath || jsonPath.startsWith('--')) {
      console.error('--json requires an output path');
      process.exit(1);
    }
    i++;
  } else if (argv[i] === '--help' || argv[i] === '-h') {
    console.log('Usage: node axe_scan.js [--json out.json] URL [URL...]');
    process.exit(0);
  } else {
    urls.push(argv[i]);
  }
}
if (!urls.length) { console.log('Usage: node axe_scan.js [--json out.json] URL [URL...]'); process.exit(1); }

(async () => {
  let browser;
  try {
    browser = await p.launch({ executablePath: findChrome(), args: ['--no-sandbox'] });
  } catch (e) {
    console.error(`Browser launch failed: ${e.message}`);
    console.error('Set CHROME_PATH to a Chromium/Chrome binary and retry.');
    process.exit(1);
  }
  const results = [];
  for (const u of urls) {
    const pg = await b_newPage(browser);
    await pg.setViewport({ width: 1280, height: 900 });
    const entry = { url: u };
    try {
      await pg.goto(u, { waitUntil: 'networkidle2', timeout: 60000 });
      await new Promise(r => setTimeout(r, 2000));
      await pg.evaluate(src);
      const r = await pg.evaluate(() => axe.run({ resultTypes: ['violations'] }));
      const finalUrl = pg.url();
      console.log('### ' + u + ' -> ' + finalUrl);
      const o = { critical: 0, serious: 0, moderate: 0, minor: 0 };
      r.violations.forEach(v => o[v.impact] += v.nodes.length);
      console.log(JSON.stringify(o));
      const violations = r.violations
        .slice()
        .sort((a, b) => IMPACTS.indexOf(a.impact) - IMPACTS.indexOf(b.impact))
        .map(v => {
          console.log(`- ${v.impact} ${v.id} (${v.nodes.length}): ${v.help}`);
          const nodes = v.nodes.slice(0, 3).map(n => {
            console.log('   ' + n.target.join(' ') + ' | ' + n.html.slice(0, 120).replace(/\n/g, ' ') + ' | ' + (n.failureSummary || '').split('\n')[1]?.slice(0, 120));
            return { target: n.target, html: n.html.slice(0, 120), failureSummary: n.failureSummary || '' };
          });
          return { id: v.id, impact: v.impact, help: v.help, description: v.description || '', nodes, nodeCount: v.nodes.length };
        });
      const links = await pg.evaluate(() => [...new Set([...document.querySelectorAll('a[href]')].map(a => a.href).filter(h => h.startsWith(location.origin) && !h.includes('#')))].slice(0, 8));
      console.log('LINKS', links.join(' '));
      Object.assign(entry, { finalUrl, counts: o, violations, links });
    } catch (e) {
      console.log('### ' + u + ' FAIL ' + e.message);
      entry.error = e.message;
    }
    results.push(entry);
    await pg.close();
  }
  await browser.close();
  if (jsonPath) fs.writeFileSync(jsonPath, JSON.stringify(results, null, 2) + '\n');
})();

async function b_newPage(browser) { return browser.newPage(); }
