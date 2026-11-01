/* ------------------------------------------------------------------ *
 *  Sounds, made on the fly with WebAudio (nothing to download): the
 *  blaster's foam "thwump", splats, balloon pops, robot boops and
 *  boings, the star's chime, combo notes, the countdown and a fanfare.
 *  place() puts a sound where it happens (a panner) so you can hear
 *  where a target popped up; the listener follows the head.
 * ------------------------------------------------------------------ */

let ctx = null, master = null, noiseBuf = null;
let muted = false;

export function audioUnlock() {
  if (!ctx) {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    ctx = new AC();
    master = ctx.createGain();
    master.gain.value = 0.8;
    const comp = ctx.createDynamicsCompressor();
    master.connect(comp).connect(ctx.destination);
    noiseBuf = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate);
    const d = noiseBuf.getChannelData(0);
    for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
  }
  if (ctx.state === "suspended") ctx.resume();
}
export const setMuted = m => { muted = m; if (master) master.gain.value = m ? 0 : 0.8; };
export const isMuted = () => muted;

/* the listener at the head: position + forward + up (world) */
export function setListener(pos, fwd, up) {
  if (!ctx) return;
  const L = ctx.listener;
  if (L.positionX) {
    const t = ctx.currentTime;
    L.positionX.setValueAtTime(pos.x, t); L.positionY.setValueAtTime(pos.y, t); L.positionZ.setValueAtTime(pos.z, t);
    L.forwardX.setValueAtTime(fwd.x, t); L.forwardY.setValueAtTime(fwd.y, t); L.forwardZ.setValueAtTime(fwd.z, t);
    L.upX.setValueAtTime(up.x, t); L.upY.setValueAtTime(up.y, t); L.upZ.setValueAtTime(up.z, t);
  } else { L.setPosition(pos.x, pos.y, pos.z); L.setOrientation(fwd.x, fwd.y, fwd.z, up.x, up.y, up.z); }
}

function out(at, gain = 1) {
  const g = ctx.createGain();
  g.gain.value = gain;
  if (at) {
    const p = ctx.createPanner();
    p.panningModel = "HRTF"; p.distanceModel = "inverse"; p.refDistance = 1.2; p.rolloffFactor = 0.8;
    if (p.positionX) { p.positionX.value = at.x; p.positionY.value = at.y; p.positionZ.value = at.z; } else p.setPosition(at.x, at.y, at.z);
    g.connect(p).connect(master);
  } else g.connect(master);
  return g;
}
function tone(dest, type, f0, f1, t0, dur, vol = 0.3) {
  const o = ctx.createOscillator(), g = ctx.createGain();
  o.type = type;
  o.frequency.setValueAtTime(f0, t0);
  if (f1 !== f0) o.frequency.exponentialRampToValueAtTime(Math.max(20, f1), t0 + dur);
  g.gain.setValueAtTime(0.0001, t0);
  g.gain.exponentialRampToValueAtTime(vol, t0 + 0.008);
  g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
  o.connect(g).connect(dest);
  o.start(t0); o.stop(t0 + dur + 0.02);
}
function noise(dest, type, freq, q, t0, dur, vol = 0.3) {
  const s = ctx.createBufferSource(), f = ctx.createBiquadFilter(), g = ctx.createGain();
  s.buffer = noiseBuf;
  s.playbackRate.value = 0.7 + Math.random() * 0.6;
  f.type = type; f.frequency.value = freq; f.Q.value = q;
  g.gain.setValueAtTime(vol, t0);
  g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
  s.connect(f).connect(g).connect(dest);
  s.start(t0, Math.random() * 0.5); s.stop(t0 + dur + 0.02);
}
const ok = () => ctx && !muted;
const now = () => ctx.currentTime;

