import React, { useEffect, useRef, useCallback } from "react";

// ============================================================
// DIGITAL ORACLE — v1.0
// ============================================================
// An ancestor-spirit avatar. A luminous presence with structure:
//  - A bright core (the "iris")
//  - Two concentric orbital rings of motes that always rotate,
//    giving it constant motion without nervous energy
//  - A subtle gaze: the rings tilt toward the cursor
//  - Slow, deliberate drift around a center anchor; long
//    pauses between movements
//  - Dramatic asymmetric breathing (quick inhale, long exhale)
//    synchronized across iris, halo, brightness, and breath
//    rings emitted on each inhale peak
//  - Ambient embers drifting up from below — atmosphere
//  - On selection: streaks toward the target, dissolves
//
// Usage:
//   <DigitalOracle prompt="Choose your path" />
//   <button data-wisp-target>...</button>
//
// Imperative trigger:
//   window.__oracleDissipate(targetElement)
// ============================================================

export const ORACLE_VERSION = "1.0";

export default function DigitalOracle({
  hue = 178,
  size = 18,                  // larger, more present
  prompt = "Speak your choice.",
  onDissipate,
}) {
  const wispRef = useRef(null);
  const haloRef = useRef(null);
  const irisRef = useRef(null);
  const ring1Ref = useRef(null);
  const ring2Ref = useRef(null);
  const promptRef = useRef(null);
  const canvasRef = useRef(null);

  const state = useRef({
    cx: window.innerWidth / 2,   // center anchor (where it lives)
    cy: window.innerHeight * 0.42,
    x: window.innerWidth / 2,
    y: window.innerHeight * 0.42,
    tx: window.innerWidth / 2,
    ty: window.innerHeight * 0.42,
    vx: 0, vy: 0,
    t: 0,
    trail: [],
    seeds: [],
    embers: [],
    pulses: [],                  // outward "breath" rings
    motes: [],                   // orbital particles
    mode: "presiding",           // presiding | gazing | drifting | streaking | dissipated
    modeUntil: 0,
    nextDrift: 0,
    nextBreath: 0,
    nextEmber: 0,
    mouse: { x: -9999, y: -9999, active: false },
    gazeX: 0, gazeY: 0,          // smoothed gaze offset
    hoverTarget: null,
    streakTarget: null,
    opacity: 1,
    respawnAt: 0,
    presenceIntensity: 1,        // grows when cursor is far/inactive
  });

  // Initialize orbital motes
  useEffect(() => {
    const s = state.current;
    s.motes = [];
    // Inner ring — 5 motes, faster, smaller
    for (let i = 0; i < 5; i++) {
      s.motes.push({
        ring: 0,
        angle: (i / 5) * Math.PI * 2,
        speed: 0.012 + Math.random() * 0.004,
        radius: size * 2.6,
        size: 1.8 + Math.random() * 0.8,
        phase: Math.random() * Math.PI * 2,
      });
    }
    // Outer ring — 8 motes, slower, varying sizes
    for (let i = 0; i < 8; i++) {
      s.motes.push({
        ring: 1,
        angle: (i / 8) * Math.PI * 2 + 0.3,
        speed: -0.006 - Math.random() * 0.003,  // counter-rotating
        radius: size * 4.5,
        size: 1.2 + Math.random() * 1.4,
        phase: Math.random() * Math.PI * 2,
      });
    }
  }, [size]);

  const dropSeed = useCallback((x, y, count = 1, opts = {}) => {
    const { burst = false, scatter = false } = opts;
    const s = state.current;
    for (let i = 0; i < count; i++) {
      let angle, sp;
      if (scatter) { angle = Math.random() * Math.PI * 2; sp = 2.5 + Math.random() * 4; }
      else if (burst) { angle = Math.random() * Math.PI * 2; sp = 1.5 + Math.random() * 2.5; }
      else { angle = Math.PI / 2 + (Math.random() - 0.5) * 0.8; sp = 0.2 + Math.random() * 0.5; }
      s.seeds.push({
        x: x + (Math.random() - 0.5) * 6,
        y: y + (Math.random() - 0.5) * 6,
        vx: Math.cos(angle) * sp,
        vy: Math.sin(angle) * sp,
        life: 1,
        decay: scatter ? 0.005 + Math.random() * 0.005
             : burst ? 0.012 + Math.random() * 0.01
             : 0.006 + Math.random() * 0.008,
        size: scatter ? 1.4 + Math.random() * 2.4 : 0.8 + Math.random() * 1.8,
        hueShift: (Math.random() - 0.5) * 30,
        twinkle: Math.random() * Math.PI * 2,
        gravity: scatter ? 0.003 : 0.02,
      });
    }
  }, []);

  const spawnEmber = useCallback(() => {
    const s = state.current;
    s.embers.push({
      x: Math.random() * window.innerWidth,
      y: window.innerHeight + 10,
      vx: (Math.random() - 0.5) * 0.3,
      vy: -0.15 - Math.random() * 0.4,
      life: 1,
      decay: 0.0015 + Math.random() * 0.002,
      size: 0.6 + Math.random() * 1.4,
      drift: Math.random() * Math.PI * 2,
      driftSpeed: 0.008 + Math.random() * 0.012,
      hueShift: (Math.random() - 0.5) * 20,
    });
  }, []);

  const triggerBreath = useCallback(() => {
    const s = state.current;
    s.pulses.push({
      x: s.x, y: s.y, radius: size * 1.5, life: 1, decay: 0.012,
    });
  }, [size]);

  const dissipate = useCallback((targetEl) => {
    const s = state.current;
    if (s.mode === "streaking" || s.mode === "dissipated") return;
    s.streakTarget = targetEl;
    s.mode = "streaking";
    s.modeUntil = s.t + 45;
  }, []);

  useEffect(() => {
    window.__oracleDissipate = dissipate;
    return () => { delete window.__oracleDissipate; };
  }, [dissipate]);

  useEffect(() => {
    const onMove = (e) => {
      const s = state.current;
      s.mouse.x = e.clientX; s.mouse.y = e.clientY; s.mouse.active = true;
      const el = document.elementFromPoint(e.clientX, e.clientY);
      const target = el?.closest?.("[data-wisp-target]");
      if (target !== s.hoverTarget) s.hoverTarget = target || null;
    };
    const onLeave = () => { state.current.mouse.active = false; state.current.hoverTarget = null; };
    const onClick = (e) => {
      const el = document.elementFromPoint(e.clientX, e.clientY);
      const target = el?.closest?.("[data-wisp-target]");
      if (target) dissipate(target);
      else dropSeed(e.clientX, e.clientY, 14, { burst: true });
    };
    const onResize = () => {
      const c = canvasRef.current;
      if (c) {
        c.width = window.innerWidth * window.devicePixelRatio;
        c.height = window.innerHeight * window.devicePixelRatio;
        c.style.width = window.innerWidth + "px";
        c.style.height = window.innerHeight + "px";
      }
      const s = state.current;
      s.cx = window.innerWidth / 2;
      s.cy = window.innerHeight * 0.42;
    };
    onResize();
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseleave", onLeave);
    window.addEventListener("click", onClick);
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseleave", onLeave);
      window.removeEventListener("click", onClick);
      window.removeEventListener("resize", onResize);
    };
  }, [dropSeed, dissipate]);

  useEffect(() => {
    let raf;
    const ctx = canvasRef.current.getContext("2d");
    const dpr = window.devicePixelRatio;

    const tick = () => {
      const s = state.current;
      s.t += 1;

      // ---- Atmospheric embers, always ----
      if (s.t >= s.nextEmber) {
        spawnEmber();
        s.nextEmber = s.t + 8 + Math.floor(Math.random() * 14);
      }

      // ---- Gaze: smooth orientation toward cursor ----
      if (s.mouse.active) {
        const dx = s.mouse.x - s.x;
        const dy = s.mouse.y - s.y;
        const dist = Math.hypot(dx, dy);
        const maxOffset = 8;
        const tgx = (dx / Math.max(dist, 1)) * Math.min(dist * 0.05, maxOffset);
        const tgy = (dy / Math.max(dist, 1)) * Math.min(dist * 0.05, maxOffset);
        s.gazeX += (tgx - s.gazeX) * 0.06;
        s.gazeY += (tgy - s.gazeY) * 0.06;
      } else {
        s.gazeX *= 0.96; s.gazeY *= 0.96;
      }

      // ---- Mode logic ----
      if (s.mode === "streaking") {
        if (s.streakTarget) {
          const r = s.streakTarget.getBoundingClientRect();
          s.tx = r.left + r.width / 2;
          s.ty = r.top + r.height / 2;
        }
        if (s.t % 2 === 0) dropSeed(s.x, s.y, 1);
        if (s.t >= s.modeUntil) {
          dropSeed(s.x, s.y, 60, { scatter: true });
          // Big final breath
          s.pulses.push({ x: s.x, y: s.y, radius: size * 2, life: 1, decay: 0.008 });
          s.mode = "dissipated";
          s.opacity = 0;
          s.respawnAt = s.t + 220;
          if (onDissipate) onDissipate(s.streakTarget);
        }
      } else if (s.mode === "dissipated") {
        if (s.t >= s.respawnAt) {
          // Reappear at center, fade in
          s.x = s.cx; s.y = s.cy - 100;
          s.tx = s.cx; s.ty = s.cy;
          s.vx = 0; s.vy = 0; s.trail = []; s.opacity = 1;
          s.mode = "presiding"; s.streakTarget = null;
          s.nextBreath = s.t + 60;
        }
      } else if (s.hoverTarget) {
        const r = s.hoverTarget.getBoundingClientRect();
        s.tx = r.left + r.width / 2;
        s.ty = r.top + r.height / 2 - r.height * 0.6;
        s.mode = "gazing";
      } else {
        if (s.mode === "gazing") {
          // Return to court
          s.tx = s.cx; s.ty = s.cy;
          s.mode = "presiding";
          s.nextDrift = s.t + 120 + Math.floor(Math.random() * 180);
        }

        if (s.mode === "presiding") {
          // Occasional slow drift to a nearby point
          if (s.t >= s.nextDrift) {
            const r = 80 + Math.random() * 140;
            const a = Math.random() * Math.PI * 2;
            s.tx = s.cx + Math.cos(a) * r;
            s.ty = s.cy + Math.sin(a) * r * 0.5; // flatter ellipse — stays upper-screen
            s.mode = "drifting";
            s.modeUntil = s.t + 120;
          }
          // Breath rings now fire automatically on inhale peak (see below)
        } else if (s.mode === "drifting") {
          if (s.t >= s.modeUntil) {
            // Settle back toward center
            s.tx = s.cx; s.ty = s.cy;
            s.mode = "presiding";
            s.nextDrift = s.t + 240 + Math.floor(Math.random() * 360); // 4-10s between drifts
          }
        }
      }

      // ---- Movement: slow, weighted ----
      let followStrength, damping, wobbleScale;
      if (s.mode === "streaking") {
        followStrength = 0.18; damping = 0.78; wobbleScale = 0.3;
      } else if (s.mode === "gazing") {
        followStrength = 0.06; damping = 0.88; wobbleScale = 0.5;
      } else if (s.mode === "drifting") {
        followStrength = 0.025; damping = 0.92; wobbleScale = 0.7;
      } else {
        // presiding — barely moves
        followStrength = 0.02; damping = 0.93; wobbleScale = 0.5;
      }

      // Subtle, slow wobble — breath-like
      const wobbleX = Math.sin(s.t * 0.012) * 6 * wobbleScale;
      const wobbleY = Math.cos(s.t * 0.009) * 4 * wobbleScale;

      const dx = s.tx + wobbleX - s.x;
      const dy = s.ty + wobbleY - s.y;
      s.vx += dx * followStrength;
      s.vy += dy * followStrength;
      s.vx *= damping; s.vy *= damping;
      s.x += s.vx; s.y += s.vy;

      // Trail (shorter, fainter — less restless)
      if (s.mode !== "dissipated") s.trail.push({ x: s.x, y: s.y });
      if (s.trail.length > 18) s.trail.shift();

      // ---- Render canvas (trail, seeds, embers, pulses) ----
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
      ctx.globalCompositeOperation = "lighter";

      // Ambient embers (drift up across whole screen)
      for (let i = s.embers.length - 1; i >= 0; i--) {
        const e = s.embers[i];
        e.drift += e.driftSpeed;
        e.x += e.vx + Math.sin(e.drift) * 0.4;
        e.y += e.vy;
        e.life -= e.decay;
        if (e.life <= 0 || e.y < -20) { s.embers.splice(i, 1); continue; }
        const eHue = hue + e.hueShift;
        const alpha = e.life * 0.5;
        const g = ctx.createRadialGradient(e.x, e.y, 0, e.x, e.y, e.size * 8);
        g.addColorStop(0, `hsla(${eHue}, 90%, 80%, ${alpha})`);
        g.addColorStop(1, `hsla(${eHue + 30}, 80%, 60%, 0)`);
        ctx.fillStyle = g;
        ctx.beginPath(); ctx.arc(e.x, e.y, e.size * 8, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = `hsla(${eHue}, 100%, 92%, ${alpha * 1.4})`;
        ctx.beginPath(); ctx.arc(e.x, e.y, e.size * 0.6, 0, Math.PI * 2); ctx.fill();
      }

      // Breath pulses (slow expanding rings)
      for (let i = s.pulses.length - 1; i >= 0; i--) {
        const p = s.pulses[i];
        p.radius += 1.4;
        p.life -= p.decay;
        if (p.life <= 0) { s.pulses.splice(i, 1); continue; }
        ctx.strokeStyle = `hsla(${hue + 20}, 90%, 70%, ${p.life * 0.35 * s.opacity})`;
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.stroke();
        // inner softer ring
        ctx.strokeStyle = `hsla(${hue}, 95%, 85%, ${p.life * 0.2 * s.opacity})`;
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius * 0.96, 0, Math.PI * 2);
        ctx.stroke();
      }

      // Subtle trail
      if (s.opacity > 0) {
        for (let i = 0; i < s.trail.length; i++) {
          const p = s.trail[i];
          const a = (i / s.trail.length) ** 2.5;
          const r = size * (0.4 + a * 0.8);
          const intensity = s.mode === "streaking" ? 1.8 : 0.7;
          const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, r * 3);
          g.addColorStop(0, `hsla(${hue}, 95%, 75%, ${0.25 * a * intensity * s.opacity})`);
          g.addColorStop(1, `hsla(${hue + 40}, 90%, 55%, 0)`);
          ctx.fillStyle = g;
          ctx.beginPath(); ctx.arc(p.x, p.y, r * 3, 0, Math.PI * 2); ctx.fill();
        }
      }

      // Orbital motes — the constellation around the oracle
      if (s.opacity > 0 && s.mode !== "dissipated") {
        // Gaze tilt: rings squash slightly toward cursor direction
        const gazeAngle = Math.atan2(s.gazeY, s.gazeX);
        const gazeMag = Math.min(1, Math.hypot(s.gazeX, s.gazeY) / 8);
        const tiltAmt = gazeMag * 0.25;

        for (const m of s.motes) {
          m.angle += m.speed;
          // Position with tilt: shrink the orbit along the perpendicular to gaze
          const cosG = Math.cos(gazeAngle), sinG = Math.sin(gazeAngle);
          const localX = Math.cos(m.angle) * m.radius;
          const localY = Math.sin(m.angle) * m.radius;
          // project onto gaze axis (keep full) and perpendicular (squash)
          const along = localX * cosG + localY * sinG;
          const perp  = -localX * sinG + localY * cosG;
          const perpSquashed = perp * (1 - tiltAmt);
          const px = along * cosG - perpSquashed * sinG + s.x;
          const py = along * sinG + perpSquashed * cosG + s.y;

          // Twinkle
          const tw = 0.5 + Math.sin(s.t * 0.06 + m.phase) * 0.5;
          const alpha = (0.6 + tw * 0.4) * s.opacity;
          const mHue = hue + (m.ring === 0 ? 0 : 25);

          const g = ctx.createRadialGradient(px, py, 0, px, py, m.size * 6);
          g.addColorStop(0, `hsla(${mHue}, 100%, 88%, ${alpha})`);
          g.addColorStop(0.4, `hsla(${mHue + 15}, 95%, 70%, ${alpha * 0.4})`);
          g.addColorStop(1, `hsla(${mHue + 40}, 90%, 55%, 0)`);
          ctx.fillStyle = g;
          ctx.beginPath(); ctx.arc(px, py, m.size * 6, 0, Math.PI * 2); ctx.fill();

          // bright core
          ctx.fillStyle = `hsla(${mHue}, 100%, 95%, ${alpha})`;
          ctx.beginPath(); ctx.arc(px, py, m.size * 0.8, 0, Math.PI * 2); ctx.fill();
        }
      }

      // Seeds (from selection burst / streak)
      for (let i = s.seeds.length - 1; i >= 0; i--) {
        const seed = s.seeds[i];
        seed.x += seed.vx; seed.y += seed.vy;
        seed.vx *= 0.98; seed.vy = seed.vy * 0.98 + seed.gravity;
        seed.life -= seed.decay; seed.twinkle += 0.15;
        if (seed.life <= 0) { s.seeds.splice(i, 1); continue; }
        const tw = 0.6 + Math.sin(seed.twinkle) * 0.4;
        const alpha = seed.life * tw;
        const r = seed.size * (1 + (1 - seed.life) * 0.5);
        const sHue = hue + seed.hueShift;
        const g = ctx.createRadialGradient(seed.x, seed.y, 0, seed.x, seed.y, r * 6);
        g.addColorStop(0, `hsla(${sHue}, 100%, 88%, ${alpha})`);
        g.addColorStop(0.3, `hsla(${sHue + 15}, 95%, 70%, ${alpha * 0.5})`);
        g.addColorStop(1, `hsla(${sHue + 40}, 90%, 55%, 0)`);
        ctx.fillStyle = g;
        ctx.beginPath(); ctx.arc(seed.x, seed.y, r * 6, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = `hsla(${sHue}, 100%, 95%, ${alpha})`;
        ctx.beginPath(); ctx.arc(seed.x, seed.y, r * 0.6, 0, Math.PI * 2); ctx.fill();
      }

      ctx.globalCompositeOperation = "source-over";

      // ---- Breathing system: asymmetric inhale/exhale shared by iris + halo + breath rings ----
      // One breath cycle = ~4 seconds (240 frames at 60fps).
      // Phase 0 → 1, where 0..0.35 is inhale (faster), 0.35..1 is exhale (slower).
      const BREATH_PERIOD = 240;
      const breathPhase = (s.t % BREATH_PERIOD) / BREATH_PERIOD;
      // Detect the moment of peak inhale (top of breath) to emit a synchronized pulse
      const prevBreathPhase = ((s.t - 1) % BREATH_PERIOD) / BREATH_PERIOD;
      const justInhaled = prevBreathPhase < 0.35 && breathPhase >= 0.35;
      if (justInhaled && s.mode !== "dissipated" && s.mode !== "streaking") {
        s.pulses.push({ x: s.x, y: s.y, radius: size * 1.5, life: 1, decay: 0.009 });
      }

      // Asymmetric breath curve: 0 (rest) → 1 (peak inhale) → 0 (rest)
      // Uses ease-out on inhale, ease-in on exhale, returning a normalized intensity
      let breathIntensity;
      if (breathPhase < 0.35) {
        // Inhale — accelerating rise
        const p = breathPhase / 0.35;
        breathIntensity = 1 - Math.pow(1 - p, 2.5);  // ease-out
      } else {
        // Exhale — long, slow fall
        const p = (breathPhase - 0.35) / 0.65;
        breathIntensity = Math.pow(1 - p, 1.6);  // ease-in fade
      }

      // Apply dramatic amplitudes
      const breathe = 1 + breathIntensity * 0.18;       // iris swells ~18%
      const haloPulse = 1 + breathIntensity * 0.35;     // halo swells ~35%
      const haloAlpha = 0.6 + breathIntensity * 0.4;    // halo brightens on inhale
      const irisBrightness = 1.1 + breathIntensity * 0.35; // iris brightens on inhale

      const streakStretch = s.mode === "streaking"
        ? 1 + Math.min(1.5, Math.hypot(s.vx, s.vy) * 0.06) : 1;
      const streakAngle = s.mode === "streaking" ? Math.atan2(s.vy, s.vx) : 0;

      if (irisRef.current) {
        irisRef.current.style.opacity = s.opacity;
        irisRef.current.style.filter = `blur(${0.6 + breathIntensity * 0.8}px) brightness(${irisBrightness})`;
        irisRef.current.style.transform =
          `translate3d(${s.x - size + s.gazeX * 0.4}px, ${s.y - size + s.gazeY * 0.4}px, 0) ` +
          `rotate(${streakAngle}rad) scale(${breathe * streakStretch}, ${breathe / Math.sqrt(streakStretch)})`;
      }
      if (haloRef.current) {
        haloRef.current.style.opacity = s.opacity * haloAlpha;
        haloRef.current.style.transform =
          `translate3d(${s.x - size * 5}px, ${s.y - size * 5}px, 0) scale(${haloPulse})`;
      }
      // Prompt fades in/out below the oracle
      if (promptRef.current && prompt) {
        const promptOpacity = s.mode === "presiding"
          ? 0.55 + Math.sin(s.t * 0.015) * 0.25
          : Math.max(0, 0.3 - (s.mode === "dissipated" ? 0.3 : 0));
        promptRef.current.style.opacity = promptOpacity * s.opacity;
        promptRef.current.style.transform =
          `translate3d(${s.x}px, ${s.y + size * 7}px, 0) translateX(-50%)`;
      }

      raf = requestAnimationFrame(tick);
    };

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [dropSeed, spawnEmber, triggerBreath, hue, size, prompt, onDissipate]);

  const styles = `
    .oracle-root { position: fixed; inset: 0; pointer-events: none; z-index: 9999; }
    .oracle-canvas { position: absolute; inset: 0; }
    .oracle-iris {
      position: absolute; top: 0; left: 0;
      width: ${size * 2}px; height: ${size * 2}px;
      border-radius: 50%;
      background:
        radial-gradient(circle at 38% 32%,
          hsla(0, 0%, 100%, 1) 0%,
          hsla(${hue}, 100%, 92%, 0.98) 18%,
          hsla(${hue + 15}, 100%, 78%, 0.85) 38%,
          hsla(${hue + 35}, 95%, 60%, 0.5) 62%,
          hsla(${hue + 55}, 90%, 45%, 0) 85%);
      transition: opacity 0.6s ease-out;
      will-change: transform, opacity, filter;
    }
    .oracle-halo {
      position: absolute; top: 0; left: 0;
      width: ${size * 10}px; height: ${size * 10}px;
      border-radius: 50%;
      background: radial-gradient(circle,
        hsla(${hue}, 95%, 70%, 0.22) 0%,
        hsla(${hue + 30}, 90%, 60%, 0.1) 35%,
        hsla(${hue + 60}, 85%, 50%, 0) 70%);
      filter: blur(14px);
      transition: opacity 0.8s ease-out;
      will-change: transform, opacity;
    }
    .oracle-prompt {
      position: absolute; top: 0; left: 0;
      font-family: 'Cormorant Garamond', 'Iowan Old Style', Georgia, serif;
      font-style: italic;
      font-weight: 300;
      font-size: 1rem;
      letter-spacing: 0.4em;
      text-transform: uppercase;
      color: hsla(${hue}, 60%, 88%, 1);
      text-shadow: 0 0 12px hsla(${hue}, 95%, 70%, 0.4);
      white-space: nowrap;
      pointer-events: none;
      will-change: transform, opacity;
      transition: opacity 0.4s ease-out;
    }
  `;

  return (
    <>
      <style>{styles}</style>
      <div className="oracle-root" aria-hidden="true">
        <canvas ref={canvasRef} className="oracle-canvas" />
        <div ref={haloRef} className="oracle-halo" />
        <div ref={irisRef} className="oracle-iris" />
        {prompt && <div ref={promptRef} className="oracle-prompt">{prompt}</div>}
      </div>
    </>
  );
}
