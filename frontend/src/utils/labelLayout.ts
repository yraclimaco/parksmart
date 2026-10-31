/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Screen-space decluttering for map pins. Pure math (no DOM), so it can be tested.
 * Pins are laid out in priority order: the selected pin and ranked picks always keep
 * their discs and labels, then parking structures, then surface lots. A lower-priority
 * item that would sit on top of something already placed gets dropped (surface lots)
 * or loses its name (everything else) until the user zooms in far enough to fit it.
 */

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface PinItem {
  id: string;
  /** Pin center in screen pixels. */
  cx: number;
  cy: number;
  /** Disc radius in pixels. */
  radius: number;
  /** Size of the name label, and where it starts below the pin center. */
  labelW: number;
  labelH: number;
  labelOffset: number;
  /** Size of the "First choice" style tag alone (ranked pins only). */
  tagW: number;
  tagH: number;
  priority: number;
  /** Selected or ranked: never hidden, and always shows at least its tag. */
  pinned: boolean;
  /** Surface lots may be hidden when crowded; structures never are. */
  droppable: boolean;
  /** The selected pin: its name is always drawn below it, wherever that lands. */
  forceName?: boolean;
}

export type LabelMode = 'full' | 'tag' | 'none';

export interface LayoutResult {
  hidden: Set<string>;
  labels: Map<string, LabelMode>;
  /** Pinned pins whose label had to move above the disc to stay clear of something. */
  above: Set<string>;
}

/** True when two rectangles overlap, with `pad` extra pixels of breathing room. */
export function overlaps(a: Rect, b: Rect, pad = 0): boolean {
  return a.x < b.x + b.w + pad && b.x < a.x + a.w + pad && a.y < b.y + b.h + pad && b.y < a.y + a.h + pad;
}

const DISC_PAD = 2;
const LABEL_PAD = 3;

function discRect(p: PinItem): Rect {
  return { x: p.cx - p.radius, y: p.cy - p.radius, w: p.radius * 2, h: p.radius * 2 };
}

function labelRect(p: PinItem, w: number, h: number, above = false): Rect {
  return { x: p.cx - w / 2, y: above ? p.cy - p.radius - 3 - h : p.cy + p.labelOffset, w, h };
}

/** Decides which pins stay visible and which labels fit, for the current zoom. */
export function layoutPins(items: PinItem[], obstacles: Rect[] = []): LayoutResult {
  const ordered = [...items].sort((a, b) => b.priority - a.priority || a.id.localeCompare(b.id));
  const hidden = new Set<string>();
  const labels = new Map<string, LabelMode>();
  const above = new Set<string>();

  // Pinned pins always draw their label below, so reserve that space before dropping lots
  const reserved: Rect[] = [...obstacles];
  for (const pin of ordered) if (pin.pinned) reserved.push(labelRect(pin, pin.labelW, pin.labelH));

  // Pass 1: discs. Crowded surface lots drop out; everything else stays.
  const placedDiscs: Array<{ id: string; rect: Rect }> = [];
  for (const pin of ordered) {
    const rect = discRect(pin);
    if (
      pin.droppable &&
      !pin.pinned &&
      (placedDiscs.some((d) => overlaps(rect, d.rect, DISC_PAD)) || reserved.some((r) => overlaps(rect, r, 1)))
    ) {
      hidden.add(pin.id);
      labels.set(pin.id, 'none');
      continue;
    }
    placedDiscs.push({ id: pin.id, rect });
  }

  // Pass 2: labels, best first, against every visible disc, earlier labels and obstacles.
  const placedLabels: Rect[] = [];
  const blocked = (rect: Rect, ownId: string) =>
    placedLabels.some((l) => overlaps(rect, l, LABEL_PAD)) ||
    placedDiscs.some((d) => d.id !== ownId && overlaps(rect, d.rect, LABEL_PAD)) ||
    obstacles.some((o) => overlaps(rect, o, LABEL_PAD));

  for (const pin of ordered) {
    if (hidden.has(pin.id)) continue;
    const full = labelRect(pin, pin.labelW, pin.labelH);
    if (!blocked(full, pin.id)) {
      labels.set(pin.id, 'full');
      placedLabels.push(full);
      continue;
    }
    if (pin.pinned && (pin.tagW === 0 || pin.forceName)) {
      // The selected pin always names itself
      labels.set(pin.id, 'full');
      placedLabels.push(full);
      continue;
    }
    if (pin.pinned) {
      // Ranked picks always show something: the name, else above the disc, else just the tag
      const tryOrder: Array<{ mode: LabelMode; up: boolean; rect: Rect }> = [
        { mode: 'full', up: true, rect: labelRect(pin, pin.labelW, pin.labelH, true) },
        { mode: 'tag', up: false, rect: labelRect(pin, pin.tagW, pin.tagH) },
        { mode: 'tag', up: true, rect: labelRect(pin, pin.tagW, pin.tagH, true) },
      ];
      const pick = tryOrder.find((t) => !blocked(t.rect, pin.id)) ?? tryOrder[1];
      labels.set(pin.id, pick.mode);
      if (pick.up) above.add(pin.id);
      placedLabels.push(pick.rect);
      continue;
    }
    labels.set(pin.id, 'none');
  }

  return { hidden, labels, above };
}
