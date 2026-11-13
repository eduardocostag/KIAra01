import assert from "node:assert/strict"
import { test } from "node:test"
import { pickFeminineVoice, speechChunks } from "../src/lib/voice-text.ts"

const v = (name, lang = "pt-BR") => ({ name, lang })

test("never picks the male Windows voice when a female pt-BR voice exists", () => {
  const voices = [v("Microsoft Daniel - Portuguese (Brazil)"), v("Microsoft Maria - Portuguese (Brazil)"), v("Microsoft Zira - English (United States)", "en-US")]
  assert.equal(pickFeminineVoice(voices).name, "Microsoft Maria - Portuguese (Brazil)")
})

test("prefers neural voices and the Kiara voice (Francisca)", () => {
  const voices = [v("Google português do Brasil"), v("Microsoft Francisca Online (Natural) - Portuguese (Brazil)"), v("Microsoft Antonio Online (Natural) - Portuguese (Brazil)")]
  assert.equal(pickFeminineVoice(voices).name, "Microsoft Francisca Online (Natural) - Portuguese (Brazil)")
  assert.equal(pickFeminineVoice([v("Female voice", "pt_BR"), v("Male voice", "pt-BR")]).name, "Female voice")
  assert.equal(pickFeminineVoice([v("Daniel", "en-US")]), undefined)
})

test("splits replies so speech starts after a short first sentence", () => {
  const chunks = speechChunks("Oi! Tudo ótimo por aqui. Para encher a agenda, ative pacientes antigos pelo WhatsApp. Também vale anunciar no Instagram. Quer ver como?")
  assert.equal(chunks[0], "Oi! Tudo ótimo por aqui.")
  assert.ok(chunks.length >= 2)
  assert.equal(chunks.join(" "), "Oi! Tudo ótimo por aqui. Para encher a agenda, ative pacientes antigos pelo WhatsApp. Também vale anunciar no Instagram. Quer ver como?")
  assert.deepEqual(speechChunks("sem pontuação final"), ["sem pontuação final"])
})
