/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { SearchX } from 'lucide-react';
import { PermitType } from '../types.ts';

interface EmptyStateProps {
  onResetFilters?: () => void;
  /** Permit that was searched; names it in the message. Omit for a generic message. */
  permitType?: PermitType;
}

/**
 * Friendly notification when no parking lots match selected criteria.
 */
export const EmptyState: React.FC<EmptyStateProps> = ({ onResetFilters, permitType }) => {
  return (
    <div className="p-5 text-center bg-white rounded-2xl border border-line space-y-3">
      <div className="w-10 h-10 mx-auto rounded-full bg-paper flex items-center justify-center text-muted">
        <SearchX className="w-5 h-5" />
      </div>
      <div>
        <h4 className="text-sm font-bold text-navy">
          {permitType ? `No structure takes your ${permitType} permit at that time` : 'No structure takes your permit at that time'}
        </h4>
        <p className="text-xs text-muted mt-1 max-w-xs mx-auto leading-relaxed">
          Your permit may only work in some structures in the evening or on weekends, or the open ones are too far to walk (over 20 min). Try a later arrival time, a different destination or a different permit.
        </p>
      </div>
      {onResetFilters && permitType !== 'S' && (
        <button
          type="button"
          onClick={onResetFilters}
          className="text-xs font-semibold text-navy hover:text-ink underline underline-offset-4 focus:outline-none cursor-pointer"
        >
          Reset to default permit (S)
        </button>
      )}
    </div>
  );
};
