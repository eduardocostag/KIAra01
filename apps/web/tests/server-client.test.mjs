import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import ts from "typescript";

const source = readFileSync(new URL("../src/lib/api/server-client.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
function client(response, { admin = true, signedIn = true } = {}) {
  const exports = {};
  class AuthenticationRequiredError extends Error {}
  class AdministratorRequiredError extends Error {}
  const require = (name) => {
    if (name === "server-only") return {};
    if (name === "@/lib/auth") return {
      requireAccessToken: async () => { if (!signedIn) throw new AuthenticationRequiredError(); return "test-token"; },
      requireSystemAdmin: async () => { if (!signedIn) throw new AuthenticationRequiredError(); if (!admin) throw new AdministratorRequiredError(); },
      AuthenticationRequiredError, AdministratorRequiredError,
    };
    if (name === "@/lib/early-access") return { EARLY_ACCESS_API_PREFIXES: ["/v1/chat", "/v1/whatsapp-web"] };
    throw new Error(name);
  };
  new Function("require", "exports", "fetch", "process", "console", compiled)(require, exports, async () => response, { env: { KIARA_API_URL: "https://api.example.test", KIARA_COMPETITION_API_URL: "https://api.example.test" } }, { info() {}, warn() {}, error() {}, log() {} });
  return exports.kiaraApi;
}
test("successful deletion preserves an empty 204 for social and competition routes", async () => {
  for (const path of ["/v1/social/posts/one", "/v1/competition/instagram/connection"]) {
    const result = await client(new Response(null, { status: 204 }))(path, { method: "DELETE" });
    assert.equal(result.status, 204);
    assert.equal(await result.text(), "");
  }
});

test("integration access is rejected before forwarding for ordinary and signed-out users", async () => {
  for (const path of ["/v1/integrations", "/v1/integrations/instagram", "/v1/integrations/hermes/capabilities"]) {
    const denied = await client(Response.json({ secret: "must-never-be-returned" }), { admin: false })(path);
    assert.equal(denied.status, 403);
    assert.equal((await denied.json()).error.code, "system_admin_required");
    const signedOut = await client(Response.json({}), { signedIn: false })(path);
    assert.equal(signedOut.status, 401);
  }
});

test("early-access modules (Chat, WhatsApp) are administrator-only before forwarding", async () => {
  for (const path of ["/v1/chat/messages", "/v1/chat/status", "/v1/whatsapp-web/config", "/v1/whatsapp-web/analysis"]) {
    const denied = await client(Response.json({ text: "must-never-be-returned" }), { admin: false })(path);
    assert.equal(denied.status, 403);
    assert.equal((await denied.json()).error.code, "system_admin_required");
  }
  const allowed = await client(Response.json({ text: "ok" }))("/v1/chat/status");
  assert.equal(allowed.status, 200);
  const leads = await client(Response.json({ items: [] }), { admin: false })("/v1/leads");
  assert.equal(leads.status, 200);
});

test("system administrator can forward an integration request", async () => {
  const response = await client(Response.json({ items: [] }))("/v1/integrations");
  assert.equal(response.status, 200);
});
test("preserves rate-limit diagnostics and retry interval", async () => {
  const payload = { error: { code: "instagram_safety_cooldown", details: { retry_after: 86400 } } };
  const result = await client(Response.json(payload, { status: 429, headers: { "Retry-After": "86400" } }))("/v1/competition/kiara/analyses");
  assert.equal(result.status, 429);
  assert.equal(result.headers.get("Retry-After"), "86400");
  assert.deepEqual(await result.json(), payload);
});
test("a successful HTML response still fails explicitly", async () => {
  const result = await client(new Response("<html>login</html>"))("/v1/social/dashboard");
  assert.equal(result.status, 502);
});
