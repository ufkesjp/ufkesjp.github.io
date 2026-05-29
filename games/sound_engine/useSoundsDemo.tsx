import { useState, useCallback, useEffect, useRef } from "react";

// ─── Audio Engine ─────────────────────────────────────────────────────────────

let _ctx = null;
let _reverb = null;

function getCtx() {
  if (!_ctx) _ctx = new (window.AudioContext || window.webkitAudioContext)();
  return _ctx;
}

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

function chord({ root, ratios = [1, 1.5, 2], vols, type = "sine",
  attack = 0.05, release = 0.7, delay = 0, reverbMix = 0.4 }) {
  ratios.forEach((r, i) => {
    tone({
      freq: root * r, type,
      vol: vols ? vols[i] : 0.12 / (i + 1),
      attack: attack + i * 0.01,
      release: release - i * 0.05,
      delay: delay + i * 0.008,
      reverbMix,
    });
  });
}

// ─── Sound Library ────────────────────────────────────────────────────────────

const sounds = {
  select: () => {
    tone({ freq: 740, vol: 0.04, attack: 0.02, release: 0.10, reverbMix: 0.25 });
  },
  cancel: () => {
    tone({ freq: 528, vol: 0.12, attack: 0.04, release: 0.32, reverbMix: 0.35 });
    tone({ freq: 396, vol: 0.08, attack: 0.06, release: 0.35, delay: 0.06, reverbMix: 0.40 });
    tone({ freq: 264, vol: 0.05, attack: 0.08, release: 0.38, delay: 0.12, reverbMix: 0.45 });
  },
  accept: () => {
    chord({
      root: 329, ratios: [1, 1.25, 1.5, 2], vols: [0.14, 0.09, 0.07, 0.05],
      attack: 0.04, release: 0.85, reverbMix: 0.45,
    });
    tone({ freq: 1318, vol: 0.03, attack: 0.08, release: 0.7, delay: 0.12, reverbMix: 0.6 });
  },
  reject: () => {
    tone({ freq: 370, vol: 0.14, attack: 0.006, release: 0.09, reverbMix: 0.15 });
    tone({ freq: 277, vol: 0.11, attack: 0.006, release: 0.08, delay: 0.07, reverbMix: 0.12 });
    tone({ freq: 370, vol: 0.07, attack: 0.006, release: 0.07, delay: 0.14, reverbMix: 0.10 });
  },
  aiOpen: () => {
    tone({ freq: 82,   vol: 0.18, attack: 0.08, release: 0.55, reverbMix: 0.30 });
    tone({ freq: 246,  vol: 0.12, attack: 0.06, release: 0.50, delay: 0.08, reverbMix: 0.45 });
    tone({ freq: 369,  freqEnd: 740, vol: 0.10, attack: 0.05, release: 0.42, delay: 0.14, reverbMix: 0.55 });
    tone({ freq: 740,  vol: 0.07, attack: 0.07, release: 0.38, delay: 0.22, reverbMix: 0.62 });
    tone({ freq: 1108, vol: 0.04, attack: 0.10, release: 0.45, delay: 0.32, reverbMix: 0.70 });
    tone({ freq: 1480, vol: 0.02, attack: 0.12, release: 0.35, delay: 0.44, reverbMix: 0.80 });
  },
  appOpen: () => {
    tone({ freq: 164,  vol: 0.10, attack: 0.06, release: 0.45, reverbMix: 0.40, delay: 0.00 });
    tone({ freq: 246,  vol: 0.09, attack: 0.06, release: 0.45, reverbMix: 0.45, delay: 0.12 });
    tone({ freq: 329,  vol: 0.08, attack: 0.06, release: 0.50, reverbMix: 0.50, delay: 0.22 });
    tone({ freq: 494,  vol: 0.07, attack: 0.06, release: 0.55, reverbMix: 0.55, delay: 0.30 });
    tone({ freq: 659,  vol: 0.05, attack: 0.07, release: 0.60, reverbMix: 0.60, delay: 0.38 });
    tone({ freq: 988,  vol: 0.03, attack: 0.08, release: 0.55, reverbMix: 0.65, delay: 0.46 });
  },
  appClose: () => {
    tone({ freq: 659,  vol: 0.10, attack: 0.03, release: 0.30, reverbMix: 0.35, delay: 0.00 });
    tone({ freq: 494,  vol: 0.09, attack: 0.03, release: 0.30, reverbMix: 0.38, delay: 0.10 });
    tone({ freq: 329,  vol: 0.08, attack: 0.04, release: 0.32, reverbMix: 0.40, delay: 0.18 });
    tone({ freq: 246,  vol: 0.06, attack: 0.04, release: 0.30, reverbMix: 0.42, delay: 0.25 });
    tone({ freq: 164,  vol: 0.05, attack: 0.05, release: 0.35, reverbMix: 0.45, delay: 0.32 });
  },
};

