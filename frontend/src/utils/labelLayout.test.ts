import { describe, expect, it } from 'vitest';
import { layoutPins, overlaps, PinItem } from './labelLayout.ts';

const pin = (id: string, cx: number, cy: number, extra: Partial<PinItem> = {}): PinItem => ({
  id, cx, cy, radius: 10, labelW: 60, labelH: 14, labelOffset: 14, tagW: 0, tagH: 0,
  priority: 10, pinned: false, droppable: false, ...extra,
});

describe('overlaps', () => {
  it('detects overlap and honors padding', () => {
    expect(overlaps({ x: 0, y: 0, w: 10, h: 10 }, { x: 5, y: 5, w: 10, h: 10 })).toBe(true);
    expect(overlaps({ x: 0, y: 0, w: 10, h: 10 }, { x: 11, y: 0, w: 10, h: 10 })).toBe(false);
    expect(overlaps({ x: 0, y: 0, w: 10, h: 10 }, { x: 11, y: 0, w: 10, h: 10 }, 2)).toBe(true);
  });
});

describe('layoutPins', () => {
  it('shows every label when pins are far apart', () => {
    const { labels, hidden } = layoutPins([pin('a', 0, 0), pin('b', 300, 0), pin('c', 0, 300)]);
    expect(hidden.size).toBe(0);
    expect([...labels.values()]).toEqual(['full', 'full', 'full']);
  });

  it('drops the lower-priority label when two collide', () => {
    const { labels } = layoutPins([pin('a', 0, 0, { priority: 20 }), pin('b', 50, 0, { priority: 10 })]);
    expect(labels.get('a')).toBe('full');
    expect(labels.get('b')).toBe('none');
  });

  it('hides a crowded surface lot but never a structure', () => {
    const { hidden } = layoutPins([
      pin('struct', 0, 0, { priority: 10 }),
      pin('lot', 5, 5, { priority: 0, droppable: true }),
      pin('struct2', 6, 6, { priority: 10 }),
    ]);
    expect(hidden.has('lot')).toBe(true);
    expect(hidden.has('struct')).toBe(false);
    expect(hidden.has('struct2')).toBe(false);
  });

  it('keeps a ranked pin visible and still labeled when space is tight', () => {
    const { labels, hidden } = layoutPins([
      pin('first', 0, 0, { priority: 5, pinned: true, droppable: true, tagW: 40, tagH: 14 }),
      pin('big', 10, 6, { priority: 90, pinned: true, tagW: 40, tagH: 14 }),
    ]);
    expect(hidden.has('first')).toBe(false);
    expect(labels.get('big')).toBe('full');
    expect(labels.get('first')).not.toBe('none');
  });

  it('moves a ranked label above its disc when the space below is taken', () => {
    const { labels, above } = layoutPins(
      [pin('first', 0, 0, { priority: 90, pinned: true, tagW: 40, tagH: 14 })],
      [{ x: -50, y: 10, w: 100, h: 30 }]
    );
    expect(labels.get('first')).toBe('full');
    expect(above.has('first')).toBe(true);
  });

  it('keeps labels off obstacles such as the destination pill', () => {
    const { labels } = layoutPins([pin('a', 0, 0)], [{ x: -20, y: 10, w: 100, h: 30 }]);
    expect(labels.get('a')).toBe('none');
  });
});
