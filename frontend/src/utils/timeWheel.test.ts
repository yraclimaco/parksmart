import { describe, expect, it } from 'vitest';
import { fromWheelTime, nearestLoopIndex, toWheelTime } from './timeWheel.ts';

describe('toWheelTime', () => {
  it('converts 24-hour times to a 12-hour wheel position', () => {
    expect(toWheelTime('09:30')).toEqual({ hour12: 9, minute: 30, pm: false });
    expect(toWheelTime('13:05')).toEqual({ hour12: 1, minute: 5, pm: true });
    expect(toWheelTime('00:00')).toEqual({ hour12: 12, minute: 0, pm: false });
    expect(toWheelTime('12:00')).toEqual({ hour12: 12, minute: 0, pm: true });
    expect(toWheelTime('23:59')).toEqual({ hour12: 11, minute: 59, pm: true });
  });

  it('falls back to 12:00 AM for anything unreadable', () => {
    expect(toWheelTime('')).toEqual({ hour12: 12, minute: 0, pm: false });
    expect(toWheelTime('abc')).toEqual({ hour12: 12, minute: 0, pm: false });
    expect(toWheelTime('25:00')).toEqual({ hour12: 12, minute: 0, pm: false });
    expect(toWheelTime('10:75')).toEqual({ hour12: 12, minute: 0, pm: false });
  });
});

describe('fromWheelTime', () => {
  it('converts back to the 24-hour format the planner uses', () => {
    expect(fromWheelTime({ hour12: 9, minute: 30, pm: false })).toBe('09:30');
    expect(fromWheelTime({ hour12: 1, minute: 5, pm: true })).toBe('13:05');
    expect(fromWheelTime({ hour12: 12, minute: 0, pm: false })).toBe('00:00');
    expect(fromWheelTime({ hour12: 12, minute: 0, pm: true })).toBe('12:00');
    expect(fromWheelTime({ hour12: 11, minute: 59, pm: true })).toBe('23:59');
  });

  it('round-trips every minute of the day', () => {
    for (let h = 0; h < 24; h += 1) {
      for (let m = 0; m < 60; m += 1) {
        const t = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
        expect(fromWheelTime(toWheelTime(t))).toBe(t);
      }
    }
  });
});

describe('nearestLoopIndex', () => {
  it('rolls the short way around a looping list', () => {
    // 60 minutes; wheel is on item 58 (middle copy 60..119 => index 118), asked for 2
    expect(nearestLoopIndex(118, 2, 60)).toBe(122);
    // from 62 asked for 58 goes back
    expect(nearestLoopIndex(62, 58, 60)).toBe(58);
    expect(nearestLoopIndex(100, 40, 60)).toBe(100);
  });
});
