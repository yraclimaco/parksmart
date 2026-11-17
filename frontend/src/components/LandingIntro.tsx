/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import parkSmartLogoHd from '../assets/parksmart-logo-hd.png';

/** Must match the lift transition in index.css. */
const LEAVE_MS = 700;

/* ---------- Scene geometry (viewBox is 1200 x 600) ---------- */
const R = 55; // turning radius into a stall
const X0 = -120; // where cars enter the lane
const LANE_A = 495; // lane that drives right (into and out of the lot)
const LANE_B = 568; // oncoming lane that drives left
const STALL_TOP = 250;
const STALL_BOTTOM = 440;
const PARK_Y = 335;
const STALL_HALF = 75;
const STALL_X = [150, 300, 450, 600, 750, 900, 1050] as const;
const TINTS = ['#2C4468', '#3A5679', '#4A6690', '#2C4468', '#3A5679', '#4A6690', '#2C4468'] as const;

const BLDG_Y = 48;
const BLDG_H = 104;
const WALK_Y = 184;
const DESTS = [
  { name: 'Library', x: 200, w: 200 },
  { name: 'Price Center', x: 495, w: 290 },
  { name: 'Lecture Hall', x: 785, w: 190 },
  { name: 'Gym', x: 1030, w: 200 },
] as const;

/* ---------- Timeline (seconds). One trip per PERIOD, trips overlap so the loop never pauses ---------- */
const PERIOD = 9;
const LEAVE_AT = 3.2; // a parked car pulls out
const ARRIVE_AT = 4.4; // another car pulls in
const EXIT_AT = 6.4; // the yellow car backs out
const EXIT_DUR = 3.1;
const FADE_AT = 6.0; // route, plates and pin fade before the car leaves
const STATIC_FRAME = 5.6; // frame shown when motion is reduced

interface Trip {
  /** Stall the yellow car parks in. */
  y: number;
  /** Stall that shows the backup plate. */
  backup: number;
  /** Index into DESTS. */
  dest: number;
  /** Stall whose parked car pulls out during this trip. */
  leave: number;
  /** Empty stall another car pulls into during this trip. */
  arrive: number;
}

/** Four trips that leave the lot exactly as they found it, so the loop is seamless. */
const TRIPS: readonly Trip[] = [
  { y: 4, backup: 2, dest: 1, leave: 1, arrive: 0 },
  { y: 2, backup: 4, dest: 0, leave: 5, arrive: 6 },
  { y: 5, backup: 4, dest: 3, leave: 0, arrive: 1 },
  { y: 0, backup: 2, dest: 2, leave: 6, arrive: 5 },
];
const START_OCCUPIED = [1, 3, 5];
/** Which stalls hold a parked car at the start of each trip. */
const OCCUPIED: readonly (readonly number[])[] = (() => {
  let cur = [...START_OCCUPIED];
  return TRIPS.map((t) => {
    const snapshot = [...cur];
    cur = cur.filter((s) => s !== t.leave).concat(t.arrive);
    return snapshot;
  });
})();

/* ---------- Motion helpers ---------- */
interface Pose {
  x: number;
  y: number;
  a: number;
}

const clamp01 = (v: number) => Math.min(1, Math.max(0, v));
const easeOutQuad = (x: number) => 1 - (1 - x) * (1 - x);
const easeOutCubic = (x: number) => 1 - Math.pow(1 - x, 3);
const easeInOut = (x: number) => (x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2);

const entryLen = (cx: number) => cx - R - X0 + (Math.PI * R) / 2 + (STALL_BOTTOM - PARK_Y);
const entryDur = (cx: number) => 1.4 + entryLen(cx) / 650;

/** Along the lane, a left turn into the stall, then straight in. */
const entryPose = (cx: number, sIn: number): Pose => {
  const s = Math.min(Math.max(sIn, 0), entryLen(cx));
  const straight = cx - R - X0;
  if (s <= straight) return { x: X0 + s, y: LANE_A, a: 0 };
  const arc = (Math.PI * R) / 2;
  if (s <= straight + arc) {
    const th = (s - straight) / R;
    return {
      x: cx - R + R * Math.sin(th),
      y: STALL_BOTTOM + R * Math.cos(th),
      a: (-th * 180) / Math.PI,
    };
  }
  return { x: cx, y: STALL_BOTTOM - (s - straight - arc), a: -90 };
};

