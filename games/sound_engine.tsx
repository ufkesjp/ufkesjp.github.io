import { useState, useCallback } from "react";

// ─── Audio Engine ─────────────────────────────────────────────────────────────

let _ctx = null;
let _reverb = null;

function getCtx() {
  if (!_ctx) _ctx = new (window.AudioContext || window.webkitAudioContext)();
  return _ctx;
}

// Algorithmic reverb via convolver — gives sounds a room to live in
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

function chord({ root, ratios = [1, 1.5, 2], vols, type = "sine", attack = 0.05,
  release = 0.7, delay = 0, reverbMix = 0.4 }) {
  ratios.forEach((r, i) => {
    tone({
      freq: root * r,
      type,
      vol: (vols ? vols[i] : 0.12 / (i + 1)),
      attack: attack + i * 0.01,
      release: release - i * 0.05,
      delay: delay + i * 0.008,
      reverbMix,
    });
  });
}

// ─── Sound Designs ────────────────────────────────────────────────────────────

export const sounds = {

  // Silk — a single warm sine that barely exists
  select: () => {
    tone({ freq: 740, vol: 0.09, attack: 0.03, release: 0.28, reverbMix: 0.4 });
    tone({ freq: 1108, vol: 0.04, attack: 0.05, release: 0.2, delay: 0.02, reverbMix: 0.45 });
  },

  // Receding pool — gentle harmonic drift downward
  cancel: () => {
    tone({ freq: 528, vol: 0.12, attack: 0.04, release: 0.32, reverbMix: 0.35 });
    tone({ freq: 396, vol: 0.08, attack: 0.06, release: 0.35, delay: 0.06, reverbMix: 0.4 });
    tone({ freq: 264, vol: 0.05, attack: 0.08, release: 0.38, delay: 0.12, reverbMix: 0.45 });
  },

  // Rising glass chord — allowed to ring longer than everything else
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

  // Staccato rejection — clipped, dry, abrupt. Unmistakably cut short.
  reject: () => {
    tone({ freq: 370, vol: 0.14, attack: 0.006, release: 0.09, reverbMix: 0.15 });
    tone({ freq: 277, vol: 0.11, attack: 0.006, release: 0.08, delay: 0.07, reverbMix: 0.12 });
    tone({ freq: 370, vol: 0.07, attack: 0.006, release: 0.07, delay: 0.14, reverbMix: 0.1 });
  },

  // AI Open — halved tails but still the longest, most layered sound
  aiOpen: () => {
    tone({ freq: 82,  vol: 0.18, attack: 0.08, release: 0.55, reverbMix: 0.3 });
    tone({ freq: 246, vol: 0.12, attack: 0.06, release: 0.5,  delay: 0.08, reverbMix: 0.45 });
    tone({ freq: 369, freqEnd: 740, vol: 0.10, attack: 0.05, release: 0.42, delay: 0.14, reverbMix: 0.55 });
    tone({ freq: 740, vol: 0.07, attack: 0.07, release: 0.38, delay: 0.22, reverbMix: 0.62 });
    tone({ freq: 1108, vol: 0.04, attack: 0.10, release: 0.45, delay: 0.32, reverbMix: 0.7 });
    tone({ freq: 1480, vol: 0.02, attack: 0.12, release: 0.35, delay: 0.44, reverbMix: 0.8 });
  },
};

export function useSounds() {
  const play = useCallback((name) => {
    if (sounds[name]) sounds[name]();
  }, []);
  return { play };
}

// ─── Demo ─────────────────────────────────────────────────────────────────────
const BUTTONS = [
  { id: "select",  label: "Navigate / Hover",   desc: "Silk — barely there, warm",              color: "#88ccff" },
  { id: "accept",  label: "Confirm / Accept",   desc: "Rising glass chord — warm major bloom",  color: "#66ffbb" },
  { id: "cancel",  label: "Cancel / Back",      desc: "Receding pool — gentle harmonic drift",  color: "#ffcc66" },
  { id: "reject",  label: "Error / Reject",     desc: "Minor descent — soft but felt",          color: "#ff7777" },
  { id: "aiOpen",  label: "Open AI Assistant",  desc: "Harmonic awakening — deep to crystal",   color: "#cc99ff" },
];

