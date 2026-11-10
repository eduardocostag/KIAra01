import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import ts from "typescript";

const source = readFileSync(new URL("../src/lib/api/server-client.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
function client(response) {
  const exports = {};
  const require = (name) => {
    if (name === "server-only") return {};
    if (name === "@/lib/auth") return { requireAccessToken: async () => "test-token", AuthenticationRequiredError: class extends Error {} };
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