/** Reverse out, swing round, then drive off to the right. */
const exitPose = (cx: number, tt: number): Pose | null => {
  if (tt < 0 || tt >= EXIT_DUR) return null;
  if (tt < 0.9) {
    return { x: cx, y: PARK_Y + 135 * easeInOut(tt / 0.9), a: -90 };
  }
  if (tt < 1.7) {
    const e = easeInOut((tt - 0.9) / 0.8);
    return { x: cx + 90 * e, y: 470 + (LANE_A - 470) * e, a: -90 * (1 - e) };
  }
  const p = (tt - 1.7) / 1.4;
  return { x: cx + 90 + (1400 - cx - 90) * (0.3 * p + 0.7 * p * p), y: LANE_A, a: 0 };
};

const yellowPose = (cx: number, lt: number): Pose | null => {
  if (lt < 0) return null;
  const d = entryDur(cx);
  if (lt < d) return entryPose(cx, entryLen(cx) * easeOutQuad(lt / d));
  if (lt < EXIT_AT) return { x: cx, y: PARK_Y, a: -90 };
  return exitPose(cx, lt - EXIT_AT);
};

const PIN_PATH = 'M0 0 C -14 -22 -22 -30 -22 -42 A 22 22 0 1 1 22 -42 C 22 -30 14 -22 0 0 Z';

/** Top-down car drawn at the origin facing right (+x). `body` may be a CSS color or var(). */
const CarShape: React.FC<{ body: string; glass?: string; beam?: boolean }> = ({
  body,
  glass = '#182B49',
  beam = false,
}) => (
  <>
    {beam && <polygon className="lp-beam" points="46,-20 200,-70 200,70 46,20" fill="url(#lp-beam)" />}
    <rect x={-42} y={-22} width={92} height={56} rx={16} fill="#000" opacity={0.28} />
    <rect x={-46} y={-28} width={92} height={56} rx={16} style={{ fill: body }} />
    <rect x={6} y={-20} width={24} height={40} rx={6} fill={glass} />
    <rect x={-34} y={-17} width={16} height={34} rx={5} fill={glass} />
    {beam && (
      <>
        <rect x={40} y={-23} width={7} height={12} rx={2} fill="#FFF7CC" />
        <rect x={40} y={11} width={7} height={12} rx={2} fill="#FFF7CC" />
      </>
    )}
  </>
);

const Tree: React.FC<{ x: number; y: number; r: number }> = ({ x, y, r }) => (
  <g>
    <circle cx={x + 5} cy={y + 7} r={r} fill="#000" opacity={0.22} />
    <circle cx={x} cy={y} r={r} fill="#2B6A4F" />
    <circle cx={x - r * 0.2} cy={y - r * 0.2} r={r * 0.62} fill="#38866A" />
  </g>
);

const Chevrons: React.FC<{ x: number; y: number; flip?: boolean }> = ({ x, y, flip = false }) => (
  <g transform={`translate(${x} ${y})${flip ? ' scale(-1 1)' : ''}`} opacity={0.22}>
    <path d="M-14 -11 L4 0 L-14 11 M-34 -11 L-16 0 L-34 11" fill="none" stroke="#F7F8FA" strokeWidth={4} strokeLinecap="round" strokeLinejoin="round" />
  </g>
);

interface LandingIntroProps {
  /** Called once the intro screen is fully gone. */
  onDone: () => void;
}

/**
 * Opening screen that waits for the visitor. A looping lot scene: cars come and go, and a
 * yellow car parks in a different stall and walks to a different building each trip.
 * The screen lifts away only when the visitor presses the button.
 */
