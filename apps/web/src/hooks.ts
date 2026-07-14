import { useState } from "react";

/**
 * Standard wrapper for async UI actions: owns the error banner state, clears
 * it before running, captures failures, and runs an optional follow-up
 * (usually the component's reload) after success.
 *
 *   const { error, setError, guard } = useGuard(() => load());
 *   <button onClick={guard(() => api.doThing(...))}>Do thing</button>
 */
export function useGuard(onDone?: () => Promise<unknown> | unknown) {
  const [error, setError] = useState("");
  const guard = (fn: () => Promise<unknown>) => async () => {
    setError("");
    try {
      await fn();
      await onDone?.();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return { error, setError, guard };
}
