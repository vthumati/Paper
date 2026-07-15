import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { api, tokenStore, type User } from "./api";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, fullName: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!tokenStore.get()) {
      setLoading(false);
      return;
    }
    api
      .me()
      .then(setUser)
      .catch(() => tokenStore.clear())
      .finally(() => setLoading(false));
  }, []);

  // Keep an active session alive: the access token lives 12h, so exchange the
  // still-valid token for a fresh one well before then — on load, on an
  // interval (half the lifetime), and when the tab regains focus. Failures are
  // transient and ignored; the token stays valid until it genuinely expires.
  useEffect(() => {
    if (!user) return;
    let last = 0;
    const refresh = async () => {
      if (!tokenStore.get()) return;
      try {
        const { access_token } = await api.refresh();
        tokenStore.set(access_token);
        last = Date.now();
      } catch {
        /* transient — token remains valid until it truly expires */
      }
    };
    refresh();
    const id = window.setInterval(refresh, 6 * 60 * 60 * 1000); // 6h
    const onFocus = () => {
      if (Date.now() - last > 30 * 60 * 1000) refresh(); // throttle to 30m
    };
    window.addEventListener("focus", onFocus);
    return () => {
      window.clearInterval(id);
      window.removeEventListener("focus", onFocus);
    };
  }, [user]);

  const login = useCallback(async (email: string, password: string) => {
    const { access_token } = await api.login({ email, password });
    tokenStore.set(access_token);
    setUser(await api.me());
  }, []);

  const signup = useCallback(
    async (email: string, fullName: string, password: string) => {
      await api.signup({ email, full_name: fullName, password });
      const { access_token } = await api.login({ email, password });
      tokenStore.set(access_token);
      setUser(await api.me());
    },
    []
  );

  const logout = useCallback(() => {
    tokenStore.clear();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