export const LandingIntro: React.FC<LandingIntroProps> = ({ onDone }) => {
  const [leaving, setLeaving] = useState(false);
  const leavingRef = useRef(false);
  const [cycle, setCycle] = useState(0);
  const [reduced] = useState(() => {
    try {
      return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    } catch {
      return false;
    }
  });

  const els = useRef<Record<string, SVGElement | null>>({});
  const parkedEls = useRef<(SVGElement | null)[]>([]);
  const laneEls = useRef<(SVGElement | null)[]>([]);
  const bldgEls = useRef<(SVGElement | null)[]>([]);

  const enter = useCallback(() => {
    if (leavingRef.current) return;
    leavingRef.current = true;
    setLeaving(true);
  }, []);

  useEffect(() => {
    if (!leaving) return;
    const doneTimer = window.setTimeout(onDone, LEAVE_MS);
    return () => window.clearTimeout(doneTimer);
  }, [leaving, onDone]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Enter') enter();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [enter]);

  /* The animation loop. Elements are updated directly (not through React state) so it stays smooth. */
  useEffect(() => {
    const E = els.current;
    let lastK = -1;
    let routeLen = 0;
    let raf = 0;

    const attr = (el: SVGElement | null | undefined, name: string, value: string | number) => {
      if (el) el.setAttribute(name, String(value));
    };
    const opacity = (el: SVGElement | null | undefined, v: number) => attr(el, 'opacity', v.toFixed(3));
    const place = (el: SVGElement | null | undefined, p: Pose | null) => {
      if (!el) return;
      if (!p) {
        el.setAttribute('visibility', 'hidden');
        return;
      }
      el.setAttribute('visibility', 'visible');
      el.setAttribute('transform', `translate(${p.x.toFixed(1)} ${p.y.toFixed(1)}) rotate(${p.a.toFixed(1)})`);
    };

    const setupCycle = (k: number) => {
      const t = TRIPS[k % TRIPS.length];
      const cx = STALL_X[t.y];
      const d = DESTS[t.dest];
      const route = `M ${cx} ${STALL_TOP} V ${WALK_Y} H ${d.x} V ${BLDG_Y + BLDG_H + 8}`;
      attr(E.route, 'd', route);
      attr(E.routeMask, 'd', route);
      const path = E.route as unknown as SVGPathElement | null;
      routeLen = path && typeof path.getTotalLength === 'function' ? path.getTotalLength() : 0;
      attr(E.hi, 'transform', `translate(${cx} 0)`);
      attr(E.backup, 'transform', `translate(${STALL_X[t.backup]} 0)`);
      (E.leave as SVGElement | null)?.style.setProperty('--car', TINTS[t.leave]);
      (E.arrive as SVGElement | null)?.style.setProperty('--car', TINTS[t.arrive]);
      setCycle(k);
    };

    const render = (T: number) => {
      const k = Math.floor(T / PERIOD);
      const u = T - k * PERIOD;
      const i = k % TRIPS.length;
      if (k !== lastK) {
        lastK = k;
        setupCycle(k);
      }
      const trip = TRIPS[i];
      const cx = STALL_X[trip.y];
      const dest = DESTS[trip.dest];

      /* Yellow cars: this trip, plus the previous one still driving away */
      [k, k - 1].forEach((kk) => {
        const g = kk % 2 === 0 ? E.yA : E.yB;
        if (kk < 0) {
          place(g, null);
          return;
        }
        const tr = TRIPS[kk % TRIPS.length];
        const lt = kk === k ? u : u + PERIOD;
        const cxk = STALL_X[tr.y];
        place(g, yellowPose(cxk, lt));
        const driving = lt < entryDur(cxk) || lt >= EXIT_AT;
        g?.querySelector('.lp-beam')?.setAttribute('opacity', driving ? '1' : '0');
      });

      /* Other drivers: one pulls out, another pulls in */
      place(E.leave, exitPose(STALL_X[trip.leave], u - LEAVE_AT));
      const cq = STALL_X[trip.arrive];
      const dq = entryDur(cq);
      const ts = u - ARRIVE_AT;
      place(E.arrive, ts >= 0 && ts < dq ? entryPose(cq, entryLen(cq) * easeOutQuad(ts / dq)) : null);

      /* Parked cars follow the occupancy table */
      parkedEls.current.forEach((g, s) => {
        let show = OCCUPIED[i].includes(s);
        if (s === trip.leave) show = u < LEAVE_AT;
        if (s === trip.arrive) show = u >= ARRIVE_AT + dq;
        attr(g, 'visibility', show ? 'visible' : 'hidden');
      });

      /* Oncoming traffic in the far lane */
      laneEls.current.forEach((g, n) => {
        const x = 1360 - ((T * 170 + n * 566) % 1700);
        attr(g, 'transform', `translate(${x.toFixed(1)} ${LANE_B}) rotate(180)`);
      });

      /* Overlays for the yellow car's trip */
      const dY = entryDur(cx);
      const fade = 1 - clamp01((u - FADE_AT) / 0.4);
      const hiO = clamp01((u - (dY - 0.2)) / 0.4) * fade;
      opacity(E.hi, hiO);

      const plateP = clamp01((u - dY) / 0.4);
      attr(E.plateFirst, 'transform', `translate(${cx} ${STALL_TOP + 8 + (1 - easeOutCubic(plateP)) * 10})`);
      opacity(E.plateFirst, plateP * fade);
      const backupP = clamp01((u - dY - 0.3) / 0.4);
      attr(E.plateBackup, 'transform', `translate(${STALL_X[trip.backup]} ${STALL_TOP + 8 + (1 - easeOutCubic(backupP)) * 10})`);
      opacity(E.plateBackup, backupP * fade);
      opacity(E.backup, backupP * fade);

      const rs = dY + 0.5;
      const rp = clamp01((u - rs) / 1.4);
      attr(E.routeMask, 'stroke-dashoffset', (1 - rp).toFixed(3));
      opacity(E.route, u > rs ? fade : 0);

      const path = E.route as unknown as SVGPathElement | null;
      if (E.walker) {
        if (path && routeLen > 0 && u > rs) {
          const pt = path.getPointAtLength(rp * routeLen);
          attr(E.walker, 'cx', pt.x.toFixed(1));
          attr(E.walker, 'cy', pt.y.toFixed(1));
          opacity(E.walker, (1 - clamp01((u - rs - 1.4) / 0.2)) * fade);
        } else {
          opacity(E.walker, 0);
        }
      }

      const arrived = u - (rs + 1.4);
      const pinP = clamp01(arrived / 0.5);
      attr(E.pin, 'transform', `translate(${dest.x} ${BLDG_Y + BLDG_H + 6 - (1 - easeOutCubic(pinP)) * 20})`);
      opacity(E.pin, pinP * fade);
      bldgEls.current.forEach((b, n) => opacity(b, n === trip.dest ? pinP * fade : 0));
      if (E.pulse) {
        const ph = arrived > 0 ? (arrived % 1.5) / 1.5 : 1;
        attr(E.pulse, 'r', (12 + 34 * ph).toFixed(1));
        opacity(E.pulse, (1 - ph) * 0.85 * pinP * fade);
      }
    };

    if (reduced) {
      render(STATIC_FRAME);
      return;
    }
    if (typeof requestAnimationFrame !== 'function') return;

    const start = performance.now();
    const frame = (now: number) => {
      raf = requestAnimationFrame(frame);
      render(Math.max(0, (now - start) / 1000));
    };
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, [reduced]);

  const trip = TRIPS[cycle % TRIPS.length];

  return (
    <div
      className={`lp-intro${leaving ? ' lp-intro--leaving' : ''}`}
      role="dialog"
      aria-label="ParkSmart intro"
    >
      <span className="lp-wordmark lp-intro-brand">
        <img src={parkSmartLogoHd} alt="" className="lp-wordmark-logo" width={52} height={52} />
        ParkSmart
      </span>

      <div className="lp-intro-inner">
        <h1 className="lp-intro-title">
          <span className="lp-fx" style={{ ['--d' as string]: '0.1s' }}>Your car.</span>{' '}
          <span className="lp-fx" style={{ ['--d' as string]: '0.35s' }}>Your spot.</span>{' '}
          <span className="lp-fx" style={{ ['--d' as string]: '0.6s' }}>Your destination.</span>
        </h1>

        <svg
          className="lp-scene"
          viewBox="0 0 1200 600"
          role="img"
          aria-label="A looping scene of a campus parking lot. Cars come and go while a yellow car parks in a different stall each time and a route leads to a different building."
        >
          <defs>
            <linearGradient id="lp-beam" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0" stopColor="#FFF3B0" stopOpacity="0.5" />
              <stop offset="1" stopColor="#FFF3B0" stopOpacity="0" />
            </linearGradient>
            <linearGradient id="lp-ground" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#1B3153" stopOpacity="0" />
              <stop offset="0.22" stopColor="#1B3153" stopOpacity="1" />
            </linearGradient>
            <radialGradient id="lp-glow" cx="50%" cy="40%" r="60%">
              <stop offset="0" stopColor="#2B4D80" stopOpacity="0.55" />
              <stop offset="1" stopColor="#182B49" stopOpacity="0" />
            </radialGradient>
            <pattern id="lp-win" width="18" height="14" patternUnits="userSpaceOnUse">
              <rect x="3" y="3" width="10" height="6" rx="1" fill="#F7F8FA" opacity="0.14" />
            </pattern>
            <mask id="lp-walk-mask" maskUnits="userSpaceOnUse" x={-100} y={0} width={1400} height={600}>
              <path
                ref={(el) => { els.current.routeMask = el; }}
                fill="none"
                stroke="#fff"
                strokeWidth={14}
                strokeLinejoin="round"
                pathLength={1}
                strokeDasharray={1}
                strokeDashoffset={1}
              />
            </mask>
          </defs>

          {/* Ground, walkway, lot, road */}
          <rect x={-3000} y={0} width={7200} height={STALL_BOTTOM} fill="url(#lp-ground)" />
          <ellipse cx={600} cy={230} rx={760} ry={300} fill="url(#lp-glow)" />
          <rect x={40} y={WALK_Y - 16} width={1120} height={32} rx={16} fill="#2C4A75" />
          <rect x={60} y={238} width={1080} height={204} rx={10} fill="#223D63" />
          <rect x={-3000} y={STALL_BOTTOM} width={7200} height={200} fill="#101C31" />
          <rect x={-3000} y={STALL_BOTTOM} width={7200} height={4} fill="#34527F" />
          <line x1={-3000} y1={531} x2={4200} y2={531} stroke="#F7F8FA" strokeOpacity={0.4} strokeWidth={4} strokeDasharray="22 18" />
          <Chevrons x={260} y={LANE_A} />
          <Chevrons x={620} y={LANE_A} />
          <Chevrons x={980} y={LANE_A} />
          <Chevrons x={440} y={LANE_B} flip />
          <Chevrons x={860} y={LANE_B} flip />

          {/* Trees */}
          <Tree x={325} y={104} r={20} />
          <Tree x={665} y={106} r={18} />
          <Tree x={905} y={100} r={19} />
          <Tree x={52} y={112} r={26} />
          <Tree x={1150} y={108} r={26} />
          <Tree x={28} y={330} r={24} />
          <Tree x={1172} y={330} r={24} />

          {/* Buildings */}
          {DESTS.map((d, n) => (
            <g key={d.name}>
              <rect x={d.x - d.w / 2 + 6} y={BLDG_Y + 8} width={d.w} height={BLDG_H} rx={10} fill="#000" opacity={0.25} />
              <rect x={d.x - d.w / 2} y={BLDG_Y} width={d.w} height={BLDG_H} rx={10} fill="#2C4C7C" />
              <rect x={d.x - d.w / 2 + 10} y={BLDG_Y + 34} width={d.w - 20} height={BLDG_H - 60} rx={6} fill="#365C93" />
              <rect x={d.x - d.w / 2 + 10} y={BLDG_Y + 34} width={d.w - 20} height={BLDG_H - 60} rx={6} fill="url(#lp-win)" />
              <rect x={d.x - 16} y={BLDG_Y + BLDG_H - 12} width={32} height={12} rx={3} fill="#FFCD00" opacity={0.45} />
              <text className="lp-scene-bldg" x={d.x} y={BLDG_Y + 23} textAnchor="middle">
                {d.name}
              </text>
              <rect
                ref={(el) => { bldgEls.current[n] = el; }}
                x={d.x - d.w / 2}
                y={BLDG_Y}
                width={d.w}
                height={BLDG_H}
                rx={10}
                fill="none"
                stroke="#FFCD00"
                strokeWidth={5}
                opacity={0}
              />
            </g>
          ))}

          {/* Yellow stall highlight and backup stall */}
          <g ref={(el) => { els.current.hi = el; }} opacity={0}>
            <rect x={-STALL_HALF} y={STALL_TOP} width={STALL_HALF * 2} height={STALL_BOTTOM - STALL_TOP} fill="#FFCD00" fillOpacity={0.2} />
          </g>
          <g ref={(el) => { els.current.backup = el; }} opacity={0}>
            <rect x={-STALL_HALF} y={STALL_TOP} width={STALL_HALF * 2} height={STALL_BOTTOM - STALL_TOP} fill="#F7F8FA" fillOpacity={0.07} />
          </g>

          {/* Stall lines (open at the top, like a real lot) */}
          <path
            d={Array.from({ length: 8 }, (_, n) => `M ${75 + 150 * n} ${STALL_BOTTOM} V ${STALL_TOP}`).join(' ')}
            fill="none"
            stroke="#F7F8FA"
            strokeOpacity={0.8}
            strokeWidth={4}
            strokeLinecap="square"
          />
          <g ref={(el) => { els.current.hiLine = el; }} />

          {/* Parked cars */}
          {STALL_X.map((x, s) => (
            <g
              key={x}
              ref={(el) => { parkedEls.current[s] = el; }}
              transform={`translate(${x} ${PARK_Y}) rotate(-90)`}
              visibility="hidden"
            >
              <CarShape body={TINTS[s]} />
            </g>
          ))}

          {/* Other drivers pulling out and in */}
          <g ref={(el) => { els.current.leave = el; }} visibility="hidden">
            <CarShape body="var(--car)" />
          </g>
          <g ref={(el) => { els.current.arrive = el; }} visibility="hidden">
            <CarShape body="var(--car)" />
          </g>

          {/* Oncoming traffic */}
          {[0, 1, 2].map((n) => (
            <g key={n} ref={(el) => { laneEls.current[n] = el; }} transform={`translate(1400 ${LANE_B}) rotate(180)`}>
              <CarShape body={TINTS[(n * 2 + 1) % TINTS.length]} />
            </g>
          ))}

          {/* The yellow car (two slots so one trip can end while the next begins) */}
          <g ref={(el) => { els.current.yA = el; }} visibility="hidden">
            <CarShape body="#FFCD00" beam />
          </g>
          <g ref={(el) => { els.current.yB = el; }} visibility="hidden">
            <CarShape body="#FFCD00" beam />
          </g>

          {/* Plates */}
          <g ref={(el) => { els.current.plateFirst = el; }} opacity={0}>
            <rect x={-58} y={0} width={116} height={26} rx={5} fill="#FFCD00" />
            <text className="lp-scene-plate" x={0} y={18} textAnchor="middle">First choice</text>
          </g>
          <g ref={(el) => { els.current.plateBackup = el; }} opacity={0}>
            <rect x={-40} y={0} width={80} height={26} rx={5} fill="#F7F8FA" />
            <text className="lp-scene-plate" x={0} y={18} textAnchor="middle">Backup</text>
          </g>

          {/* Walking route and destination pin */}
          <path
            ref={(el) => { els.current.route = el; }}
            fill="none"
            stroke="#FFCD00"
            strokeWidth={5}
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeDasharray="1 11"
            mask="url(#lp-walk-mask)"
            opacity={0}
          />
          <circle ref={(el) => { els.current.walker = el; }} r={7} fill="#FFCD00" stroke="#182B49" strokeWidth={3} opacity={0} />
          <g ref={(el) => { els.current.pin = el; }} opacity={0}>
            <circle ref={(el) => { els.current.pulse = el; }} cx={0} cy={-42} r={12} fill="none" stroke="#FFCD00" strokeWidth={3} opacity={0} />
            <path d={PIN_PATH} fill="#FFCD00" />
            <circle cx={0} cy={-42} r={8} fill="#182B49" />
          </g>
        </svg>

        <p key={cycle} className="lp-intro-caption" aria-hidden="true">
          <span className="lp-intro-caption-dot" />
          <strong>Heading to the {DESTS[trip.dest].name}</strong>
          <span>First choice parked, backup ready</span>
        </p>

        <button
          type="button"
          className="lp-btn lp-btn--yellow lp-intro-cta lp-fx"
          style={{ ['--d' as string]: '0.8s' }}
          onClick={enter}
        >
          Enter ParkSmart
        </button>
      </div>
    </div>
  );
};
