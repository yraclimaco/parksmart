/**
 * Permit time-window tests. T1 to T4 mirror test cases from the team's
 * "UCSD Parking Domain Research v1.2", section 8 (ordinary stalls only).
 */

import { describe, expect, it } from 'vitest';
import { accessLabel, canPark, holidayNotice, lotAccess, parseArrival, relyOnUnverifiedDAccess } from './permitRules.ts';

// Oct 20, 2026 is a Tuesday; Oct 21 a Wednesday; Oct 24 a Saturday.
const at = (date: string, time: string) => parseArrival(date, time)!;

describe('canPark (research doc test cases)', () => {
  it('T1: S permit, B stall, Tuesday 5 PM -> allowed', () => {
    expect(canPark('S', 'B', at('2026-10-20', '17:00'))).toBe(true);
  });
  it('T2: S permit, B stall, Tuesday 10 AM -> not allowed', () => {
    expect(canPark('S', 'B', at('2026-10-20', '10:00'))).toBe(false);
  });
  it('T3: B permit, A stall, Saturday noon -> allowed', () => {
    expect(canPark('B', 'A', at('2026-10-24', '12:00'))).toBe(true);
  });
  it('T4: D permit, S stall, Wednesday 3 PM -> not allowed', () => {
    expect(canPark('D', 'S', at('2026-10-21', '15:00'))).toBe(false);
  });
});

describe('canPark (published cutovers)', () => {
  it('uses the 8 AM cutover for S and the 7:30 AM cutover for visitors', () => {
    expect(canPark('S', 'B', at('2026-10-21', '07:45'))).toBe(true);
    expect(canPark('V', 'B', at('2026-10-21', '07:45'))).toBe(false);
  });
  it('lets visitors use A stalls only from 5 PM, weekends included', () => {
    expect(canPark('V', 'A', at('2026-10-24', '12:00'))).toBe(false);
    expect(canPark('V', 'A', at('2026-10-24', '17:30'))).toBe(true);
  });
  it('never lets an S permit use V stalls', () => {
    expect(canPark('S', 'V', at('2026-10-24', '12:00'))).toBe(false);
  });
});

describe('lotAccess', () => {
  it('is 24/7 when the permit has an always-on category in the lot', () => {
    expect(lotAccess('S', ['A', 'S'], at('2026-10-21', '10:00'))).toEqual({ status: 'always' });
  });
  it('reports when a weekday evening upgrade ends', () => {
    const arrival = at('2026-10-21', '18:00');
    const access = lotAccess('S', ['A', 'B'], arrival);
    expect(access.status).toBe('until');
    expect(accessLabel(access, 'S', arrival)).toBe('Valid until Thu 8:00 AM');
  });
  it('reports when access starts later the same day', () => {
    const arrival = at('2026-10-21', '10:00');
    const access = lotAccess('S', ['A', 'B'], arrival);
    expect(accessLabel(access, 'S', arrival)).toBe('Your S permit works here from 4:00 PM');
  });
  it('carries a Friday evening window through the weekend to Monday 8 AM', () => {
    const arrival = at('2026-10-23', '18:00'); // Friday
    expect(accessLabel(lotAccess('S', ['B'], arrival), 'S', arrival)).toBe('Valid until Mon 8:00 AM');
  });
  it('is never valid when no rule covers any category', () => {
    expect(lotAccess('S', ['V'], at('2026-10-21', '10:00'))).toEqual({ status: 'never' });
  });
});

describe('parseArrival', () => {
  it('returns null for empty or invalid input', () => {
    expect(parseArrival('', '10:00')).toBeNull();
    expect(parseArrival('2026-10-21', '')).toBeNull();
    expect(parseArrival('not-a-date', '10:00')).toBeNull();
  });
});

describe('stall-specific wording and verification flags', () => {
  const tue = at('2026-10-20', '12:00');
  it('names the stalls that are open 24/7', () => {
    const access = lotAccess('S', ['A', 'D'], tue);
    expect(accessLabel(access, 'S', tue, ['A', 'D'])).toBe('Open 24/7 in D stalls with your S permit');
  });
  it('flags non-D permits that rely only on D stalls', () => {
    expect(relyOnUnverifiedDAccess('S', ['A', 'D'], tue)).toBe(true);
    expect(relyOnUnverifiedDAccess('S', ['A', 'S'], tue)).toBe(false);
    expect(relyOnUnverifiedDAccess('D', ['D'], tue)).toBe(false);
  });
  it('shows a notice on university holidays only', () => {
    expect(holidayNotice(at('2026-11-26', '12:00'))).toMatch(/Thanksgiving/);
    expect(holidayNotice(at('2026-10-20', '12:00'))).toBeNull();
  });
});
