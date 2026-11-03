// Cold desktop switch in the measured lounge. Runs only on the local test server.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const puppeteer = require(process.env.PUPPETEER_CORE || 'puppeteer-core');

async function main() {
  const origin = new URL(process.env.STUDIO_URL || 'https://127.0.0.1:8450');
  assert.equal(origin.protocol, 'https:');
  assert.equal(origin.port, '8450');
  assert(['127.0.0.1', '192.168.1.118'].includes(origin.hostname));
  const preview = origin.hostname !== '127.0.0.1';
  const route = preview ? '/preview/?version=approved_2b' : '/house.html?site=house&version=approved_2b&mode=review';
  const browser = await puppeteer.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true,
    args: ['--ignore-certificate-errors', '--disable-background-networking', '--use-angle=metal'],
  });
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1100, height: 700 });
    await page.goto(new URL(route, origin).href, { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => window.__house?.V && !document.querySelector('#startDesktop').disabled, { timeout: 240000 });
    await page.click('#startDesktop');
    const switches = await page.evaluate(async () => {
      const house = window.__house, frame = () => new Promise(requestAnimationFrame);
      house.feet.set(2, .002, -2.6);
      house.yawPitch.yaw = 1;
      house.step(3);
      for (let i = 0; i < 20; i++) await frame();
      const result = [];
      for (const on of [true,false]) {
        let previous = await frame(), longest = 0;
        const count = house.renderer.info.programs.length;
        document.querySelector('#baAllLamps').click();
        for (let i = 0; i < 10; i++) {
          const now = await frame();
          longest = Math.max(longest, now - previous);
          previous = now;
        }
        result.push({ on, ms: Math.round(longest), counts: [count, house.renderer.info.programs.length],
          lit: [...new Set(house.look.snapshot().emitters.map(light => light.id))] });
      }
      return result;
    });
    const filename = preview ? 'house-lights-wifi.json' : 'house-lights-local.json';
    const dir = path.resolve(__dirname, '../../renders/garden-tool/performance');
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, filename), JSON.stringify(switches, null, 2));
    assert(switches[0].lit.includes('LIV-TLAMP') && switches[1].lit.length === 0);
    for (const s of switches) assert(s.ms < 500, String(s.on) + ' lamp switch stalled for ' + s.ms + ' ms');
    console.log(switches);
  } finally {
    await browser.close();
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
