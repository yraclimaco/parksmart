/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

interface ErrorStateProps {
  onRetry: () => void;
  message?: string;
}

/**
 * Friendly error display when parking recommendation calculation fails, with retry action.
 */
export const ErrorState: React.FC<ErrorStateProps> = ({
  onRetry,
  message = 'Unable to calculate parking options right now.',
}) => {
  return (
    <div className="p-5 text-center bg-rose-50/70 rounded-2xl border border-rose-200/80 shadow-xs space-y-3">
      <div className="w-10 h-10 mx-auto rounded-full bg-rose-100 flex items-center justify-center text-rose-500">
        <AlertCircle className="w-5 h-5" />
      </div>
      <div>
        <h4 className="text-sm font-bold text-rose-900">
          Something went wrong
        </h4>
        <p className="text-xs text-rose-700/80 mt-1 max-w-xs mx-auto leading-relaxed">
          {message}
        </p>
      </div>
      <button
        type="button"
        onClick={onRetry}
        className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-white border border-rose-200 text-xs font-semibold text-rose-700 hover:bg-rose-50 hover:text-rose-800 focus:outline-none focus:ring-2 focus:ring-rose-400 shadow-xs transition-colors cursor-pointer"
      >
        <RefreshCw className="w-3.5 h-3.5" />
        <span>Try again</span>
      </button>
    </div>
  );
};
