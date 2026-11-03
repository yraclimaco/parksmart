/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { ChevronDown, History, RotateCcw } from 'lucide-react';
import { ParkingPlannerRequest } from '../types.ts';
import { getDestination } from '../data/destinations.ts';
import { parseArrival } from '../utils/permitRules.ts';

interface RecentSearchesProps {
  /** Earlier searches this visit, most recent first. */
  history: ParkingPlannerRequest[];
  onRestore: (request: ParkingPlannerRequest) => void;
}

/** "Thu 9:30 AM" for a request's arrival. */
function whenLabel(request: ParkingPlannerRequest): string {
  const arrival = parseArrival(request.arrivalDate, request.arrivalTime);
  if (!arrival) return '';
  return `${arrival.toLocaleDateString('en-US', { weekday: 'short' })} ${arrival.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
  })}`;
}

/**
 * "Recent" button in the results header. Opens a short list of this visit's earlier
 * searches; picking one runs it again (and the current search moves into the list,
 * so searching X then Y and picking X from Recent goes back to X).
 */
export const RecentSearches: React.FC<RecentSearchesProps> = ({ history, onRestore }) => {
  const [isOpen, setIsOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  // Close on outside click or Esc
  useEffect(() => {
    if (!isOpen) return;
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setIsOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [isOpen]);

  if (history.length === 0) return null;

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        aria-haspopup="menu"
        aria-expanded={isOpen}
        className="flex items-center gap-1 px-2 py-1 -my-1 rounded-lg text-[11px] font-semibold text-ink hover:bg-paper transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-sky/40 cursor-pointer"
      >
        <History className="w-3.5 h-3.5" aria-hidden="true" />
        Recent
        <span className="min-w-4 h-4 px-1 rounded-full bg-black/[0.08] text-[10px] flex items-center justify-center tabular-nums">
          {history.length}
        </span>
        <ChevronDown className={`w-3 h-3 transition-transform ${isOpen ? 'rotate-180' : ''}`} aria-hidden="true" />
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.ul
            role="menu"
            aria-label="Recent searches"
            initial={{ opacity: 0, y: -4, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.98 }}
            transition={{ duration: 0.12, ease: 'easeOut' }}
            className="absolute right-0 top-full mt-1.5 w-64 p-1.5 rounded-xl bg-white border border-line shadow-[0_12px_32px_rgba(24,43,73,0.18)] z-40 origin-top-right"
          >
            <li role="presentation" className="px-2.5 pt-1 pb-1.5 text-[12px] font-semibold text-muted">
              Earlier searches
            </li>
            {history.map((request, i) => (
              <li key={`${request.destinationId}|${request.arrivalDate}|${request.arrivalTime}|${request.permitType}`} role="none">
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setIsOpen(false);
                    onRestore(request);
                  }}
                  className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-left hover:bg-paper focus:outline-none focus-visible:bg-paper cursor-pointer group"
                >
                  <RotateCcw
                    className={`w-3.5 h-3.5 shrink-0 ${i === 0 ? 'text-ink' : 'text-muted'} group-hover:text-navy`}
                    aria-hidden="true"
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block text-xs font-semibold text-navy truncate">
                      {getDestination(request.destinationId).name}
                    </span>
                    <span className="block text-[11px] text-muted">
                      {whenLabel(request)} · {request.permitType} permit
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  );
};
