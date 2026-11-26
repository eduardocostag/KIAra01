import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import ts from "typescript";

const source = readFileSync(new URL("../src/lib/modules.ts", import.meta.url), "utf8");
const m = {};
new Function("exports", ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText)(m);

test("administrators always have every module; others what was chosen, or Leads when never configured", () => {
  assert.deepEqual(m.modulesFor("eduardocgonsalves@hotmail.com", { modules: [] }), ["leads", "whatsapp", "chat", "automation"]);
  // The chat is for the system administrators only: a client given "chat" still does not get it.
  assert.deepEqual(m.modulesFor("ana@empresa.com", { modules: ["chat", "leads", "bogus"] }), ["leads"]);
  assert.deepEqual(m.modulesFor("ana@empresa.com", { modules: [] }), []);
  assert.deepEqual(m.modulesFor("ana@empresa.com", { provider: "email" }), ["leads"]);
  assert.deepEqual(m.modulesFor("ana@empresa.com", undefined), ["leads"]);
});

test("pages and backend routes map to their module; shared pages to none", () => {
  assert.equal(m.moduleForPage("/app/chat"), "chat");
  assert.equal(m.moduleForPage("/app/whatsapp/automacao"), "whatsapp");
  assert.equal(m.moduleForPage("/app/inbox/123"), "whatsapp");
  assert.equal(m.moduleForPage("/app/hunter"), "leads");
  assert.equal(m.moduleForPage("/app/leads/abc"), "leads");
  assert.equal(m.moduleForPage("/app/automation"), "automation");
  for (const shared of ["/app", "/app/settings", "/app/aprovacoes", "/app/empresa", "/app/admin", "/app/chatbot"]) assert.equal(m.moduleForPage(shared), null, shared);
  assert.equal(m.moduleForApiPath("/v1/chat/stream"), "chat");
  assert.equal(m.moduleForApiPath("/v1/automation"), "automation");
  assert.equal(m.moduleForApiPath("/v1/leads"), null);
});
