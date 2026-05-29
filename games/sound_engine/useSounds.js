// useSounds.js
// Drop into your project at: src/sounds/useSounds.js
// No dependencies. No audio files. Works in all modern browsers.

import { useCallback } from "react";

// ─── Audio Context ────────────────────────────────────────────────────────────

let _ctx = null;
let _reverb = null;

function getCtx() {
  if (!_ctx) _ctx = new (window.AudioContext || window.webkitAudioContext)();
  return _ctx;
}

// Algorithmic reverb — exponentially decaying noise convolver
function getReverb() {
  if (_reverb) return _reverb;
  const ctx = getCtx();
  const len = ctx.sampleRate * 1.8;
  const buf = ctx.createBuffer(2, len, ctx.sampleRate);
  for (let c = 0; c < 2; c++) {
    const d = buf.getChannelData(c);
    for (let i = 0; i < len; i++) {
      d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 2.4);
    }
  }
  _reverb = ctx.createConvolver();
  _reverb.buffer = buf;
  _reverb.connect(ctx.destination);
  return _reverb;
}

// ─── Core Tone Builder ────────────────────────────────────────────────────────

function tone({ freq, type = "sine", vol = 0.15, attack = 0.04, release = 0.6,
  freqEnd = null, delay = 0, reverbMix = 0.35 }) {
  const ctx = getCtx();
  const reverb = getReverb();

  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  const dryGain = ctx.createGain();
  const wetGain = ctx.createGain();

  osc.connect(gain);
  gain.connect(dryGain);
  gain.connect(wetGain);
  dryGain.connect(ctx.destination);
  wetGain.connect(reverb);

  dryGain.gain.value = 1 - reverbMix;
  wetGain.gain.value = reverbMix;

  const t = ctx.currentTime + delay;
  osc.type = type;
  osc.frequency.setValueAtTime(freq, t);
  if (freqEnd) osc.frequency.exponentialRampToValueAtTime(freqEnd, t + release * 0.5);

  gain.gain.setValueAtTime(0, t);
  gain.gain.linearRampToValueAtTime(vol, t + attack);
  gain.gain.exponentialRampToValueAtTime(0.0001, t + attack + release);

  osc.start(t);
  osc.stop(t + attack + release + 0.1);
}

function chord({ root, ratios = [1, 1.5, 2], vols, type = "sine",
  attack = 0.05, release = 0.7, delay = 0, reverbMix = 0.4 }) {
  ratios.forEach((r, i) => {
    tone({
      freq: root * r,
      type,
      vol: vols ? vols[i] : 0.12 / (i + 1),
      attack: attack + i * 0.01,
      release: release - i * 0.05,
      delay: delay + i * 0.008,
      reverbMix,
    });
  });
}

// ─── Sound Library ────────────────────────────────────────────────────────────

export const sounds = {

  // Whisper — almost subliminal. Barely registers on a single hover,
  // stays pleasant even through rapid scrolling.
  select: () => {
    tone({ freq: 740, vol: 0.04, attack: 0.02, release: 0.10, reverbMix: 0.25 });
  },

  // Receding pool — gentle harmonic drift. Use on back / dismiss / close.
  cancel: () => {
    tone({ freq: 528, vol: 0.12, attack: 0.04, release: 0.32, reverbMix: 0.35 });
    tone({ freq: 396, vol: 0.08, attack: 0.06, release: 0.35, delay: 0.06, reverbMix: 0.40 });
    tone({ freq: 264, vol: 0.05, attack: 0.08, release: 0.38, delay: 0.12, reverbMix: 0.45 });
  },

  // Rising glass chord — warm major bloom. Rings longest. Use on save / submit / complete.
  accept: () => {
    chord({
      root: 329,
      ratios: [1, 1.25, 1.5, 2],
      vols:   [0.14, 0.09, 0.07, 0.05],
      attack: 0.04, release: 0.85,
      reverbMix: 0.45,
    });
    tone({ freq: 1318, vol: 0.03, attack: 0.08, release: 0.7, delay: 0.12, reverbMix: 0.6 });
  },

  // Staccato denial — clipped, dry, abrupt. Use on error / invalid / forbidden.
  reject: () => {
    tone({ freq: 370, vol: 0.14, attack: 0.006, release: 0.09, reverbMix: 0.15 });
    tone({ freq: 277, vol: 0.11, attack: 0.006, release: 0.08, delay: 0.07, reverbMix: 0.12 });
    tone({ freq: 370, vol: 0.07, attack: 0.006, release: 0.07, delay: 0.14, reverbMix: 0.10 });
  },

  // Harmonic awakening — deep to crystalline. Use exclusively for opening the AI assistant.
  aiOpen: () => {
    tone({ freq: 82,   vol: 0.18, attack: 0.08, release: 0.55, reverbMix: 0.30 });
    tone({ freq: 246,  vol: 0.12, attack: 0.06, release: 0.50, delay: 0.08, reverbMix: 0.45 });
    tone({ freq: 369,  freqEnd: 740, vol: 0.10, attack: 0.05, release: 0.42, delay: 0.14, reverbMix: 0.55 });
    tone({ freq: 740,  vol: 0.07, attack: 0.07, release: 0.38, delay: 0.22, reverbMix: 0.62 });
    tone({ freq: 1108, vol: 0.04, attack: 0.10, release: 0.45, delay: 0.32, reverbMix: 0.70 });
    tone({ freq: 1480, vol: 0.02, attack: 0.12, release: 0.35, delay: 0.44, reverbMix: 0.80 });
  },
};

// ─── Optional: Mute Toggle ────────────────────────────────────────────────────

export let muted = false;
export const toggleMute = () => { muted = !muted; };

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useSounds() {
  const play = useCallback((name) => {
    if (!muted && sounds[name]) sounds[name]();
  }, []);
  return { play };
}
