import assert from "node:assert/strict"
import { test } from "node:test"
import { readFileSync } from "node:fs"
import ts from "typescript"

function route({ session = { access_token: "test-access", refresh_token: "never-export", expires_at: Math.floor(Date.now() / 1000) + 3600 }, revoked = false, role = "owner", memberId = "user-one", admin = true } = {}) {
  const exports = {}, calls = []
  const compiled = ts.transpileModule(readFileSync(new URL("../src/app/api/whatsapp-web/session/route.ts", import.meta.url), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText
  const mocks = {
    "@/lib/auth": { requireWorkspace: async () => ({ isSystemAdmin: admin }) },
    "@/lib/supabase/server": { createClient: async () => ({ auth: {
      getSession: async () => ({ data: { session }, error: null }),
      getUser: async token => { calls.push(token); return { data: { user: revoked ? null : { id: "user-one" } }, error: revoked ? new Error("revoked") : null } },
    } }) },
    "@/lib/api/server-client": { kiaraApi: async path => { calls.push(path); return Response.json({ user_id: memberId, role }) } },
  }
  new Function("require", "exports", compiled)(name => mocks[name], exports)
  return { ...exports, calls }
}
const request = origin => new Request("https://kiaralead.vercel.app/api/whatsapp-web/session", {
  method: "POST", headers: origin === undefined ? {} : { Origin: origin },
})

test("session transfer rejects cross-origin and missing origin before auth", async () => {
  for (const origin of [undefined, "https://attacker.test"]) {
    const api = route()
    assert.equal((await api.POST(request(origin))).status, 403)
    assert.equal(api.calls.length, 0)
  }
})

test("session transfer rejects missing, expired and revoked sessions", async () => {
  for (const options of [{ session: null }, { revoked: true }, { session: { access_token: "expired", expires_at: 1 } }]) {
    assert.equal((await route(options).POST(request("https://kiaralead.vercel.app"))).status, 401)
  }
})

test("session transfer enforces API membership identity and owner/admin role", async () => {
  for (const options of [{ role: "operator" }, { role: "viewer" }, { memberId: "another-user" }]) {
    assert.equal((await route(options).POST(request("https://kiaralead.vercel.app"))).status, 403)
  }
})

test("session transfer returns only a short-lived access lease without refresh token", async () => {
  const result = await route().POST(request("https://kiaralead.vercel.app"))
  const body = await result.json()
  assert.equal(result.status, 200)
  assert.deepEqual(Object.keys(body).sort(), ["access_token", "expires_at"])
  assert.equal(body.access_token, "test-access")
  assert.ok(body.expires_at <= Math.floor(Date.now() / 1000) + 90)
  assert.match(result.headers.get("cache-control"), /no-store/)
})

test("session transfer is administrator-only while WhatsApp and Chat are in early access", async () => {
  const api = route({ admin: false })
  assert.equal((await api.POST(request("https://kiaralead.vercel.app"))).status, 403)
  assert.equal(api.calls.length, 0)
})