export default function Demo() {
  const { play } = useSounds();
  const [active, setActive] = useState(null);
  const [chatOpen, setChatOpen] = useState(false);

  const fire = (btn) => {
    play(btn.id);
    setActive(btn.id);
    setTimeout(() => setActive(null), 400);
    if (btn.id === "aiOpen") setTimeout(() => setChatOpen(true), 250);
  };

  return (
    <div style={{
      minHeight: "100vh", background: "#07090f",
      display: "flex", flexDirection: "column", alignItems: "center",
      justifyContent: "center", padding: 40, gap: 48,
      fontFamily: "'Georgia', serif",
    }}>
      <style>{`
        @keyframes ripple {
          0%   { box-shadow: 0 0 0 0 var(--c); }
          100% { box-shadow: 0 0 0 32px transparent; }
        }
        @keyframes chatIn {
          from { opacity: 0; transform: translateY(16px) scale(0.96); }
          to   { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes breathe {
          0%,100% { opacity: 0.5; transform: scale(1); }
          50%     { opacity: 1;   transform: scale(1.15); }
        }
        .sbtn { transition: background 0.25s, border-color 0.25s, transform 0.18s, box-shadow 0.25s; }
        .sbtn:hover { transform: translateY(-2px); }
        .sbtn:active { transform: translateY(0px) scale(0.99); }
      `}</style>

      <div style={{ textAlign: "center" }}>
        <div style={{ fontSize: 10, letterSpacing: "0.35em", color: "#333", marginBottom: 10, textTransform: "uppercase", fontFamily: "monospace" }}>
          Harmonic Sound System
        </div>
        <div style={{ fontSize: 30, fontWeight: 400, color: "#ccc", letterSpacing: "-0.01em" }}>
          Soft. Deep. Eloquent.
        </div>
        <div style={{ fontSize: 12, color: "#3a3a4a", marginTop: 8, fontFamily: "monospace" }}>
          Sine waves · Algorithmic reverb · Zero audio files
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10, width: "100%", maxWidth: 500 }}>
        {BUTTONS.map(btn => {
          const isActive = active === btn.id;
          return (
            <button key={btn.id} className="sbtn" onClick={() => fire(btn)} style={{
              "--c": btn.color + "33",
              display: "flex", alignItems: "center", gap: 20,
              padding: "18px 28px", borderRadius: 14, cursor: "pointer",
              border: `1px solid ${isActive ? btn.color + "66" : btn.color + "1a"}`,
              background: isActive ? btn.color + "0e" : "transparent",
              textAlign: "left", width: "100%",
              boxShadow: isActive ? `0 0 32px ${btn.color}22` : "none",
              animation: isActive ? "ripple 0.6s ease-out" : "none",
            }}>
              <div style={{
                width: 38, height: 38, borderRadius: "50%", flexShrink: 0,
                background: `radial-gradient(circle at 38% 35%, ${btn.color}55, ${btn.color}11)`,
                border: `1px solid ${btn.color}33`,
                boxShadow: isActive ? `0 0 24px ${btn.color}44` : `0 0 8px ${btn.color}11`,
                transition: "box-shadow 0.4s",
              }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 14, color: btn.color, fontWeight: 400, marginBottom: 4, letterSpacing: "0.02em" }}>
                  {btn.label}
                </div>
                <div style={{ fontSize: 11, color: "#3a3a50", fontFamily: "monospace", letterSpacing: "0.04em" }}>
                  {btn.desc}
                </div>
              </div>
            </button>
          );
        })}
      </div>

      <div style={{
        width: "100%", maxWidth: 500,
        background: "#0b0d15", border: "1px solid #181c28",
        borderRadius: 12, padding: "20px 24px",
      }}>
        <div style={{ fontSize: 10, color: "#2a2a3a", letterSpacing: "0.2em", marginBottom: 12, fontFamily: "monospace" }}>USAGE IN YOUR APP</div>
        <pre style={{ fontSize: 11, color: "#5a9a7a", margin: 0, lineHeight: 1.9, fontFamily: "monospace" }}>{
`const { play } = useSounds();

onMouseEnter={() => play("select")}
onClick={() => play("accept")}
onClick={() => play("cancel")}
onClick={() => play("reject")}
onClick={() => play("aiOpen")}`
        }</pre>
      </div>

      {chatOpen && (
        <div style={{
          position: "fixed", bottom: 32, right: 32, width: 340,
          background: "#090b13", borderRadius: 20, overflow: "hidden",
          border: "1px solid #cc99ff22",
          boxShadow: "0 0 100px #cc99ff14, 0 40px 80px #00000099",
          animation: "chatIn 0.45s cubic-bezier(0.34,1.3,0.64,1)",
          zIndex: 100,
        }}>
          <div style={{
            padding: "18px 24px", borderBottom: "1px solid #cc99ff14",
            display: "flex", alignItems: "center", justifyContent: "space-between",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div style={{
                width: 8, height: 8, borderRadius: "50%", background: "#cc99ff",
                boxShadow: "0 0 12px #cc99ff88",
                animation: "breathe 3s ease infinite",
              }} />
              <span style={{ fontSize: 11, color: "#cc99ffaa", letterSpacing: "0.2em", fontFamily: "monospace" }}>
                AI ASSISTANT
              </span>
            </div>
            <button onClick={() => { play("cancel"); setChatOpen(false); }}
              style={{ background: "none", border: "none", color: "#333", cursor: "pointer", fontSize: 20, lineHeight: 1, fontFamily: "serif" }}>
              ×
            </button>
          </div>
          <div style={{ padding: "22px 24px 24px" }}>
            <div style={{
              fontSize: 13, color: "#cc99ff99", lineHeight: 1.75,
              padding: "14px 18px", background: "#cc99ff07",
              borderRadius: 12, border: "1px solid #cc99ff14", marginBottom: 18,
              fontFamily: "Georgia, serif",
            }}>
              Good evening. How may I assist you?
            </div>
            <div style={{
              display: "flex", borderRadius: 12,
              border: "1px solid #181c28", overflow: "hidden",
            }}>
              <input
                placeholder="Ask anything..."
                onFocus={() => play("select")}
                style={{
                  flex: 1, background: "transparent", border: "none", outline: "none",
                  color: "#aaa", fontSize: 13, padding: "13px 18px",
                  fontFamily: "Georgia, serif",
                }}
              />
              <button onClick={() => play("accept")} style={{
                background: "transparent",
                borderLeft: "1px solid #181c28", border: "none",
                borderLeft: "1px solid #181c28",
                color: "#cc99ff88", padding: "13px 18px", cursor: "pointer",
                fontSize: 10, letterSpacing: "0.15em", fontFamily: "monospace",
              }}>
                SEND
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
