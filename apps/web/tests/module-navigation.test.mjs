import assert from "node:assert/strict"
import { test } from "node:test"
import { modulePrefixForPath, isModuleNavActive } from "../src/lib/module-navigation.ts"

test("WhatsApp owns its pages while all lead routes keep their sidebar", () => {
  for (const path of ["/app/whatsapp", "/app/whatsapp/automacao", "/app/inbox", "/app/inbox/thread-1"]) assert.equal(modulePrefixForPath(path), "/app/whatsapp")
  for (const path of ["/app/hunter", "/app/pipeline", "/app/leads/123"]) assert.equal(modulePrefixForPath(path), "/app/leads")
  for (const path of ["/app/settings", "/app/settings/integrations", "/app/admin"]) assert.equal(modulePrefixForPath(path), null)
  for (const path of ["/app/automation", "/app/automation/x"]) assert.equal(modulePrefixForPath(path), "/app/automation")
  for (const path of ["/app", "/app/platform", "/app/whatsapp-other"]) assert.equal(modulePrefixForPath(path), null)
})

test("only one WhatsApp page or section is selected", () => {
  const links = ["/app/whatsapp", "/app/whatsapp#conexao", "/app/whatsapp#analise", "/app/whatsapp/automacao", "/app/whatsapp#configuracoes"]
  for (const href of links) {
    const [pathname, hash] = href.split("#")
    assert.deepEqual(links.filter((link) => isModuleNavActive(pathname, hash ? `#${hash}` : "", link)), [href])
  }
})
