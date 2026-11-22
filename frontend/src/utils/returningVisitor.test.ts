import { describe, expect, it } from 'vitest';
import { markPlannerVisited, shouldOpenPlannerDirectly } from './returningVisitor.ts';

function fakeStore(initial?: string) {
  let value = initial ?? null;
  return {
    getItem: () => value,
    setItem: (_key: string, next: string) => {
      value = next;
    },
  };
}

describe('returning visitor', () => {
  it('shows the landing page to a first-time visitor', () => {
    expect(shouldOpenPlannerDirectly('', fakeStore())).toBe(false);
  });

  it('opens the planner directly after it has been opened once', () => {
    const store = fakeStore();
    markPlannerVisited(store);
    expect(shouldOpenPlannerDirectly('', store)).toBe(true);
  });

  it('?home always shows the landing page', () => {
    const store = fakeStore();
    markPlannerVisited(store);
    expect(shouldOpenPlannerDirectly('?home', store)).toBe(false);
    expect(shouldOpenPlannerDirectly('?utm=x&home=1', store)).toBe(false);
  });

  it('falls back to the landing page when storage throws or is missing', () => {
    const broken = {
      getItem: () => {
        throw new Error('blocked');
      },
      setItem: () => {
        throw new Error('blocked');
      },
    };
    expect(shouldOpenPlannerDirectly('', broken)).toBe(false);
    expect(() => markPlannerVisited(broken)).not.toThrow();
    expect(shouldOpenPlannerDirectly('', null)).toBe(false);
  });
});
