import { describe, expect, it } from "vitest";

import { bearer, endsSessionOnUnauthorized, isApiRequest } from "./http-auth";

describe("http-auth", () => {
  it("attaches the token only to calls to the Nexus API", () => {
    expect(isApiRequest("/api/assistants")).toBe(true);
    expect(isApiRequest("/config.json")).toBe(false);
    expect(isApiRequest("http://localhost:8080/realms/nexus/protocol/openid-connect/token")).toBe(
      false
    );
    expect(isApiRequest("https://evil.example/api/assistants")).toBe(false);
  });

  it("ends the session on a 401, except when reading the session itself", () => {
    expect(endsSessionOnUnauthorized("/api/assistants")).toBe(true);
    expect(endsSessionOnUnauthorized("/api/me")).toBe(false);
    expect(endsSessionOnUnauthorized("/config.json")).toBe(false);
  });

  it("formats the authorization header", () => {
    expect(bearer("abc")).toBe("Bearer abc");
  });
});
