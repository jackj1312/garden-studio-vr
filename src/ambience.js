/* ------------------------------------------------------------------ *
 *  Ambient sound, generated rather than recorded.
 *
 *  Silence is the single biggest thing that makes a VR scene feel like
 *  a model. A garden has wind, leaves and birds. These are synthesised
 *  from filtered noise and sine sweeps, so there are no audio files to
 *  licence and nothing to download. Starts on the first click, because
 *  browsers will not start audio without one.
 * ------------------------------------------------------------------ */

export function createAmbience() {
  let ctx = null, master = null, muffle = null;
  let windFilter, windGain, leafGain;
  let started = false;
  let timeKey = "midday";
  let insideTarget = 0, inside = 0;
  let gustPhase = 0, gust = 0.5;
  let birdTimer = 2;
  let stepBuf = null;

  function noiseBuffer(seconds, kind) {
    const n = Math.floor(ctx.sampleRate * seconds);
    const buf = ctx.createBuffer(1, n, ctx.sampleRate);
    const d = buf.getChannelData(0);
    let last = 0;
    for (let i = 0; i < n; i++) {
      const w = Math.random() * 2 - 1;
      if (kind === "brown") {
        last = (last + 0.02 * w) / 1.02;
        d[i] = last * 3.5;
      } else {
        d[i] = w;
      }
    }
    return buf;
  }

  function loop(buffer, filter, gain) {
    const src = ctx.createBufferSource();
    src.buffer = buffer;
    src.loop = true;
    src.connect(filter).connect(gain).connect(master);
    src.start(0, Math.random() * buffer.duration);
    return src;
  }

  function start() {
    if (started) return;
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    started = true;
    ctx = new AC();

    master = ctx.createGain();
    master.gain.value = 0;
    muffle = ctx.createBiquadFilter();
    muffle.type = "lowpass";
    muffle.frequency.value = 18000;
    master.connect(muffle).connect(ctx.destination);

    // wind: a deep rolling bed
    windFilter = ctx.createBiquadFilter();
    windFilter.type = "lowpass";
    windFilter.frequency.value = 420;
    windFilter.Q.value = 0.6;
    windGain = ctx.createGain();
    windGain.gain.value = 0.32;
    loop(noiseBuffer(6, "brown"), windFilter, windGain);

    // leaves: a hiss that comes and goes with the gusts
    const leafFilter = ctx.createBiquadFilter();
    leafFilter.type = "bandpass";
    leafFilter.frequency.value = 2800;
    leafFilter.Q.value = 0.8;
    leafGain = ctx.createGain();
    leafGain.gain.value = 0.04;
    loop(noiseBuffer(5, "white"), leafFilter, leafGain);

    stepBuf = noiseBuffer(0.35, "white");
    master.gain.linearRampToValueAtTime(0.85, ctx.currentTime + 3.5);
    if (ctx.state === "suspended") ctx.resume();
  }

  /* One bird: a few short notes, each a quick upward sweep. Random
     pitch, count and stereo position, so no two calls are the same. */
  function chirp() {
    const t0 = ctx.currentTime + 0.05;
    const pan = ctx.createStereoPanner();
    pan.pan.value = Math.random() * 1.6 - 0.8;
    const voice = ctx.createGain();
    voice.gain.value = 0.9;
    voice.connect(pan).connect(master);

    const notes = 2 + Math.floor(Math.random() * 3);
    const base = 2300 + Math.random() * 1900;
    let t = t0;
    for (let i = 0; i < notes; i++) {
      const o = ctx.createOscillator();
      o.type = "sine";
      const f0 = base * (0.92 + Math.random() * 0.2);
      const f1 = f0 * (1.12 + Math.random() * 0.35);
      o.frequency.setValueAtTime(f0, t);
      o.frequency.exponentialRampToValueAtTime(f1, t + 0.07);
      o.frequency.exponentialRampToValueAtTime(f0 * 0.96, t + 0.15);
      const env = ctx.createGain();
      env.gain.setValueAtTime(0.0001, t);
      env.gain.exponentialRampToValueAtTime(0.07, t + 0.02);
      env.gain.exponentialRampToValueAtTime(0.0001, t + 0.17);
      o.connect(env).connect(voice);
      o.start(t);
      o.stop(t + 0.2);
      t += 0.16 + Math.random() * 0.14;
    }
  }

  /* One footstep on grass: a burst of band-passed noise and a low thud,
     pitch and timing jittered so no two are the same. */
  function step() {
    if (!started) return;
    const t = ctx.currentTime;
    const src = ctx.createBufferSource();
    src.buffer = stepBuf;
    src.playbackRate.value = 0.85 + Math.random() * 0.3;
    const bp = ctx.createBiquadFilter();
    bp.type = "bandpass";
    bp.frequency.value = 1300 + Math.random() * 900;
    bp.Q.value = 0.7;
    const g = ctx.createGain();
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(0.22 + Math.random() * 0.1, t + 0.008);
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.1 + Math.random() * 0.05);
    src.connect(bp).connect(g).connect(master);
    src.start(t); src.stop(t + 0.25);

    const o = ctx.createOscillator();
    o.type = "sine";
    o.frequency.setValueAtTime(95, t);
    o.frequency.exponentialRampToValueAtTime(52, t + 0.08);
    const og = ctx.createGain();
    og.gain.setValueAtTime(0.0001, t);
    og.gain.exponentialRampToValueAtTime(0.16, t + 0.006);
    og.gain.exponentialRampToValueAtTime(0.0001, t + 0.1);
    o.connect(og).connect(master);
    o.start(t); o.stop(t + 0.12);
  }

  function update(dt) {
    if (!started) return;

    // gusts: a slow random walk, so the wind breathes rather than drones
    gustPhase += dt * (0.25 + Math.random() * 0.1);
    const wander = (Math.random() - 0.5) * dt * 0.6;
    gust = Math.min(1, Math.max(0, gust + wander + Math.sin(gustPhase) * dt * 0.15));
    const now = ctx.currentTime;
    windFilter.frequency.setTargetAtTime(300 + gust * 650, now, 0.4);
    windGain.gain.setTargetAtTime(0.22 + gust * 0.28, now, 0.4);
    leafGain.gain.setTargetAtTime(0.015 + gust * gust * 0.12, now, 0.25);

    // birds: frequent at midday, sparse at dusk
    birdTimer -= dt;
    if (birdTimer <= 0) {
      chirp();
      birdTimer = (timeKey === "night" ? 16 : timeKey === "dusk" ? 7 : timeKey === "golden" ? 4 : 2.5) + Math.random() * 6;
    }

    // inside the studio everything goes dull and quiet, which is how a
    // closed room sounds and a large part of why it feels enclosed
    inside += (insideTarget - inside) * Math.min(1, dt * 3);
    muffle.frequency.setTargetAtTime(18000 - inside * 17000, now, 0.1);
    master.gain.setTargetAtTime(0.85 - inside * 0.5, now, 0.1);
  }

  return {
    start,
    update,
    step,
    setInside(b) { insideTarget = b ? 1 : 0; },
    setTime(k) { timeKey = k; },
    get started() { return started; }
  };
}
