/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';

/** Top-down car for the landing page lot scenes (SVG, centered on cx, cy). */
export const LotCar: React.FC<{ cx: number; cy: number; color: string; scale?: number }> = ({
  cx,
  cy,
  color,
  scale = 1,
}) => (
  <g transform={`translate(${cx} ${cy}) scale(${scale})`}>
    <rect x={-20} y={-26} width={40} height={52} rx={10} fill={color} />
    <rect x={-14} y={-14} width={28} height={11} rx={4} fill="#101D33" opacity={0.62} />
    <rect x={-13} y={8} width={26} height={9} rx={3} fill="#101D33" opacity={0.5} />
  </g>
);

export const CAR_COLORS = ['#F7F8FA', '#7C93B5', '#4A6690', '#C9D3E3', '#3A5679', '#FFCD00'] as const;

/** Becomes true once the element has scrolled into view (and stays true). */
export const useInView = <T extends Element>(): [React.RefObject<T | null>, boolean] => {
  const ref = React.useRef<T | null>(null);
  const [seen, setSeen] = React.useState(false);
  React.useEffect(() => {
    const el = ref.current;
    if (!el || seen) return;
    if (typeof IntersectionObserver === 'undefined') {
      setSeen(true);
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setSeen(true);
          io.disconnect();
        }
      },
      { threshold: 0.35 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [seen]);
  return [ref, seen];
};

export const prefersReducedMotion = (): boolean => {
  try {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  } catch {
    return false;
  }
};
