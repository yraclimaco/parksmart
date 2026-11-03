/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import { ParkingLot } from '../types.ts';
import { AERIAL_CREDIT, AERIAL_HEIGHT, lotAerialUrl } from '../utils/lotAerial.ts';

/**
 * Aerial photo header for the lot card: shimmer while loading, fades in, and quietly
 * disappears if the imagery server can't be reached (the card works without it).
 * A pulsing "P" marks the pin so people can see which building or lot it is.
 */
export const LotAerial: React.FC<{ lot: ParkingLot }> = ({ lot }) => {
  const [state, setState] = useState<'loading' | 'loaded' | 'error'>('loading');
  // The imagery server occasionally drops a request; retry once before giving up
  const [attempt, setAttempt] = useState(0);
  if (state === 'error') return null;
  const src = lotAerialUrl(lot) + (attempt > 0 ? `&retry=${attempt}` : '');

  return (
    <div
      className="ps-aerial relative -mx-4 -mt-4 mb-3 overflow-hidden rounded-t-[23px] bg-slate-300/60"
      style={{ height: AERIAL_HEIGHT }}
    >
      {state === 'loading' && <div className="absolute inset-0 ps-aerial-shimmer" aria-hidden="true" />}
      <img
        src={src}
        alt={`Aerial view of ${lot.name}`}
        decoding="async"
        draggable={false}
        onLoad={() => setState('loaded')}
        onError={() => (attempt < 1 ? setAttempt((a) => a + 1) : setState('error'))}
        className={`absolute inset-0 w-full h-full object-cover transition-[opacity,transform] duration-500 ease-out ${
          state === 'loaded' ? 'opacity-100 scale-100' : 'opacity-0 scale-[1.04]'
        }`}
      />
      {state === 'loaded' && (
        <>
          {/* Soft fade into the glass card below */}
          <div className="absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-white/45 to-transparent pointer-events-none" />
          <span className="ps-aerial-pin absolute left-1/2 top-1/2" aria-hidden="true">
            P
          </span>
          <span className="absolute bottom-1.5 right-2 px-1.5 py-0.5 rounded-md bg-black/35 text-[9px] font-medium text-white/90 backdrop-blur-sm">
            {AERIAL_CREDIT}
          </span>
        </>
      )}
    </div>
  );
};
