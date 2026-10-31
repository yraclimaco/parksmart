/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import { Sliders, Check } from 'lucide-react';
import { DevSimulationState } from '../types.ts';

interface DevStateControlProps {
  currentState: DevSimulationState;
  onStateChange: (state: DevSimulationState) => void;
}

/**
 * Developer helper widget tucked in the corner to effortlessly simulate and verify
 * all 4 required UI states: normal, loading, empty, and error.
 */
export const DevStateControl: React.FC<DevStateControlProps> = ({
  currentState,
  onStateChange,
}) => {
  const [isOpen, setIsOpen] = useState(false);

  const states: Array<{ id: DevSimulationState; label: string; desc: string }> = [
    { id: 'normal', label: 'Normal', desc: 'Standard ranked sample recommendations' },
    { id: 'loading', label: 'Loading', desc: 'Shimmer skeleton placeholders' },
    { id: 'empty', label: 'Empty', desc: 'No parking found message' },
    { id: 'error', label: 'Error', desc: 'Error message with retry action' },
  ];

  return (
    <div className="fixed bottom-10 right-4 z-30 font-sans text-xs">
      {isOpen ? (
        <div className="p-3 bg-white rounded-2xl border border-line shadow-[0_12px_32px_rgba(24,43,73,0.16)] w-60 animate-in fade-in slide-in-from-bottom-2 duration-150">
          <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-100">
            <div className="flex items-center gap-1.5 font-semibold text-navy">
              <Sliders className="w-3.5 h-3.5 text-navy" />
              <span>Dev: simulate state</span>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="text-muted hover:text-muted px-1 py-0.5 rounded text-[11px]"
            >
              Close
            </button>
          </div>

          <div className="space-y-1">
            {states.map((s) => {
              const isSelected = currentState === s.id;
              return (
                <button
                  key={s.id}
                  onClick={() => {
                    onStateChange(s.id);
                  }}
                  className={`w-full text-left px-2.5 py-1.5 rounded-lg flex items-center justify-between transition-colors ${
                    isSelected
                      ? 'bg-paper text-navy font-semibold border border-line'
                      : 'hover:bg-paper text-ink'
                  }`}
                >
                  <div>
                    <div className="capitalize">{s.label}</div>
                    <div className="text-[10px] text-muted font-normal">{s.desc}</div>
                  </div>
                  {isSelected && <Check className="w-3.5 h-3.5 text-navy shrink-0 ml-1" />}
                </button>
              );
            })}
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setIsOpen(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white border border-line text-ink hover:text-navy shadow-sm hover:shadow transition-all font-medium text-xs cursor-pointer group"
        >
          <Sliders className="w-3.5 h-3.5 text-muted group-hover:text-navy transition-colors" />
          <span>Dev: simulate state ({currentState})</span>
        </button>
      )}
    </div>
  );
};
