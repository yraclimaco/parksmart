/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

interface ErrorStateProps {
  onRetry: () => void;
  message?: string;
  /** Button text; defaults to "Try again". */
  actionLabel?: string;
}

/**
 * Friendly error display when parking recommendation calculation fails, with retry action.
 */
export const ErrorState: React.FC<ErrorStateProps> = ({
  onRetry,
  message = 'Your search is fine. The service did not answer, so no lots are shown. Try again in a moment.',
  actionLabel = 'Try again',
}) => {
  return (
    <div role="alert" className="p-5 text-center bg-paper rounded-2xl border border-line border-b-[3px] border-b-gold space-y-3">
      <div className="w-10 h-10 mx-auto rounded-full bg-navy flex items-center justify-center text-sun">
        <AlertCircle className="w-5 h-5" aria-hidden="true" />
      </div>
      <div>
        <h4 className="font-serif text-lg font-semibold text-navy leading-tight">
          Couldn&apos;t get parking options
        </h4>
        <p className="text-[13px] text-muted mt-1 max-w-xs mx-auto leading-relaxed">
          {message}
        </p>
      </div>
      <button
        type="button"
        onClick={onRetry}
        className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-navy text-[13px] font-semibold text-white hover:bg-navy-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky focus-visible:ring-offset-2 min-h-[44px] transition-colors cursor-pointer"
      >
        <RefreshCw className="w-3.5 h-3.5" />
        <span>{actionLabel}</span>
      </button>
    </div>
  );
};
