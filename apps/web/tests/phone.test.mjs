import assert from "node:assert/strict"
import test from "node:test"
import { normalizeWhatsAppPhone } from "../src/lib/api/pipeline.ts"

test("Brazilian numbers without country code receive 55 instead of being read as a foreign code", () => {
  assert.equal(normalizeWhatsAppPhone("(51) 99999-8888"), "5551999998888")
  assert.equal(normalizeWhatsAppPhone("51 3333-4444"), "555133334444")
  assert.equal(normalizeWhatsAppPhone("051 99999-8888"), "5551999998888")
  assert.equal(normalizeWhatsAppPhone("(55) 99999-8888"), "5555999998888")
})

test("numbers that already carry 55 are kept", () => {
  assert.equal(normalizeWhatsAppPhone("+55 11 99999-8888"), "5511999998888")
  assert.equal(normalizeWhatsAppPhone("5511999998888"), "5511999998888")
})

test("foreign numbers require an explicit international prefix", () => {
  assert.equal(normalizeWhatsAppPhone("+1 415 555 0123"), "14155550123")
  assert.equal(normalizeWhatsAppPhone("0014155550123"), "14155550123")
  assert.equal(normalizeWhatsAppPhone("14155550123123"), null)
})

test("empty or short values are rejected", () => {
  assert.equal(normalizeWhatsAppPhone(""), null)
  assert.equal(normalizeWhatsAppPhone(null), null)
  assert.equal(normalizeWhatsAppPhone("9999-8888"), null)
})
