/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Runs a request with a deadline. `run` gets one signal that fires on either the
 * caller's cancel or the timeout. A timeout resolves with `onTimeout()`; a cancel
 * through `signal` rejects with AbortError, so a newer search can still replace
 * an older one.
 */
export async function withTimeout<T>(
  run: (signal: AbortSignal) => Promise<T>,
  onTimeout: () => T,
  options: { signal?: AbortSignal; timeoutMs: number }
): Promise<T> {
  const { signal, timeoutMs } = options;
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  const forwardAbort = () => controller.abort();
  if (signal?.aborted) controller.abort();
  else signal?.addEventListener('abort', forwardAbort, { once: true });

  try {
    const result = await run(controller.signal);
    return timedOut ? onTimeout() : result;
  } catch (error) {
    if (timedOut) return onTimeout();
    throw error;
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', forwardAbort);
  }
}
