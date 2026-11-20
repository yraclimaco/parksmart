/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';

/** How long a dash takes to fade out, in milliseconds. */
const TRAIL_LIFE_MS = 650;
/** Minimum distance between trail points, in pixels. Keeps the trail light on fast mice. */
const TRAIL_STEP_PX = 4;
/** Hard cap on stored trail points. */
const TRAIL_MAX_POINTS = 120;
/**
 * One dashed line down the middle behind the car, like the centre line on a road. Dashes are
 * tied to distance travelled (not to the fading tail), so they never shuffle as the trail fades.
 */
const DASH_LENGTH_PX = 11;
const DASH_PERIOD_PX = 20;
const DASH_WIDTH_PX = 2.8;
/** How quickly the car turns toward its heading (0-1 per frame). */
const TURN_RATE = 0.22;
/** Movement below this many pixels per frame does not change the heading. */
const MIN_TURN_MOVE_PX = 1.5;
/** Car scale over buttons, links and other things you can press. */
const HOVER_SCALE = 1.3;
/** Car scale while a button is held down: a quick squash. */
const PRESS_SCALE = 0.78;
/** Click ripple: how long it lasts and how far it spreads. */
const RIPPLE_LIFE_MS = 450;
const RIPPLE_START_PX = 8;
const RIPPLE_END_PX = 38;
const REST_SCALE = 1;

const INTERACTIVE = 'a, button, summary, input, select, textarea, label, [role="button"], [role="radio"]';
const BRAND_YELLOW = '#FFCD00';
const BRAND_NAVY = '#182B49';
const PAINT_WHITE = '#F7F8FA';

interface Ripple {
  x: number;
  y: number;
  t: number;
}

interface TrailPoint {
  x: number;
  y: number;
  t: number;
  /** Total distance the pointer had travelled when this point was recorded. */
  d: number;
}

/** True only for a real mouse or trackpad and when the visitor has not asked for less motion. */
const canUseCarCursor = (): boolean => {
  try {
    return (
      window.matchMedia('(hover: hover) and (pointer: fine)').matches &&
      !window.matchMedia('(prefers-reduced-motion: reduce)').matches
    );
  } catch {
    return false;
  }
};

