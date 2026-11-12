import assert from "node:assert/strict"
import { test } from "node:test"
import {
  hunterEvidenceLabel,
  hunterMissingEvidence,
  hunterResultLocation,
  parseHunterJob,
  parseHunterHistory,
  publicEmail,
  publicWebsiteUrl,
  requestHunter,
} from "../src/lib/api/hunter-client.ts"

const job = { id: "saved-search", market: "b2b", query: "clínicas", location: "SP", sources: ["web"], result_limit: 10, status: "completed", results: [{ id: "lead-1", source: "web", title: "Clínica", url: "https://example.com", summary: "Informação pública" }] }

test("explains missing lead evidence without implying missing data was verified", () => {
  assert.deepEqual(hunterMissingEvidence(undefined), [])
  assert.deepEqual(hunterMissingEvidence({ lead_requirements_missing: ["phone_or_whatsapp", "verified_location", "verified_location"] }), ["telefone ou WhatsApp público", "localização confirmada"])
})

test("accepts completed results and a genuine empty history", () => {
  assert.equal(parseHunterJob(job).results.length, 1)
  assert.deepEqual(parseHunterHistory({ items: [] }), [])
})
test("does not silently treat missing or malformed payloads as no results", () => {
  for (const invalid of [{}, null, { items: {} }, { items: [{}] }]) assert.throws(() => parseHunterHistory(invalid))
  assert.throws(() => parseHunterJob({ ...job, results: null }))
  assert.throws(() => parseHunterJob({ ...job, status: "unknown" }))
})
test("rejects unsafe links from external results", () => {
  assert.throws(() => parseHunterJob({ ...job, results: [{ ...job.results[0], url: "javascript:alert(1)" }] }))
})
test("preserves verified Maps evidence and rejects malformed evidence fields", () => {
  const result = {
    ...job.results[0],
    source: "google_maps",
    public_data: {
      detail_inspected: true,
      address: "Rua Exemplo, 100",
      email: "contato@example.com",
      website_url: "https://example.com/",
      rating: 4.8,
      user_rating_count: 21,
    },
  }
  assert.equal(parseHunterJob({ ...job, results: [result] }).results[0].public_data.rating, 4.8)
  assert.throws(() => parseHunterJob({
    ...job,
    results: [{ ...result, public_data: { detail_inspected: "yes" } }],
  }))
  assert.throws(() => parseHunterJob({
    ...job,
    results: [{ ...result, public_data: { lead_requirements_missing: "phone" } }],
  }))
})
test("parses incomplete-candidate counts for the Hunter quality gate", () => {
  const parsed = parseHunterJob({ ...job, validation: { checked: 5, accepted: 2, excluded: 3, unknown: 0, incomplete: 2, source_failures: 0 } })
  assert.equal(parsed.validation.incomplete, 2)
})
test("labels manually supplied and unverified search data honestly", () => {
  assert.match(hunterEvidenceLabel("instagram", { manual_import: true }), /não verificado/)
  assert.match(hunterEvidenceLabel("google_maps", { detail_inspected: true }), /inspecionada/)
  assert.match(hunterEvidenceLabel("web", undefined), /vínculo.*não confirmado/)
  assert.match(hunterResultLocation("web", undefined, "Porto Alegre"), /não confirmada/)
  assert.equal(hunterResultLocation("google_maps", { detail_inspected: true, address: "Rua Exemplo" }, "Porto Alegre"), "Rua Exemplo")
})
test("only safe websites and syntactically valid public emails are linkable", () => {
  assert.equal(publicWebsiteUrl("https://example.com/"), "https://example.com/")
  assert.equal(publicWebsiteUrl("javascript:alert(1)"), null)
  assert.equal(publicWebsiteUrl("https://user:pass@example.com/"), null)
  assert.equal(publicEmail("contato@example.com"), "contato@example.com")
  assert.equal(publicEmail("not-an-email"), null)
})
test("HTML 200 is an explicit failure, not an empty success", async (t) => {
  t.mock.method(globalThis, "fetch", async () => new Response("<html>Login</html>", { status: 200 }))
  await assert.rejects(requestHunter("/test"), /não retornou os dados/)
})
test("expired sessions have an actionable message", async (t) => {
  t.mock.method(globalThis, "fetch", async () => Response.json({}, { status: 401 }))
  await assert.rejects(requestHunter("/test"), /sessão expirou/)
})
test("API errors preserve the diagnostic code and request reference", async (t) => {
  t.mock.method(globalThis, "fetch", async () => Response.json({ error: { code: "upstream_route_not_found", message: "A rota da API não foi encontrada.", request_id: "req-123" } }, { status: 502 }))
  await assert.rejects(requestHunter("/test"), /Código: upstream_route_not_found\. Referência: req-123\./)
})
test("unknown HTTP errors still identify their status", async (t) => {
  t.mock.method(globalThis, "fetch", async () => Response.json({}, { status: 503 }))
  await assert.rejects(requestHunter("/test"), /Código: http_503/)
})
test("a network request is bounded and advises recovering saved results", async (t) => {
  t.mock.method(globalThis, "fetch", (_, { signal }) => new Promise((resolve, reject) => {
    signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")))
  }))
  await assert.rejects(requestHunter("/test", {}, 15), /Atualizar resultados antes de repetir/)
})
