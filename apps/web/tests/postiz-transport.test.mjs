import assert from "node:assert/strict"
import { test } from "node:test"
import { createServer } from "node:http"
import { createRequire } from "node:module"
import { readFileSync } from "node:fs"
import ts from "typescript"
const native = createRequire(import.meta.url)
const compiled = ts.transpileModule(readFileSync(new URL("../src/lib/postiz/transport.ts", import.meta.url), "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText
const transport = {}
new Function("require", "exports", compiled)((name) => name === "server-only" ? {} : native(name), transport)

test("tenant Postiz endpoints cannot connect to private networks in production", async () => {
  const previous = process.env.NODE_ENV
  process.env.NODE_ENV = "production"
  try {
    for (const address of ["127.0.0.1", "10.0.0.1", "169.254.169.254", "192.168.1.1", "[::1]"]) await assert.rejects(transport.postizTransport(new URL(`https://${address}/`), {}, new Headers()), /privado/)
    assert.equal(transport.publicAddress("100.64.0.1"), false)
    assert.equal(transport.publicAddress("2001:db8::1"), false)
    assert.equal(transport.publicAddress("1.1.1.1"), true)
  } finally { if (previous === undefined) delete process.env.NODE_ENV; else process.env.NODE_ENV = previous }
})

test("local development transport sends form data and rejects redirects without retry", async () => {
  const previous = process.env.NODE_ENV
  process.env.NODE_ENV = "development"
  const received = []
  const server = createServer(async (request, response) => {
    const chunks = []; for await (const chunk of request) chunks.push(chunk)
    received.push({ path: request.url, authorization: request.headers.authorization, body: Buffer.concat(chunks).toString() })
    if (request.url === "/redirect") response.writeHead(302, { Location: "/destination" }).end()
    else response.writeHead(200, { "Content-Type": "application/json" }).end('{"id":"media-1"}')
  })
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve))
  const origin = `http://127.0.0.1:${server.address().port}`
  try {
    const form = new FormData(); form.append("file", new Blob(["image-content"]), "image.png")
    const result = await transport.postizTransport(new URL(`${origin}/upload`), { method: "POST", body: form }, new Headers({ Authorization: "synthetic" }))
    assert.equal(result.status, 200)
    assert.match(received[0].body, /image-content/)
    assert.equal(received[0].authorization, "synthetic")
    await assert.rejects(transport.postizTransport(new URL(`${origin}/redirect`), {}, new Headers({ Authorization: "synthetic" })), /Redirecionamento/)
    assert.deepEqual(received.map(item => item.path), ["/upload", "/redirect"])
  } finally {
    await new Promise(resolve => server.close(resolve))
    if (previous === undefined) delete process.env.NODE_ENV; else process.env.NODE_ENV = previous
  }
})
