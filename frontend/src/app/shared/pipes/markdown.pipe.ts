import { Pipe, PipeTransform, SecurityContext } from "@angular/core";
import { DomSanitizer } from "@angular/platform-browser";
import hljs from "highlight.js";
import { marked } from "marked";

marked.setOptions({
  gfm: true,
  breaks: true
});

@Pipe({
  name: "markdown",
  standalone: true
})
export class MarkdownPipe implements PipeTransform {
  constructor(private readonly sanitizer: DomSanitizer) {}

  transform(value: string | null | undefined): string {
    if (!value) {
      return "";
    }
    const html = marked.parse(value, { async: false }) as string;
    const highlighted = html.replace(
      /<pre><code class="language-([^"]*)">([\s\S]*?)<\/code><\/pre>/g,
      (_match, language, code) => {
        const decodedCode = this.decodeHtml(code);
        if (language && hljs.getLanguage(language)) {
          const rendered = hljs.highlight(decodedCode, { language }).value;
          return `<pre><code class="hljs language-${language}">${rendered}</code></pre>`;
        }
        const rendered = hljs.highlightAuto(decodedCode).value;
        return `<pre><code class="hljs">${rendered}</code></pre>`;
      }
    );

    // A resposta vem do LLM e pode refletir conteúdo de documentos: sanitiza antes de
    // entregar ao [innerHTML]. O sanitizador do Angular mantém `class` e `span` (realce)
    // e remove scripts, atributos `on*` e URLs `javascript:`.
    return this.sanitizer.sanitize(SecurityContext.HTML, highlighted) ?? "";
  }

  private decodeHtml(code: string): string {
    return code
      .replaceAll("&amp;", "&")
      .replaceAll("&lt;", "<")
      .replaceAll("&gt;", ">")
      .replaceAll("&#39;", "'")
      .replaceAll("&quot;", '"');
  }
}
