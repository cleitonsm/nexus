import { describe, expect, it } from "vitest";

import { base64Url, codeChallenge, randomString } from "./pkce";

describe("pkce", () => {
  it("encodes bytes as base64url without padding", () => {
    expect(base64Url(new Uint8Array([251, 255, 254]))).toBe("-__-");
    expect(base64Url(new Uint8Array([1]))).toBe("AQ");
  });

  it("derives the S256 challenge of the RFC 7636 example", async () => {
    const challenge = await codeChallenge(
      "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk",
      crypto.subtle
    );
    expect(challenge).toBe("E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM");
  });

  it("generates verifiers with the requested length and allowed characters", () => {
    const verifier = randomString(64, crypto);
    expect(verifier).toHaveLength(64);
    expect(verifier).toMatch(/^[A-Za-z0-9\-._~]+$/);
    expect(randomString(64, crypto)).not.toBe(verifier);
  });

  it("discards bytes that would bias the distribution", () => {
    const biased = {
      getRandomValues<T extends ArrayBufferView | null>(array: T): T {
        (array as unknown as Uint8Array).fill(255);
        (array as unknown as Uint8Array)[0] = 0;
        return array;
      }
    };
    expect(randomString(3, biased)).toBe("AAA");
  });
});
