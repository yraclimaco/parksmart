/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';

/**
 * Shimmer skeleton loading placeholder for recommendation cards.
 */
export const SkeletonCard: React.FC = () => {
  return (
    <div className="p-3.5 rounded-2xl bg-white border border-line animate-pulse">
      {/* Header tags */}
      <div className="flex items-center justify-between mb-3">
        <div className="h-5 w-20 bg-slate-200/70 rounded-full" />
        <div className="h-4 w-12 bg-slate-200/50 rounded" />
      </div>

      {/* Lot Title & Walk time */}
      <div className="flex justify-between items-center mb-3">
        <div className="h-5 w-32 bg-slate-200/70 rounded" />
        <div className="h-4 w-16 bg-slate-200/50 rounded" />
      </div>

      {/* Availability Meter */}
      <div className="space-y-1.5 mb-3">
        <div className="flex justify-between">
          <div className="h-3 w-28 bg-slate-200/50 rounded" />
          <div className="h-3 w-8 bg-slate-200/70 rounded" />
        </div>
        <div className="h-1.5 w-full bg-slate-200/60 rounded-full" />
      </div>

      {/* Reason line */}
      <div className="h-10 w-full bg-slate-200/40 rounded-lg mb-2" />

      {/* Footnote */}
      <div className="flex justify-between pt-1">
        <div className="h-3 w-16 bg-slate-200/40 rounded" />
        <div className="h-3 w-12 bg-slate-200/40 rounded" />
      </div>
    </div>
  );
};
