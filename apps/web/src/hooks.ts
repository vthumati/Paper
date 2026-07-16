import { useCallback, useEffect, useState } from "react";
import { toast } from "./components/Toast";

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
  const guard =
    (fn: () => Promise<unknown>, success?: string) => async () => {
      setError("");
      try {
        await fn();
        await onDone?.();
        if (success) toast(success);
      } catch (e) {
        setError((e as Error).message);
      }
    };
  return { error, setError, guard };
}

/**
 * Fetch-on-mount resource loader: owns data/error/loading state and runs the
 * fetcher whenever `deps` change. Returns `reload` to refetch (e.g. after a
 * mutation) and `setData` for optimistic updates.
 *
 *   const { data, error, loading, reload } = useResource(() => api.listX(id), [id]);
 */
export function useResource<T>(fetcher: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const reload = useCallback(() => {
    setLoading(true);
    return fetcher()
      .then((d) => {
        setData(d);
        setError("");
        return d;
      })
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => {
    reload();
  }, [reload]);
  return { data, error, loading, reload, setData, setError };
}
