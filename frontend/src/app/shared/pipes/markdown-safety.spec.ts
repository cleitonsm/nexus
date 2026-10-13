/** SPEC-006 D12 (fix-12, RF-60): a resposta do LLM nao carrega imagem nem vaza o Referer. */
import { describe, expect, it } from "vitest";

import { neutralizeRemoteContent } from "./markdown-safety";

describe("neutralizeRemoteContent", () => {
  it("replaces images with their description and makes no request", () => {
    const html = '<p>Veja <img src="https://externo.example/x.png?d=segredo" alt="grafico"> aqui</p>';
    const safe = neutralizeRemoteContent(html);
    expect(safe).not.toContain("<img");
    expect(safe).not.toContain("externo.example");
    expect(safe).toContain("[imagem: grafico]");
  });

  it("escapes the description and handles images without alt", () => {
    expect(neutralizeRemoteContent('<img alt="&lt;b&gt;x" src="a.png">')).toBe(
      "[imagem: &lt;b&gt;x]"
    );
    expect(neutralizeRemoteContent('<IMG SRC="a.png"/>')).toBe("[imagem]");
  });

  it("adds rel noopener noreferrer to links without one", () => {
    expect(neutralizeRemoteContent('<a href="https://x.example">x</a>')).toBe(
      '<a rel="noopener noreferrer" href="https://x.example">x</a>'
    );
    expect(neutralizeRemoteContent('<a rel="nofollow" href="/y">y</a>')).toBe(
      '<a rel="nofollow" href="/y">y</a>'
    );
  });

  it("keeps ordinary markup untouched", () => {
    const html = '<p><strong>Ferias</strong> de <code>30</code> dias [1].</p>';
    expect(neutralizeRemoteContent(html)).toBe(html);
  });
});
