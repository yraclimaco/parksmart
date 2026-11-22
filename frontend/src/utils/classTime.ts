/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * How long before class starts the planner aims to be parked: about a 10-minute walk plus
 * a 10-minute margin. Our own choice, not UCSD data; the walk to each building varies.
 * Kept apart from the building list so the landing page can show it without loading the campus data.
 */
export const ARRIVE_BEFORE_CLASS_MINUTES = 20;

/** 570 becomes "9:30 AM". */
export function formatClock(minutes: number): string {
  const h = Math.floor(minutes / 60) % 24;
  const m = minutes % 60;
  const h12 = h % 12 === 0 ? 12 : h % 12;
  return `${h12}:${String(m).padStart(2, '0')} ${h >= 12 ? 'PM' : 'AM'}`;
}
