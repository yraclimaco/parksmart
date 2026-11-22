import { describe, expect, it } from 'vitest';
import { alertArrivalTime, getArrivalError, maxArrivalDate, reuseAlertArrival } from './arrival.ts';

const now = new Date('2026-10-21T14:00:00');

describe('getArrivalError', () => {
  it('flags a missing date or time', () => {
    expect(getArrivalError({ arrivalDate: '', arrivalTime: '14:00' }, now)).toMatch(/date/);
    expect(getArrivalError({ arrivalDate: '2026-10-21', arrivalTime: '' }, now)).toMatch(/time/);
  });
  it('flags a past date', () => {
    expect(getArrivalError({ arrivalDate: '2026-10-20', arrivalTime: '14:00' }, now)).toMatch(/passed/);
  });
  it('allows a few minutes of slack and any future time', () => {
    expect(getArrivalError({ arrivalDate: '2026-10-21', arrivalTime: '13:50' }, now)).toBeNull();
    expect(getArrivalError({ arrivalDate: '2026-10-22', arrivalTime: '09:00' }, now)).toBeNull();
  });
});

describe('getArrivalError, far future', () => {
  it('rejects dates more than a year ahead', () => {
    expect(getArrivalError({ arrivalDate: '2099-01-01', arrivalTime: '09:00' }, now)).toMatch(/next year/);
  });
  it('maxArrivalDate is one year after today', () => {
    expect(maxArrivalDate(now)).toBe('2027-10-21');
  });
});

describe('alertArrivalTime', () => {
  it('moves "now" just ahead of now, so the weather source does not see a past arrival', () => {
    expect(alertArrivalTime('2026-10-21', '14:00', now)).toBe('2026-10-21T14:02:00');
    expect(alertArrivalTime('2026-10-21', '13:50', now)).toBe('2026-10-21T14:02:00');
  });

  it('keeps any arrival that is comfortably in the future', () => {
    expect(alertArrivalTime('2026-10-21', '14:05', now)).toBe('2026-10-21T14:05:00');
    expect(alertArrivalTime('2026-10-22', '09:00', now)).toBe('2026-10-22T09:00:00');
  });

  it('carries over into the next hour or day', () => {
    const late = new Date('2026-10-21T23:59:00');
    expect(alertArrivalTime('2026-10-21', '23:59', late)).toBe('2026-10-22T00:01:00');
  });

  it('passes unreadable input through untouched', () => {
    expect(alertArrivalTime('', '09:00', now)).toBe('T09:00:00');
  });
});

describe('reuseAlertArrival', () => {
  const t0 = new Date('2026-11-23T10:00:00');

  it('works out the arrival the first time', () => {
    expect(reuseAlertArrival(null, '2026-11-23', '10:00', t0)).toBe('2026-11-23T10:02:00');
  });

  it('keeps the same arrival while it is still ahead, so nothing refetches on its own', () => {
    expect(reuseAlertArrival('2026-11-23T10:02:00', '2026-11-23', '10:00', new Date('2026-11-23T10:00:30'))).toBe(
      '2026-11-23T10:02:00'
    );
  });

  it('works it out again once it has gone past, so a later card tap never sends a past arrival', () => {
    const later = new Date('2026-11-23T10:10:00');
    expect(reuseAlertArrival('2026-11-23T10:02:00', '2026-11-23', '10:00', later)).toBe('2026-11-23T10:12:00');
  });

  it('never moves a later arrival', () => {
    expect(reuseAlertArrival(null, '2026-11-24', '09:00', t0)).toBe('2026-11-24T09:00:00');
    expect(reuseAlertArrival('2026-11-24T09:00:00', '2026-11-24', '09:00', t0)).toBe('2026-11-24T09:00:00');
  });
});