// ─── Idle Drone ───────────────────────────────────────────────────────────────

let _droneOsc = null;
let _droneGain = null;
let _droneLfo = null;

function startIdle() {
  if (_droneOsc) return;
  const ctx = getCtx();
  _droneOsc = ctx.createOscillator();
  _droneGain = ctx.createGain();
  _droneOsc.type = "sine";
  _droneOsc.frequency.value = 82;
  _droneOsc.connect(_droneGain);
  _droneGain.connect(ctx.destination);
  _droneGain.gain.setValueAtTime(0, ctx.currentTime);
  _droneGain.gain.linearRampToValueAtTime(0.018, ctx.currentTime + 2.5);
  _droneLfo = ctx.createOscillator();
  const lfoGain = ctx.createGain();
  _droneLfo.type = "sine";
  _droneLfo.frequency.value = 0.12;
  lfoGain.gain.value = 0.010;
  _droneLfo.connect(lfoGain);
  lfoGain.connect(_droneGain.gain);
  _droneOsc.start();
  _droneLfo.start();
}

function stopIdle() {
  if (!_droneOsc) return;
  const ctx = getCtx();
  _droneGain.gain.linearRampToValueAtTime(0, ctx.currentTime + 1.5);
  setTimeout(() => {
    try { _droneOsc.stop(); _droneLfo.stop(); } catch (_) {}
    _droneOsc = null; _droneGain = null; _droneLfo = null;
  }, 1600);
}

// ─── Demo ─────────────────────────────────────────────────────────────────────

const BUTTONS = [
  { id: "appOpen",  label: "App Open",           desc: "Boot sequence — ascending tones",        color: "#aaddff", group: "lifecycle" },
  { id: "appClose", label: "App Close",           desc: "Shutdown — descending mirror",           color: "#7799bb", group: "lifecycle" },
  { id: "select",   label: "Navigate / Hover",    desc: "Whisper — almost subliminal",            color: "#88ccff", group: "interaction" },
  { id: "accept",   label: "Confirm / Accept",    desc: "Rising glass chord — rings longest",     color: "#66ffbb", group: "interaction" },
  { id: "cancel",   label: "Cancel / Back",       desc: "Receding pool — gentle drift",           color: "#ffcc66", group: "interaction" },
  { id: "reject",   label: "Error / Reject",      desc: "Staccato — clipped and dry",             color: "#ff7777", group: "interaction" },
  { id: "aiOpen",   label: "Open AI Assistant",   desc: "Harmonic awakening — deep to crystal",   color: "#cc99ff", group: "interaction" },
  { id: "idle",     label: "Idle Drone (toggle)", desc: "Background hum — toggle on/off",         color: "#668866", group: "lifecycle" },
];

