import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, tokenStore } from "../api";

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

function fakeResponse(status: number, body: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: "status",
    json: async () => body,
  };
}

describe("tokenStore", () => {
  it("round-trips and clears the token", () => {
    tokenStore.set("tok123");
    expect(tokenStore.get()).toBe("tok123");
    tokenStore.clear();
    expect(tokenStore.get()).toBeNull();
  });
});

describe("api client", () => {
  it("attaches the bearer token and parses JSON", async () => {
    tokenStore.set("tok123");
    const fetchMock = vi.fn(async () =>
      fakeResponse(200, { id: "u1", email: "a@x.in", full_name: "A" })
    );
    vi.stubGlobal("fetch", fetchMock);

    const me = await api.me();
    expect(me.email).toBe("a@x.in");

    const [url, opts] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain("/auth/me");
    expect((opts.headers as Record<string, string>).Authorization).toBe("Bearer tok123");
  });

  it("omits the Authorization header when logged out", async () => {
    const fetchMock = vi.fn(async () => fakeResponse(200, []));
    vi.stubGlobal("fetch", fetchMock);
    await api.listTenants();
    const [, opts] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect((opts.headers as Record<string, string>).Authorization).toBeUndefined();
  });

  it("raises ApiError carrying the server's detail message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => fakeResponse(403, { detail: "Not a member of this tenant" }))
    );
    const err = await api.listTenants().then(
      () => null,
      (e) => e
    );
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(403);
    expect(err.message).toBe("Not a member of this tenant");
  });
});
