import { describe, expect, it } from 'vitest';
import { campusNow } from './campusClock.ts';

describe('campusNow', () => {
  it('reads campus time whatever the computer clock zone is', () => {
    // 8 PM UTC on Nov 23 is noon in California (PST)
    const n = campusNow(new Date('2026-11-23T20:00:00Z'));
    expect([n.getFullYear(), n.getMonth() + 1, n.getDate(), n.getHours(), n.getMinutes()]).toEqual([2026, 11, 23, 12, 0]);
  });

  it('uses daylight time in summer', () => {
    const n = campusNow(new Date('2026-07-01T19:30:00Z'));
    expect([n.getHours(), n.getMinutes()]).toEqual([12, 30]);
  });

  it('crosses midnight with the campus date, not the UTC date', () => {
    const n = campusNow(new Date('2026-11-24T06:30:00Z')); // 10:30 PM on Nov 23 in California
    expect([n.getDate(), n.getHours(), n.getMinutes()]).toEqual([23, 22, 30]);
  });
});
