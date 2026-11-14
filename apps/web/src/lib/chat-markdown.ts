/** Turns the model's Markdown into clean blocks, so the chat never shows raw "##", "**" or "|" to people. */

export type Inline = { text: string; bold?: boolean; italic?: boolean; code?: boolean }
export type TextBlock = { kind: "heading" | "paragraph" | "quote"; inlines: Inline[] }
export type ListBlock = { kind: "bullets" | "numbers"; items: Inline[][] }
export type Block =
  | TextBlock
  | ListBlock
  | { kind: "table"; header: Inline[][]; rows: Inline[][][] }
  | { kind: "code"; text: string }

const INLINE = /(\*\*\*[^*\n]+\*\*\*|\*\*[^*\n]+\*\*|__[^_\n]+__|`[^`\n]+`|\[[^\]\n]+\]\([^)\s]+\)|(?<![\w*])\*(?!\s)[^*\n]+?(?<!\s)\*(?![\w*])|(?<![\w_])_(?!\s)[^_\n]+?(?<!\s)_(?![\w_]))/g

export function parseInline(text: string): Inline[] {
  const parts: Inline[] = []
  let last = 0
  for (const match of text.matchAll(INLINE)) {
    const token = match[0]
    if (match.index > last) parts.push({ text: text.slice(last, match.index) })
    if (token.startsWith("***")) parts.push({ text: token.slice(3, -3), bold: true, italic: true })
    else if (token.startsWith("**") || token.startsWith("__")) parts.push({ text: token.slice(2, -2), bold: true })
    else if (token.startsWith("`")) parts.push({ text: token.slice(1, -1), code: true })
    else if (token.startsWith("[")) parts.push({ text: token.slice(1, token.indexOf("](")) })
    else parts.push({ text: token.slice(1, -1), italic: true })
    last = match.index + token.length
  }
  if (last < text.length) parts.push({ text: text.slice(last) })
  // Leftover markers from unbalanced syntax ("**Dica:" without closing) are dropped too.
  return parts.map((part) => part.code ? part : { ...part, text: part.text.replace(/\*\*|__/g, "") }).filter((part) => part.text)
}

const cells = (line: string) => line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((cell) => parseInline(cell.trim()))

export function parseBlocks(source: string): Block[] {
  const blocks: Block[] = []
  const lines = source.replace(/\r\n?/g, "\n").split("\n")
  let paragraph: string[] = []
  const flush = () => {
    if (paragraph.length) blocks.push({ kind: "paragraph", inlines: parseInline(paragraph.join("\n")) })
    paragraph = []
  }
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index]
    if (/^\s*```/.test(line)) {
      flush()
      const code: string[] = []
      for (index += 1; index < lines.length && !/^\s*```/.test(lines[index]); index += 1) code.push(lines[index])
      blocks.push({ kind: "code", text: code.join("\n") })
      continue
    }
    if (!line.trim() || /^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) { flush(); continue }
    const heading = line.match(/^\s*#{1,6}\s+(.*?)\s*#*\s*$/)
    if (heading) { flush(); blocks.push({ kind: "heading", inlines: parseInline(heading[1]) }); continue }
    if (/^\s*\|.*\|\s*$/.test(line)) {
      flush()
      const table: string[] = []
      for (; index < lines.length && /^\s*\|.*\|\s*$/.test(lines[index]); index += 1) table.push(lines[index])
      index -= 1
      const body = table.filter((row) => !/^\s*\|?[\s:|-]+\|?\s*$/.test(row) || !row.includes("-"))
      const hasHeader = table.length > 1 && /^\s*\|?[\s:|-]+\|?\s*$/.test(table[1]) && table[1].includes("-")
      blocks.push({ kind: "table", header: hasHeader ? cells(body[0]) : [], rows: (hasHeader ? body.slice(1) : body).map(cells) })
      continue
    }
    const bullet = line.match(/^\s*[-*•+]\s+(.*)$/)
    const number = line.match(/^\s*\d+[.)]\s+(.*)$/)
    if (bullet || number) {
      flush()
      const kind = bullet ? "bullets" : "numbers"
      const previous = blocks.at(-1)
      const item = parseInline((bullet ?? number)![1])
      if (previous?.kind === kind) previous.items.push(item)
      else blocks.push({ kind, items: [item] })
      continue
    }
    const quote = line.match(/^\s*>\s?(.*)$/)
    if (quote) { flush(); blocks.push({ kind: "quote", inlines: parseInline(quote[1]) }); continue }
    paragraph.push(line)
  }
  flush()
  return blocks
}

const plain = (inlines: Inline[]) => inlines.map((part) => part.text).join("")

/** Clean text for copying and for the voice: no Markdown symbols at all. */
export function plainText(source: string): string {
  return parseBlocks(source).map((block) => {
    if (block.kind === "code") return block.text
    if (block.kind === "bullets") return block.items.map((item) => `• ${plain(item)}`).join("\n")
    if (block.kind === "numbers") return block.items.map((item, index) => `${index + 1}. ${plain(item)}`).join("\n")
    if (block.kind === "table") return [block.header, ...block.rows].filter((row) => row.length).map((row) => row.map(plain).join(" · ")).join("\n")
    return plain((block as TextBlock).inlines)
  }).join("\n\n")
}