export const sfx = {
  fire() {
    if (!ok()) return; const t = now(), o = out(null, 0.9);
    noise(o, "bandpass", 1400, 1.2, t, 0.09, 0.5);
    tone(o, "sine", 190, 55, t, 0.13, 0.55);
    tone(o, "triangle", 900 + Math.random() * 200, 300, t, 0.05, 0.12);
  },
  splat(at) {
    if (!ok()) return; const t = now(), o = out(at, 0.8);
    noise(o, "lowpass", 900, 0.8, t, 0.14, 0.5);
    tone(o, "sine", 320, 90, t, 0.08, 0.2);
  },
  pop(at) {
    if (!ok()) return; const t = now(), o = out(at, 1);
    noise(o, "highpass", 2500, 0.7, t, 0.06, 0.8);
    tone(o, "square", 1200, 180, t, 0.09, 0.18);
  },
  ding(at, pitch = 1) {
    if (!ok()) return; const t = now(), o = out(at, 0.8);
    tone(o, "triangle", 880 * pitch, 880 * pitch, t, 0.35, 0.3);
    tone(o, "sine", 1760 * pitch, 1760 * pitch, t, 0.2, 0.12);
  },
  boop(at) {
    if (!ok()) return; const t = now(), o = out(at, 0.7);
    tone(o, "square", 520, 520, t, 0.07, 0.12);
    tone(o, "square", 780, 780, t + 0.08, 0.09, 0.12);
  },
  boing(at) {
    if (!ok()) return; const t = now(), o = out(at, 1);
    const osc = ctx.createOscillator(), g = ctx.createGain(), lfo = ctx.createOscillator(), lg = ctx.createGain();
    osc.type = "sine"; osc.frequency.setValueAtTime(420, t); osc.frequency.exponentialRampToValueAtTime(110, t + 0.5);
    lfo.frequency.value = 18; lg.gain.value = 40; lfo.connect(lg).connect(osc.frequency);
    g.gain.setValueAtTime(0.4, t); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.55);
    osc.connect(g).connect(o); osc.start(t); lfo.start(t); osc.stop(t + 0.6); lfo.stop(t + 0.6);
    tone(o, "square", 990, 660, t, 0.06, 0.1);
  },
  star(at) {
    if (!ok()) return; const t = now(), o = out(at, 0.9);
    [1047, 1319, 1568, 2093].forEach((f, i) => tone(o, "triangle", f, f, t + i * 0.06, 0.3, 0.22));
  },
  combo(level) {
    if (!ok()) return; const t = now(), o = out(null, 0.7);
    const base = 523 * Math.pow(2, Math.min(level, 6) / 6);
    tone(o, "square", base, base, t, 0.08, 0.12);
    tone(o, "square", base * 1.5, base * 1.5, t + 0.08, 0.14, 0.12);
  },
  spawn(at) {
    if (!ok()) return; const t = now(), o = out(at, 0.5);
    tone(o, "sine", 660, 990, t, 0.12, 0.18);
  },
  beep(hi = false) {
    if (!ok()) return; const t = now(), o = out(null, 0.8);
    tone(o, "square", hi ? 880 : 440, hi ? 880 : 440, t, hi ? 0.5 : 0.18, 0.18);
  },
  fanfare() {
    if (!ok()) return; const t = now(), o = out(null, 0.8);
    [[523, 0], [659, 0.14], [784, 0.28], [1047, 0.42], [784, 0.62], [1047, 0.76]].forEach(([f, d]) => {
      tone(o, "square", f, f, t + d, d > 0.7 ? 0.6 : 0.16, 0.13);
      tone(o, "triangle", f / 2, f / 2, t + d, d > 0.7 ? 0.6 : 0.16, 0.12);
    });
  },
  click() {
    if (!ok()) return; const t = now(), o = out(null, 0.5);
    tone(o, "square", 1500, 1500, t, 0.03, 0.08);
  },
  tick() {
    if (!ok()) return; const t = now(), o = out(null, 0.4);
    tone(o, "sine", 1200, 1200, t, 0.05, 0.12);
  },
};
