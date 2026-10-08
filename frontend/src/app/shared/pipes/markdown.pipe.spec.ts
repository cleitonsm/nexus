/** Lacuna de seguranca: a resposta do LLM so chega ao [innerHTML] depois de sanitizada. */
import { SecurityContext } from "@angular/core";
import { DomSanitizer } from "@angular/platform-browser";
import { describe, expect, it } from "vitest";

import { MarkdownPipe } from "./markdown.pipe";

interface SanitizeCall {
  context: SecurityContext;
  value: string;
}

function fakeSanitizer(result: string | null = "<p>limpo</p>") {
  const calls: SanitizeCall[] = [];
  let bypassUsed = false;
  const sanitizer = {
    sanitize: (context: SecurityContext, value: string) => {
      calls.push({ context, value });
      return result;
    },
    bypassSecurityTrustHtml: () => {
      bypassUsed = true;
      return "";
    }
  } as unknown as DomSanitizer;
  return { sanitizer, calls, wasBypassed: () => bypassUsed };
}

describe("MarkdownPipe", () => {
  it("sanitiza o HTML gerado no contexto HTML e devolve o resultado do sanitizador", () => {
    const fake = fakeSanitizer("<p>seguro</p>");
    const pipe = new MarkdownPipe(fake.sanitizer);

    const output = pipe.transform('Texto <img src="x" onerror="alert(1)">');

    expect(output).toBe("<p>seguro</p>");
    expect(fake.calls).toHaveLength(1);
    expect(fake.calls[0].context).toBe(SecurityContext.HTML);
    expect(fake.calls[0].value).toContain("onerror");
    expect(fake.wasBypassed()).toBe(false);
  });

  it("aplica o realce de codigo antes de sanitizar", () => {
    const fake = fakeSanitizer();
    const pipe = new MarkdownPipe(fake.sanitizer);

    pipe.transform("```python\nprint(1)\n```");

    expect(fake.calls[0].value).toContain('class="hljs language-python"');
  });

  it("devolve texto vazio sem conteudo ou quando o sanitizador devolve null", () => {
    const vazio = fakeSanitizer();
    expect(new MarkdownPipe(vazio.sanitizer).transform(null)).toBe("");
    expect(new MarkdownPipe(vazio.sanitizer).transform("")).toBe("");
    expect(vazio.calls).toHaveLength(0);

    const nulo = fakeSanitizer(null);
    expect(new MarkdownPipe(nulo.sanitizer).transform("**oi**")).toBe("");
  });
});
