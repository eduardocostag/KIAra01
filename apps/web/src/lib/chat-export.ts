/** A Kiara answer taken out of the chat: WhatsApp text, a Word file or a page to save as PDF. */
import { parseBlocks, type Inline, type TextBlock } from "./chat-markdown"

const escape = (text: string) => text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;")

function waInline(parts: Inline[]): string {
  return parts.map((part) => {
    const text = part.text
    if (part.code) return "`" + text + "`"
    if (part.href) return `${text} (${part.href})`
    if (!text.trim()) return text
    // WhatsApp needs the marker glued to the words: "*negrito*", "_itálico_".
    const [, lead, core, tail] = text.match(/^(\s*)([\s\S]*?)(\s*)$/) ?? ["", "", text, ""]
    if (part.bold && part.italic) return `${lead}*_${core}_*${tail}`
    if (part.bold) return `${lead}*${core}*${tail}`
    if (part.italic) return `${lead}_${core}_${tail}`
    return text
  }).join("")
}

/** Text that keeps bold, italics and lists when pasted into WhatsApp. */
export function whatsappText(source: string): string {
  return parseBlocks(source).map((block) => {
    if (block.kind === "code") return "```" + block.text + "```"
    if (block.kind === "heading") return `*${block.inlines.map((part) => part.text).join("").trim()}*`
    if (block.kind === "bullets") return block.items.map((item) => `• ${waInline(item)}`).join("\n")
    if (block.kind === "numbers") return block.items.map((item, index) => `${index + 1}. ${waInline(item)}`).join("\n")
    if (block.kind === "table") return [block.header, ...block.rows].filter((row) => row.length).map((row, index) => {
      const line = row.map(waInline).join(" | ")
      return index === 0 && block.header.length ? `*${row.map((cell) => cell.map((part) => part.text).join("")).join(" | ")}*` : line
    }).join("\n")
    if (block.kind === "quote") return `> ${waInline(block.inlines)}`
    return waInline((block as TextBlock).inlines)
  }).join("\n\n")
}

function htmlInline(parts: Inline[]): string {
  return parts.map((part) => {
    let html = escape(part.text).replace(/\n/g, "<br>")
    if (part.code) return `<code>${html}</code>`
    if (part.bold) html = `<strong>${html}</strong>`
    if (part.italic) html = `<em>${html}</em>`
    return part.href ? `<a href="${escape(part.href)}">${html}</a>` : html
  }).join("")
}

export function answerHtml(source: string): string {
  return parseBlocks(source).map((block) => {
    if (block.kind === "code") return `<pre><code>${escape(block.text)}</code></pre>`
    if (block.kind === "heading") return `<h2>${htmlInline(block.inlines)}</h2>`
    if (block.kind === "quote") return `<blockquote>${htmlInline(block.inlines)}</blockquote>`
    if (block.kind === "bullets" || block.kind === "numbers") {
      const tag = block.kind === "bullets" ? "ul" : "ol"
      return `<${tag}>${block.items.map((item) => `<li>${htmlInline(item)}</li>`).join("")}</${tag}>`
    }
    if (block.kind === "table") return `<table>${block.header.length ? `<thead><tr>${block.header.map((cell) => `<th>${htmlInline(cell)}</th>`).join("")}</tr></thead>` : ""}<tbody>${block.rows.map((row) => `<tr>${row.map((cell) => `<td>${htmlInline(cell)}</td>`).join("")}</tr>`).join("")}</tbody></table>`
    return `<p>${htmlInline((block as TextBlock).inlines)}</p>`
  }).join("\n")
}

/** A complete, printable document; Word opens it as a .doc with the formatting. */
export function answerDocument(source: string, title: string): string {
  const date = new Date().toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" })
  return `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>${escape(title)}</title><style>
@page { margin: 2cm; }
body { font-family: Calibri, "Segoe UI", Arial, sans-serif; font-size: 11pt; line-height: 1.55; color: #1d1d1f; max-width: 720px; margin: 0 auto; }
header { border-bottom: 1px solid #ddd; margin-bottom: 18px; padding-bottom: 8px; color: #666; font-size: 9pt; }
h1 { font-size: 16pt; margin: 0 0 4px; color: #111; } h2 { font-size: 13pt; margin: 18px 0 6px; }
table { border-collapse: collapse; width: 100%; margin: 10px 0; } th, td { border: 1px solid #ccc; padding: 5px 8px; text-align: left; vertical-align: top; } th { background: #f2f2f5; }
pre { background: #f5f5f7; padding: 10px; border-radius: 6px; white-space: pre-wrap; font-size: 9.5pt; } code { font-family: Consolas, monospace; }
blockquote { border-left: 3px solid #ccc; margin: 8px 0; padding-left: 10px; color: #555; } a { color: #5b3fd6; }
</style></head><body><header><h1>${escape(title)}</h1>Kiara · ${date}</header>${answerHtml(source)}</body></html>`
}

export function answerTitle(source: string): string {
  const first = source.replace(/[#*_`>|[\]]/g, "").split("\n").map((line) => line.trim()).find(Boolean) ?? "Resposta da Kiara"
  return first.length > 70 ? `${first.slice(0, 67).trimEnd()}…` : first
}

export function downloadWord(source: string, title = answerTitle(source)) {
  const blob = new Blob(["﻿", answerDocument(source, title)], { type: "application/msword" })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = `${title.replace(/[\\/:*?"<>|…]+/g, "").trim().slice(0, 60) || "kiara-resposta"}.doc`
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

/** Opens the browser's print window on a clean copy of the answer; "Salvar como PDF" is one of its options. */
export function printAnswer(source: string, title = answerTitle(source)) {
  const frame = document.createElement("iframe")
  frame.setAttribute("aria-hidden", "true")
  frame.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0;"
  document.body.appendChild(frame)
  const done = () => setTimeout(() => frame.remove(), 1000)
  frame.onload = () => {
    const view = frame.contentWindow
    if (!view) return done()
    view.addEventListener("afterprint", done, { once: true })
    view.focus()
    view.print()
    setTimeout(done, 60_000)
  }
  frame.srcdoc = answerDocument(source, title)
}

/** An answer that stopped mid-way: interrupted, unclosed code block, or no final punctuation. */
export function looksUnfinished(source: string): boolean {
  const text = source.trim()
  if (!text) return false
  if ((text.match(/```/g)?.length ?? 0) % 2 === 1) return true
  const last = text.split("\n").at(-1)!.trim()
  if (/^\|.*\|$/.test(last) || /^[-*•]\s|^\d+[.)]\s/.test(last)) return false
  return text.length > 400 && !/[.!?…:;)"'”»\]*_`\p{Extended_Pictographic}]$/u.test(text)
}