export default function Demo() {
  const [active, setActive] = useState(null);
  const [droneOn, setDroneOn] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [log, setLog] = useState([{ label: "Click any button to hear it", color: "#333", id: 0 }]);

  const addLog = (label, color) =>
    setLog(prev => [{ id: Date.now(), label, color }, ...prev.slice(0, 7)]);

  const fire = (btn) => {
    if (btn.id === "idle") {
      if (droneOn) { stopIdle(); setDroneOn(false); addLog("Idle drone — stopped", btn.color); }
      else         { startIdle(); setDroneOn(true);  addLog("Idle drone — started (listen closely)", btn.color); }
      return;
    }
    sounds[btn.id]?.();
    setActive(btn.id);
    addLog(btn.label, btn.color);
    setTimeout(() => setActive(null), 400);
    if (btn.id === "aiOpen") setTimeout(() => setChatOpen(true), 250);
  };

  const lifecycle = BUTTONS.filter(b => b.group === "lifecycle");
  const interaction = BUTTONS.filter(b => b.group === "interaction");

  return (
    <div style={{
      minHeight: "100vh", background: "#07090f", color: "#ccc",
      display: "flex", flexDirection: "column", alignItems: "center",
      justifyContent: "center", padding: "40px 24px", gap: 36,
      fontFamily: "'Georgia', serif",
    }}>
      <style>{`
        @keyframes ripple { 0% { box-shadow: 0 0 0 0 var(--c); } 100% { box-shadow: 0 0 0 28px transparent; } }
        @keyframes chatIn { from { opacity:0; transform:translateY(14px) scale(0.96); } to { opacity:1; transform:translateY(0) scale(1); } }
        @keyframes breathe { 0%,100% { opacity:0.5; transform:scale(1); } 50% { opacity:1; transform:scale(1.2); } }
        @keyframes logIn { from { opacity:0; transform:translateX(-8px); } to { opacity:1; transform:translateX(0); } }
        .sbtn { transition: background 0.2s, border-color 0.2s, transform 0.15s, box-shadow 0.2s; cursor: pointer; }
        .sbtn:hover { transform: translateY(-1px); }
        .sbtn:active { transform: scale(0.99); }
      `}</style>

      {/* Header */}
      <div style={{ textAlign: "center" }}>
        <div style={{ fontSize: 10, letterSpacing: "0.3em", color: "#333", marginBottom: 8, fontFamily: "monospace" }}>
          SOUND SYSTEM DEMO — ALL 8 SOUNDS
        </div>
        <div style={{ fontSize: 26, fontWeight: 400, color: "#bbb", letterSpacing: "-0.01em" }}>
          Click to Preview
        </div>
      </div>

      <div style={{ display: "flex", gap: 20, width: "100%", maxWidth: 720, alignItems: "flex-start" }}>

        {/* Left: buttons */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 20 }}>

          {/* Lifecycle group */}
          <div>
            <div style={{ fontSize: 9, letterSpacing: "0.2em", color: "#2a2a3a", marginBottom: 8, fontFamily: "monospace" }}>
              LIFECYCLE
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {lifecycle.map(btn => {
                const isActive = active === btn.id;
                const isDroneBtn = btn.id === "idle";
                const isOn = isDroneBtn && droneOn;
                return (
                  <button key={btn.id} className="sbtn" onClick={() => fire(btn)} style={{
                    "--c": btn.color + "33",
                    display: "flex", alignItems: "center", gap: 16,
                    padding: "14px 20px", borderRadius: 12,
                    border: `1px solid ${isOn || isActive ? btn.color + "77" : btn.color + "1a"}`,
                    background: isOn || isActive ? btn.color + "10" : "transparent",
                    textAlign: "left", width: "100%",
                    animation: isActive ? "ripple 0.5s ease-out" : "none",
                  }}>
                    <div style={{
                      width: 32, height: 32, borderRadius: "50%", flexShrink: 0,
                      background: `radial-gradient(circle at 38% 35%, ${btn.color}55, ${btn.color}11)`,
                      border: `1px solid ${btn.color}33`,
                      boxShadow: isOn ? `0 0 16px ${btn.color}66` : `0 0 6px ${btn.color}11`,
                      transition: "box-shadow 0.4s",
                      animation: isOn ? "breathe 3s ease infinite" : "none",
                    }} />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 13, color: btn.color, marginBottom: 2 }}>
                        {btn.label} {isDroneBtn ? (isOn ? "· ON" : "· OFF") : ""}
                      </div>
                      <div style={{ fontSize: 10, color: "#333", fontFamily: "monospace" }}>{btn.desc}</div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Interaction group */}
          <div>
            <div style={{ fontSize: 9, letterSpacing: "0.2em", color: "#2a2a3a", marginBottom: 8, fontFamily: "monospace" }}>
              INTERACTION
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {interaction.map(btn => {
                const isActive = active === btn.id;
                return (
                  <button key={btn.id} className="sbtn" onClick={() => fire(btn)} style={{
                    "--c": btn.color + "33",
                    display: "flex", alignItems: "center", gap: 16,
                    padding: "14px 20px", borderRadius: 12,
                    border: `1px solid ${isActive ? btn.color + "77" : btn.color + "1a"}`,
                    background: isActive ? btn.color + "10" : "transparent",
                    textAlign: "left", width: "100%",
                    animation: isActive ? "ripple 0.5s ease-out" : "none",
                  }}>
                    <div style={{
                      width: 32, height: 32, borderRadius: "50%", flexShrink: 0,
                      background: `radial-gradient(circle at 38% 35%, ${btn.color}55, ${btn.color}11)`,
                      border: `1px solid ${btn.color}33`,
                      boxShadow: isActive ? `0 0 20px ${btn.color}55` : `0 0 6px ${btn.color}11`,
                      transition: "box-shadow 0.3s",
                    }} />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 13, color: btn.color, marginBottom: 2 }}>{btn.label}</div>
                      <div style={{ fontSize: 10, color: "#333", fontFamily: "monospace" }}>{btn.desc}</div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Right: log */}
        <div style={{ width: 200, flexShrink: 0 }}>
          <div style={{ fontSize: 9, letterSpacing: "0.2em", color: "#2a2a3a", marginBottom: 8, fontFamily: "monospace" }}>
            EVENT LOG
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {log.map((e, i) => (
              <div key={e.id} style={{
                fontSize: 11, color: i === 0 ? e.color : "#2a2a3a",
                fontFamily: "monospace", padding: "6px 10px",
                background: i === 0 ? e.color + "0a" : "transparent",
                borderRadius: 6,
                border: `1px solid ${i === 0 ? e.color + "22" : "transparent"}`,
                animation: i === 0 ? "logIn 0.2s ease" : "none",
                transition: "color 0.3s",
              }}>
                ▶ {e.label}
              </div>
            ))}
          </div>

          {/* Duration guide */}
          <div style={{ marginTop: 24, borderTop: "1px solid #111", paddingTop: 16 }}>
            <div style={{ fontSize: 9, letterSpacing: "0.2em", color: "#2a2a3a", marginBottom: 10, fontFamily: "monospace" }}>
              TAIL LENGTH
            </div>
            {[
              ["reject",   0.1,  "#ff7777"],
              ["select",   0.1,  "#88ccff"],
              ["cancel",   0.4,  "#ffcc66"],
              ["appClose", 0.6,  "#7799bb"],
              ["aiOpen",   0.9,  "#cc99ff"],
              ["accept",   1.0,  "#66ffbb"],
              ["appOpen",  1.1,  "#aaddff"],
            ].map(([name, len, color]) => (
              <div key={name} style={{ marginBottom: 6 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                  <span style={{ fontSize: 9, color: "#2a2a3a", fontFamily: "monospace" }}>{name}</span>
                  <span style={{ fontSize: 9, color, fontFamily: "monospace" }}>{len}s</span>
                </div>
                <div style={{ height: 2, background: "#111", borderRadius: 99 }}>
                  <div style={{
                    height: 2, borderRadius: 99, width: `${(len / 1.1) * 100}%`,
                    background: color, opacity: 0.6,
                  }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* AI Chat Panel */}
      {chatOpen && (
        <div style={{
          position: "fixed", bottom: 28, right: 28, width: 320,
          background: "#090b13", borderRadius: 18, overflow: "hidden",
          border: "1px solid #cc99ff22",
          boxShadow: "0 0 80px #cc99ff14, 0 32px 80px #00000099",
          animation: "chatIn 0.4s cubic-bezier(0.34,1.3,0.64,1)",
          zIndex: 100,
        }}>
          <div style={{
            padding: "16px 22px", borderBottom: "1px solid #cc99ff14",
            display: "flex", alignItems: "center", justifyContent: "space-between",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{
                width: 8, height: 8, borderRadius: "50%", background: "#cc99ff",
                boxShadow: "0 0 10px #cc99ff88", animation: "breathe 3s ease infinite",
              }} />
              <span style={{ fontSize: 11, color: "#cc99ffaa", letterSpacing: "0.18em", fontFamily: "monospace" }}>
                AI ASSISTANT
              </span>
            </div>
            <button onClick={() => { sounds.cancel(); setChatOpen(false); }}
              style={{ background: "none", border: "none", color: "#444", cursor: "pointer", fontSize: 20 }}>×</button>
          </div>
          <div style={{ padding: "20px 22px 22px" }}>
            <div style={{
              fontSize: 13, color: "#cc99ff99", lineHeight: 1.7,
              padding: "14px 16px", background: "#cc99ff07",
              borderRadius: 10, border: "1px solid #cc99ff14", marginBottom: 16,
              fontFamily: "Georgia, serif",
            }}>
              Good evening. How may I assist you?
            </div>
            <div style={{ display: "flex", borderRadius: 10, border: "1px solid #181c28", overflow: "hidden" }}>
              <input placeholder="Ask anything..." onFocus={() => sounds.select()}
                style={{ flex: 1, background: "transparent", border: "none", outline: "none",
                  color: "#aaa", fontSize: 13, padding: "12px 16px", fontFamily: "Georgia, serif" }} />
              <button onClick={() => sounds.accept()}
                style={{ background: "transparent", borderLeft: "1px solid #181c28", border: "none",
                  borderLeft: "1px solid #181c28", color: "#cc99ff88", padding: "12px 16px",
                  cursor: "pointer", fontSize: 10, letterSpacing: "0.15em", fontFamily: "monospace" }}>
                SEND
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
