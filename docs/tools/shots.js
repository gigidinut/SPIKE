// Sets up one scene for a manual screenshot (#shot=<name>), then writes the
// page positions of the main parts into <pre id="rects"> for cropping.
(async () => {
  document.documentElement.style.overflow = 'hidden';     // same layout in both passes:
  document.documentElement.style.width = '1400px';        // they see different window widths
  const $ = id => document.getElementById(id);
  const wait = ms => new Promise(r => setTimeout(r, ms));
  const shot = new URLSearchParams(location.hash.slice(1).replace(/^autorun&?/, '')).get('shot');
  const until = async (fn, ms = 600000) => { for (let t = 0; t < ms && !fn(); t += 100) await wait(100); };
  const fileLoaded = () => !$('roverCheck').innerText.startsWith('Loads');
  await until(fileLoaded);
  if (shot === 'overview' || shot === 'logsel') {
    await until(() => /Finished|Error|Time limit/.test($('hudStatus').textContent));
    if (shot === 'logsel') {
      const items = [...document.querySelectorAll('#logList li')];
      const target = items.find(li => li.textContent.includes('step: WEST done')) || items[Math.floor(items.length / 2)];
      target.click(); target.scrollIntoView({ block: 'center' });
    }
  }
  if (shot === 'roverprops') {
    await wait(300);
    const cv = $('rcv'), r = cv.getBoundingClientRect();
    const fire = (type, px, py) => cv.dispatchEvent(new PointerEvent(type, { clientX: r.left + px, clientY: r.top + py, pointerId: 1, bubbles: true }));
    const where = (px, py) => { fire('pointermove', px, py); const m = /x (-?[\d.]+) cm .*y (-?[\d.]+) cm/.exec($('rhint').textContent); return [Number(m[1]), Number(m[2])]; };
    const [ax, ay] = where(100, 100), [bx] = where(200, 200), k = 100 / (bx - ax);
    const px = x => 100 + (x - ax) * k, py = y => 100 - (y - ay) * k;
    fire('pointerdown', px(6.4), py(0)); fire('pointerup', px(6.4), py(0));
    fire('pointermove', px(6.4), py(0));
  }
  if (shot === 'course') document.querySelector('[data-tool="wall"]').click();
  await wait(500);
  const rects = {};
  for (const [name, sel] of Object.entries({ bar: '.bar', toolbar: '.toolbar', stage: '.stage', hud: '.hud', panel: 'aside.panel',
    hint: '#hint', rstage: '.rstage', rtools: '.rtools', props: '#roverProps', check: '#roverCheck', summary: '#roverSummary', match: '#mTurnPoint' })) {
    const el = document.querySelector(sel); if (!el) continue;
    const b = el.getBoundingClientRect(); rects[name] = [b.left, b.top + scrollY, b.width, b.height];
  }
  const pre = document.createElement('pre'); pre.id = 'rects'; pre.textContent = JSON.stringify(rects); document.body.appendChild(pre);
})();
