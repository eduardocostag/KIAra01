import assert from "node:assert/strict"
import test from "node:test"
import { parseInboxDetail, sendOutcome } from "../src/lib/api/inbox-contract.ts"

const base = { id: "thread-a", channel: "whatsapp_web", consumer: { id: "lead-a", display_name: "Cliente", phone: "5511999999999", instagram_username: null }, messages: [{ id: "message-a", direction: "inbound", text: "Qual o orçamento?", created_at: "2026-11-09T15:00:00Z" }], updated_at: "2026-11-09T15:00:00Z", unread_count: 1, qualification: { score: 85, temperature: "hot", confidence: 0.9, reasons: ["Solicitou orçamento"], recommendation: "Confirmar serviço" }, automation_enabled: true }

test("WhatsApp identity and evidence remain distinct from Instagram usernames", () => {
  const result = parseInboxDetail(base)
  assert.equal(result.handle, "5511999999999")
  assert.equal(result.channel, "whatsapp_web")
  assert.equal(result.temperature, "hot")
  assert.deepEqual(result.facts, ["Solicitou orçamento"])
  assert.equal(result.nextAction, "Confirmar serviço")
  assert.equal(result.messages[0].from, "lead")
  assert.equal(result.automationEnabled, true)
})
test("unqualified conversations do not invent a warm score", () => {
  const result = parseInboxDetail({ ...base, qualification: null, channel: "instagram", consumer: { id: "lead-b", display_name: "Pessoa", instagram_username: "pessoa" } })
  assert.equal(result.handle, "@pessoa")
  assert.equal(result.temperature, "unknown")
  assert.equal(result.score, 0)
  assert.deepEqual(result.facts, [])
})
test("malformed messages are errors rather than a false empty inbox", () => {
  assert.throws(() => parseInboxDetail({ ...base, messages: [{ id: "bad", direction: "system", text: "wrong" }] }))
  assert.throws(() => parseInboxDetail({ ...base, consumer: null }))
})
test("2xx delivery results never turn failed or uncertain sends into success", () => {
  assert.equal(sendOutcome({ status: "failed" }).accepted, false)
  assert.equal(sendOutcome({ status: "unknown" }).uncertain, true)
  assert.equal(sendOutcome({}).uncertain, true)
  assert.equal(sendOutcome({ status: "queued" }).accepted, true)
  assert.match(sendOutcome({ status: "queued" }).message, /fila não significa entrega/)
})
