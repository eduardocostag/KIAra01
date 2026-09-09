import assert from "node:assert/strict"
import test from "node:test"
import { instagramProfileUrl, parsePipeline, parsePipelineEntry, safeWhatsAppUrl, phoneHref, requestPipeline, whatsappComposerUrl } from "../src/lib/api/pipeline.ts"

const entry = { id: "entry-1", stage: "new", next_action: null, version: 1, updated_at: "2026-09-09T00:00:00Z", consumer: { id: "lead-1", display_name: "Contato de teste", instagram_username: null, phone: "+5511987654321" } }

test("Maps contact has no invented Instagram or WhatsApp", () => {
  const parsed = parsePipeline({ items: [entry] })[0]
  assert.equal(parsed.consumer.instagram_username, null)
  assert.equal(parsed.consumer.whatsapp_url, null)
  assert.equal(phoneHref(parsed.consumer.phone), "tel:+5511987654321")
})
test("malformed CRM payload cannot become an empty state", () => {
  assert.throws(() => parsePipeline({}))
  assert.throws(() => parsePipeline({ items: [{ ...entry, version: 0 }] }))
  assert.throws(() => parsePipeline({ items: [{ ...entry, stage: "fake" }] }))
  assert.deepEqual(parsePipeline({ items: [] }), [])
})
test("only real WhatsApp contact links survive URL validation", () => {
  assert.equal(safeWhatsAppUrl("https://wa.me/5511987654321"), "https://wa.me/5511987654321")
  assert.equal(safeWhatsAppUrl("https://api.whatsapp.com/send?phone=5511987654321"), "https://wa.me/5511987654321")
  for (const unsafe of ["javascript:alert(1)", "https://wa.me.evil.test/5511987654321", "https://wa.me/", "https://user:pass@wa.me/5511987654321", "+5511987654321"]) assert.equal(safeWhatsAppUrl(unsafe), null)
  const parsed = parsePipelineEntry({ ...entry, consumer: { ...entry.consumer, source_url: "javascript:alert(1)" } })
  assert.equal(parsed.consumer.source_url, null)
})
test("outreach links prefill text without pretending a phone is confirmed WhatsApp", () => {
  assert.deepEqual(
    whatsappComposerUrl("(11) 98765-4321", null, "Olá & tudo bem?"),
    { url: "https://wa.me/5511987654321?text=Ol%C3%A1%20%26%20tudo%20bem%3F", confirmed: false },
  )
  assert.deepEqual(
    whatsappComposerUrl(null, "https://wa.me/5511987654321", "Mensagem"),
    { url: "https://wa.me/5511987654321?text=Mensagem", confirmed: true },
  )
  assert.equal(whatsappComposerUrl("1234", null, "Mensagem"), null)
})
test("Instagram profile links accept usernames, not arbitrary URLs", () => {
  assert.equal(instagramProfileUrl("@kiara.agency"), "https://www.instagram.com/kiara.agency/")
  assert.equal(instagramProfileUrl("https://evil.test"), null)
})
test("version conflict tells user to refresh, never pretends mutation succeeded", async (t) => {
  t.mock.method(globalThis, "fetch", async () => Response.json({ error: { message: "Conflict" } }, { status: 412 }))
  await assert.rejects(requestPipeline("/api/pipeline/entry-1", { method: "PATCH" }), /outra sessão/)
})
test("HTML error is surfaced instead of accepted as CRM data", async (t) => {
  t.mock.method(globalThis, "fetch", async () => new Response("<html>Error</html>"))
  await assert.rejects(requestPipeline("/api/pipeline"), /resposta inválida/)
})
