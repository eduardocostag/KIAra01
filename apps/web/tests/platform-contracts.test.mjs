import assert from "node:assert/strict"
import test from "node:test"
import {
  isModuleKey, moduleHref, moduleKeys, parsePlatformContext, parsePlatformModule,
  parsePlatformModuleDetail, parsePlatformSkills, platformFailureKind,
} from "../src/lib/platform/contracts.ts"

const moduleFixture = (key) => ({
  key, name: key === "leads" ? "Leads" : key, description: "Descrição do módulo",
  href: moduleHref(key), status: key === "leads" ? "operational" : "preparation",
  status_label: key === "leads" ? "Operação existente" : "Em preparação", enabled: true,
  areas: ["Área de consulta"], integration_status: key === "leads" ? "existing" : "pending",
})
const context = (modules = moduleKeys.map(moduleFixture)) => ({
  brand: "KIARA", organization: { id: "org_a", name: "Empresa A" },
  membership: { id: "member_a", role: "owner" }, platform_role: "client", modules,
  phase: "structure_only", external_execution_enabled: false, access_source: "organization_policy",
})

test("uses the existing Leads URL and keeps new modules under the platform", () => {
  assert.equal(moduleHref("leads"), "/app")
  assert.deepEqual(moduleKeys.slice(1).map(moduleHref), ["/app/platform/whatsapp", "/app/platform/atendimento", "/app/platform/ti"])
  assert.equal(isModuleKey("unknown"), false)
  assert.equal(isModuleKey("../settings"), false)
})

test("accepts only server-authorized modules without adding missing modules", () => {
  const parsed = parsePlatformContext(context([moduleFixture("leads")]))
  assert.equal(parsed.organization.name, "Empresa A")
  assert.deepEqual(parsed.modules.map((entry) => entry.key), ["leads"])
  assert.deepEqual(parsePlatformContext(context([])).modules, [])
})

test("a failed or malformed context cannot become a successful empty platform", () => {
  for (const value of [null, {}, [], { error: { code: "unavailable" } }, context(null), context({})]) {
    assert.throws(() => parsePlatformContext(value))
  }
  for (const field of ["organization", "membership", "brand", "access_source", "phase"]) {
    assert.throws(() => parsePlatformContext({ ...context(), [field]: undefined }))
  }
})

test("rejects disabled, duplicated and unknown modules instead of displaying them", () => {
  assert.throws(() => parsePlatformContext(context([{ ...moduleFixture("whatsapp"), enabled: false }])))
  assert.throws(() => parsePlatformContext(context([moduleFixture("leads"), moduleFixture("leads")])))
  assert.throws(() => parsePlatformModule({ ...moduleFixture("ti"), key: "unknown" }))
})

test("rejects external, executable and cross-module navigation URLs", () => {
  for (const href of ["https://example.com", "javascript:alert(1)", "//example.com", "/app/hunter", "/app/platform/ti?org=other"]) {
    assert.throws(() => parsePlatformModule({ ...moduleFixture("ti"), href }))
  }
  assert.throws(() => parsePlatformModule({ ...moduleFixture("leads"), href: "/app/platform/leads" }))
})

test("new modules cannot claim operational integrations or external execution", () => {
  for (const key of ["whatsapp", "atendimento", "ti"]) {
    assert.throws(() => parsePlatformModule({ ...moduleFixture(key), status: "operational" }))
    assert.throws(() => parsePlatformModule({ ...moduleFixture(key), integration_status: "existing" }))
  }
  assert.throws(() => parsePlatformContext({ ...context(), external_execution_enabled: true }))
  assert.throws(() => parsePlatformContext({ ...context(), phase: "production" }))
})

test("accepts only recognized account roles and genuine organization fields", () => {
  for (const platform_role of ["client", "reseller", "platform_admin"]) {
    assert.equal(parsePlatformContext({ ...context(), platform_role }).platform_role, platform_role)
  }
  assert.throws(() => parsePlatformContext({ ...context(), platform_role: "owner" }))
  assert.throws(() => parsePlatformContext({ ...context(), organization: { id: "org", name: "" } }))
})

test("the server detail must confirm the requested module and inactive execution", () => {
  const detail = { module: moduleFixture("whatsapp"), phase: "structure_only", external_execution_enabled: false, execution_status: "inactive" }
  assert.equal(parsePlatformModuleDetail(detail, "whatsapp").module.key, "whatsapp")
  assert.throws(() => parsePlatformModuleDetail(detail, "ti"))
  assert.throws(() => parsePlatformModuleDetail({ ...detail, execution_status: "active" }, "whatsapp"))
  assert.throws(() => parsePlatformModuleDetail({ ...detail, module: { ...detail.module, enabled: false } }, "whatsapp"))
})

test("skills are references with inactive executors and known module scopes", () => {
  const skill = { name: "kiara-chatwoot", description: "Referência", modules: ["atendimento"], trust: "untrusted_reference", executor_status: "inactive" }
  const payload = { items: [skill], phase: "structure_only", external_execution_enabled: false }
  assert.equal(parsePlatformSkills(payload)[0].executor_status, "inactive")
  assert.deepEqual(parsePlatformSkills(payload)[0].modules, ["atendimento"])
  assert.deepEqual(parsePlatformSkills({ ...payload, items: [] }), [])
  assert.throws(() => parsePlatformSkills({ ...payload, items: [{ ...skill, executor_status: "active" }] }))
  assert.throws(() => parsePlatformSkills({ ...payload, items: [{ ...skill, modules: ["unknown"] }] }))
  assert.throws(() => parsePlatformSkills({ ...payload, items: [{ ...skill, modules: [] }] }))
  assert.throws(() => parsePlatformSkills({ ...payload, items: [skill, skill] }))
  assert.throws(() => parsePlatformSkills({ ...payload, external_execution_enabled: true }))
})

test("denied and unavailable responses remain distinct from successful modules", () => {
  assert.equal(platformFailureKind(401), "authentication")
  assert.equal(platformFailureKind(403), "denied")
  assert.equal(platformFailureKind(404), "denied")
  assert.equal(platformFailureKind(503), "unavailable")
  assert.equal(platformFailureKind(502), "unavailable")
})
