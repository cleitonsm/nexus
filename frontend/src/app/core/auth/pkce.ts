/** PKCE (RFC 7636) com o Web Crypto do navegador; sem dependencias. */

const UNRESERVED = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~";

export type RandomSource = Pick<Crypto, "getRandomValues">;
export type DigestSource = Pick<SubtleCrypto, "digest">;

export function base64Url(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/** Texto aleatorio para o `state` e para o `code_verifier` (43 a 128 caracteres). */
export function randomString(length: number, random: RandomSource): string {
  // 256 nao e multiplo de 66: os valores acima de 197 sao descartados para
  // que todos os caracteres tenham a mesma probabilidade.
  const limit = 256 - (256 % UNRESERVED.length);
  let text = "";
  while (text.length < length) {
    const bytes = random.getRandomValues(new Uint8Array(length));
    for (const byte of bytes) {
      if (byte < limit && text.length < length) {
        text += UNRESERVED[byte % UNRESERVED.length];
      }
    }
  }
  return text;
}

/** `code_challenge` do metodo S256: SHA-256 do verificador, em base64url. */
export async function codeChallenge(verifier: string, subtle: DigestSource): Promise<string> {
  const digest = await subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  return base64Url(new Uint8Array(digest));
}
