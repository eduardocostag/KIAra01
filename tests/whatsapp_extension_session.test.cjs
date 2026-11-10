const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')

function worker() {
  let handler
  const calls = []
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../extensions/kiara-whatsapp/service-worker.js'), 'utf8'), {
    URL, Date, setTimeout,
    chrome: { runtime: { onMessage: { addListener(fn) { handler = fn } } }, tabs: { onRemoved: { addListener() {} } } },
    fetch: async (url, init) => { calls.push({ url, body: JSON.parse(init.body) }); return { ok: true, json: async () => ({ ok: true }) } },
  })
  return { calls, run(request, sender) { return new Promise(resolve => handler(request, sender, resolve)) } }
}
const sender = { url: 'https://kiaralead.vercel.app/app', frameId: 0, tab: { id: 1 } }
const session = () => ({ type: 'kiara-executor-session', access_token: 'test-token', expires_at: Math.floor(Date.now() / 1000) + 90 })

test('worker forwards session only from the allowed top-level website', async () => {
  for (const badSender of [{ ...sender, frameId: 1 }, { ...sender, url: 'https://attacker.test/' }, { ...sender, tab: undefined }]) {
    const w = worker()
    assert.ok((await w.run(session(), badSender)).error)
    assert.equal(w.calls.length, 0)
  }
  const w = worker()
  assert.equal((await w.run(session(), sender)).error, null)
  assert.equal(w.calls[0].url, 'http://127.0.0.1:17843/v1/session')
})

test('worker rejects expired leases and forwards logout without token', async () => {
  const w = worker()
  assert.ok((await w.run({ ...session(), expires_at: 1 }, sender)).error)
  assert.equal(w.calls.length, 0)
  await w.run({ type: 'kiara-executor-session', access_token: null, expires_at: 0 }, sender)
  assert.deepEqual(w.calls[0].body, { access_token: null, expires_at: 0 })
})

test('content script transfers credentials directly to extension without exposing them to page messages', async () => {
  const calls = [], listeners = {}, intervals = []
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../extensions/kiara-whatsapp/kiara-content.js'), 'utf8'), {
    window: { location: { origin: 'https://kiaralead.vercel.app' }, addEventListener(name, fn) { listeners[name] = fn }, postMessage() { throw new Error('unexpected token exposure') } },
    chrome: { runtime: { sendMessage: async body => { calls.push(body); return {} } } },
    fetch: async () => ({ ok: true, status: 200, json: async () => ({ access_token: 'test-token', expires_at: 12345 }) }),
    AbortSignal, setInterval(fn) { intervals.push(fn) },
  })
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(calls[0].type, 'kiara-executor-session')
  assert.equal(calls[0].access_token, 'test-token')
  assert.equal(intervals.length, 1)
})

test('content script clears logout but never refreshes a lease on network failure', async () => {
  for (const status of [401, 403, 503, 'network-failure']) {
    const calls = []
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../extensions/kiara-whatsapp/kiara-content.js'), 'utf8'), {
      window: { location: { origin: 'https://kiaralead.vercel.app' }, addEventListener() {} },
      chrome: { runtime: { sendMessage: async body => { calls.push(body); return {} } } },
      fetch: async () => {
        if (status === 'network-failure') throw new Error('offline')
        return { ok: false, status }
      },
      AbortSignal, setInterval() {},
    })
    await new Promise(resolve => setImmediate(resolve))
    if (status === 401 || status === 403) {
      assert.equal(calls.length, 1)
      assert.equal(calls[0].access_token, null)
    } else assert.equal(calls.length, 0)
  }
})
