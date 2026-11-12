// Render project/site-imagery/ogp-card.svg to public/img/ogp.png (1200x630) with Chromium.
// Usage: node project/site-imagery/render.mjs   (requires the `playwright` package and its Chromium)
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

// CommonJS resolution so a globally installed playwright (NODE_PATH) also works.
const { chromium } = createRequire(import.meta.url)('playwright');

const root = fileURLToPath(new URL('../../', import.meta.url));
const svg = await readFile(new URL('./ogp-card.svg', import.meta.url), 'utf8');
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1200, height: 630 }, deviceScaleFactor: 1 });
  await page.setContent(`<!doctype html><html><body style="margin:0;background:#242629">${svg}</body></html>`);
  await page.screenshot({ path: `${root}public/img/ogp.png`, clip: { x: 0, y: 0, width: 1200, height: 630 }, omitBackground: false });
} finally {
  await browser.close();
}
console.log('wrote public/img/ogp.png');
