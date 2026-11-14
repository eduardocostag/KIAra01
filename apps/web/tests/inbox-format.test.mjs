import assert from "node:assert/strict"
import { test } from "node:test"
import { dayLabel, differentDay, listTime, mediaOf } from "../src/lib/inbox-format.ts"

// Friday 14 Nov 2026, 16:00 in São Paulo (19:00 UTC).
const now = new Date("2026-11-14T19:00:00Z")

test("media placeholders become friendly labels", () => {
  assert.deepEqual(mediaOf("[figurinha]"), { kind: "sticker", label: "Figurinha" })
  assert.deepEqual(mediaOf(" [Imagem] "), { kind: "image", label: "Foto" })
  assert.equal(mediaOf("Olha essa [figurinha] aqui"), null)
})

test("day separators read like WhatsApp", () => {
  assert.equal(dayLabel("2026-11-14T12:00:00Z", now), "Hoje")
  assert.equal(dayLabel("2026-11-14T02:30:00Z", now), "Ontem") // 23:30 on the 13th in São Paulo
  assert.match(dayLabel("2026-11-11T15:00:00Z", now), /^Quarta-feira$/)
  assert.equal(dayLabel("2026-10-02T15:00:00Z", now), "2 de outubro")
  assert.equal(dayLabel("2025-10-02T15:00:00Z", now), "2 de outubro de 2025")
  assert.equal(differentDay("2026-11-14T02:30:00Z", "2026-11-14T12:00:00Z"), true)
  assert.equal(differentDay("2026-11-14T12:00:00Z", "2026-11-14T20:00:00Z"), false)
})

test("conversation list shows time today, then Ontem, weekday or date", () => {
  assert.equal(listTime("2026-11-14T17:05:00Z", now), "14:05")
  assert.equal(listTime("2026-11-13T17:05:00Z", now), "Ontem")
  assert.equal(listTime("2026-11-11T17:05:00Z", now), "qua")
  assert.equal(listTime("2026-10-03T17:05:00Z", now), "03/10/26")
  assert.equal(listTime("not a date", now), "")
})
