import assert from "node:assert/strict"
import { test } from "node:test"
import { parseBlocks, parseInline, plainText } from "../src/lib/chat-markdown.ts"

const sample = `pense bem antes de liberar.

## Dicas rápidas

- **Iniciar com o sistema:** o serviço já vem habilitado.
- Use *atalhos* e \`kiara start\`.

---

1. Primeiro passo
2) Segundo passo

| Ação | Valor |
|---|---:|
| Anúncios | R$ 900 |

> Atenção: [veja o guia](https://example.com).`

test("headings, lists, tables and quotes lose their Markdown symbols", () => {
  const blocks = parseBlocks(sample)
  assert.deepEqual(blocks.map((block) => block.kind), ["paragraph", "heading", "bullets", "numbers", "table", "quote"])
  assert.equal(blocks[1].inlines[0].text, "Dicas rápidas")
  assert.deepEqual(blocks[2].items[0][0], { text: "Iniciar com o sistema:", bold: true })
  assert.equal(blocks[3].items.length, 2)
  assert.equal(blocks[4].header.map((cell) => cell[0].text).join(","), "Ação,Valor")
  assert.equal(blocks[4].rows[0][1][0].text, "R$ 900")
  const text = plainText(sample)
  for (const symbol of ["##", "**", "|", "---", "`", "](", "> "]) assert.ok(!text.includes(symbol), `${symbol} in ${text}`)
  assert.match(text, /• Iniciar com o sistema: o serviço já vem habilitado\./)
})

test("inline marks become styles and unbalanced markers disappear", () => {
  assert.deepEqual(parseInline("um **forte** e _leve_"), [{ text: "um " }, { text: "forte", bold: true }, { text: " e " }, { text: "leve", italic: true }])
  assert.equal(plainText("**Dica: sem fechar"), "Dica: sem fechar")
  // Arithmetic and snake_case are not italics.
  assert.equal(plainText("2 * 3 * 4 e nome_do_arquivo"), "2 * 3 * 4 e nome_do_arquivo")
})

test("code blocks are kept verbatim", () => {
  const blocks = parseBlocks("Veja:\n```bash\nnpm run **dev**\n```")
  assert.deepEqual(blocks.at(-1), { kind: "code", text: "npm run **dev**" })
})