/** Draws the car (nose pointing along +x) centred on the origin. */
function drawCar(ctx: CanvasRenderingContext2D) {
  ctx.fillStyle = 'rgba(16, 29, 51, 0.28)';
  ctx.beginPath();
  ctx.ellipse(1, 3, 19, 11, 0, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = BRAND_YELLOW;
  ctx.strokeStyle = BRAND_NAVY;
  ctx.lineWidth = 1.75;
  ctx.beginPath();
  ctx.roundRect(-17, -9, 34, 18, 6);
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = 'rgba(24, 43, 73, 0.9)';
  ctx.beginPath();
  ctx.roundRect(2, -6.5, 7, 13, 2);
  ctx.fill();
  ctx.fillStyle = 'rgba(24, 43, 73, 0.65)';
  ctx.beginPath();
  ctx.roundRect(-11, -6.5, 4, 13, 1.5);
  ctx.fill();

  ctx.fillStyle = PAINT_WHITE;
  ctx.beginPath();
  ctx.arc(15.5, -5.5, 1.6, 0, Math.PI * 2);
  ctx.arc(15.5, 5.5, 1.6, 0, Math.PI * 2);
  ctx.fill();
}

/**
 * Landing-page cursor: a small yellow car at the pointer that turns toward where it is
 * heading and leaves a single dashed black line, like the centre line on a road, that fades away. Only for a mouse or trackpad and only
 * when reduced motion is off; everyone else keeps the normal cursor.
 */
export const CarCursor: React.FC = () => {
  const canvasRef = React.useRef<HTMLCanvasElement | null>(null);
  const [enabled] = React.useState(canUseCarCursor);

  React.useEffect(() => {
    if (!enabled) return;
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return;

    // On <body>, not the landing div: React rewrites that div's className on every render
    document.body.classList.add('ps-car-cursor');

    let width = 0;
    let height = 0;
    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();

    const trail: TrailPoint[] = [];
    const ripples: Ripple[] = [];
    let pressed = false;
    let hoverScale = REST_SCALE;
    const pos = { x: 0, y: 0 };
    let heading = 0;
    let scale = REST_SCALE;
    let targetScale = REST_SCALE;
    let visible = false;
    let raf = 0;
    let lastMoveTime = 0;
    let prev = { x: 0, y: 0 };
    let travelled = 0;

    const frame = (now: number) => {
      ctx.clearRect(0, 0, width, height);

      // Heading follows the direction of travel, turning the short way round
      const dx = pos.x - prev.x;
      const dy = pos.y - prev.y;
      if (Math.hypot(dx, dy) > MIN_TURN_MOVE_PX) {
        const target = Math.atan2(dy, dx);
        let diff = target - heading;
        while (diff > Math.PI) diff -= Math.PI * 2;
        while (diff < -Math.PI) diff += Math.PI * 2;
        heading += diff * TURN_RATE;
      }
      prev = { x: pos.x, y: pos.y };
      scale += (targetScale - scale) * 0.25;

      while (trail.length && now - trail[0].t > TRAIL_LIFE_MS) trail.shift();
      while (ripples.length && now - ripples[0].t > RIPPLE_LIFE_MS) ripples.shift();

      // Click ripple: a ring that spreads and fades, navy under white so it shows on any section
      for (const r of ripples) {
        const p = (now - r.t) / RIPPLE_LIFE_MS;
        const eased = 1 - Math.pow(1 - p, 3);
        const radius = RIPPLE_START_PX + (RIPPLE_END_PX - RIPPLE_START_PX) * eased;
        ctx.beginPath();
        ctx.arc(r.x, r.y, radius, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(24, 43, 73, ${0.45 * (1 - p)})`;
        ctx.lineWidth = 6;
        ctx.stroke();
        ctx.strokeStyle = `rgba(255, 205, 0, ${1 - p})`;
        ctx.lineWidth = 3.5;
        ctx.stroke();
      }

      // One black dashed line, like the centre line on a road. Each trail segment is cut at the
      // dash boundaries (measured in distance travelled), and each piece fades with its own age.
      ctx.lineCap = 'butt';
      ctx.lineWidth = DASH_WIDTH_PX;
      for (let i = 1; i < trail.length; i += 1) {
        const a = trail[i - 1];
        const b = trail[i];
        const segLen = b.d - a.d;
        if (segLen <= 0) continue;
        const segX = b.x - a.x;
        const segY = b.y - a.y;
        for (let k = Math.floor(a.d / DASH_PERIOD_PX); k * DASH_PERIOD_PX < b.d; k += 1) {
          const start = Math.max(a.d, k * DASH_PERIOD_PX);
          const end = Math.min(b.d, k * DASH_PERIOD_PX + DASH_LENGTH_PX);
          if (end <= start) continue;
          const f0 = (start - a.d) / segLen;
          const f1 = (end - a.d) / segLen;
          const life = 1 - (now - (a.t + (b.t - a.t) * f1)) / TRAIL_LIFE_MS;
          if (life <= 0) continue;
          ctx.beginPath();
          ctx.moveTo(a.x + segX * f0, a.y + segY * f0);
          ctx.lineTo(a.x + segX * f1, a.y + segY * f1);
          ctx.strokeStyle = `rgba(0, 0, 0, ${life})`;
          ctx.stroke();
        }
      }

      if (visible) {
        ctx.save();
        ctx.translate(pos.x, pos.y);
        ctx.rotate(heading);
        ctx.scale(scale, scale);
        drawCar(ctx);
        ctx.restore();
      }

      // Stop drawing once the pointer has been still and the trail has faded
      const idle = now - lastMoveTime > TRAIL_LIFE_MS + 200;
      if (idle && trail.length === 0 && ripples.length === 0 && Math.abs(targetScale - scale) < 0.01) {
        raf = 0;
        return;
      }
      raf = requestAnimationFrame(frame);
    };

    const wake = () => {
      if (!raf) raf = requestAnimationFrame(frame);
    };

    const onMove = (e: PointerEvent) => {
      if (e.pointerType !== 'mouse' && e.pointerType !== 'pen') return;
      if (!visible) {
        visible = true;
        prev = { x: e.clientX, y: e.clientY };
      }
      pos.x = e.clientX;
      pos.y = e.clientY;
      const now = performance.now();
      lastMoveTime = now;
      const last = trail[trail.length - 1];
      if (!last || Math.hypot(pos.x - last.x, pos.y - last.y) >= TRAIL_STEP_PX) {
        if (last) travelled += Math.hypot(pos.x - last.x, pos.y - last.y);
        trail.push({ x: pos.x, y: pos.y, t: now, d: travelled });
        if (trail.length > TRAIL_MAX_POINTS) trail.shift();
      }
      const el = e.target instanceof Element ? e.target : null;
      hoverScale = el?.closest(INTERACTIVE) ? HOVER_SCALE : REST_SCALE;
      targetScale = pressed ? PRESS_SCALE : hoverScale;
      wake();
    };

    const onDown = (e: PointerEvent) => {
      if ((e.pointerType !== 'mouse' && e.pointerType !== 'pen') || e.button !== 0) return;
      pressed = true;
      targetScale = PRESS_SCALE;
      lastMoveTime = performance.now();
      ripples.push({ x: e.clientX, y: e.clientY, t: performance.now() });
      visible = true;
      pos.x = e.clientX;
      pos.y = e.clientY;
      wake();
    };

    const onUp = () => {
      if (!pressed) return;
      pressed = false;
      targetScale = hoverScale;
      lastMoveTime = performance.now();
      wake();
    };

    const onLeave = (e: MouseEvent) => {
      if (e.relatedTarget === null) {
        visible = false;
        wake();
      }
    };

    window.addEventListener('pointermove', onMove, { passive: true });
    window.addEventListener('pointerdown', onDown, { passive: true });
    window.addEventListener('pointerup', onUp, { passive: true });
    window.addEventListener('pointercancel', onUp, { passive: true });
    document.addEventListener('mouseout', onLeave);
    window.addEventListener('resize', resize);
    return () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerdown', onDown);
      window.removeEventListener('pointerup', onUp);
      window.removeEventListener('pointercancel', onUp);
      document.removeEventListener('mouseout', onLeave);
      window.removeEventListener('resize', resize);
      if (raf) cancelAnimationFrame(raf);
      document.body.classList.remove('ps-car-cursor');
    };
  }, [enabled]);

  if (!enabled) return null;
  return <canvas ref={canvasRef} className="lp-car-cursor" aria-hidden="true" />;
};
