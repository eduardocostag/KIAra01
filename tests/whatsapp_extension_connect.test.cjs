const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')

function connection({ missing = false } = {}) {
  let attempts = 0
  const waits = []
  const context = {
    URL, Date,
    setTimeout(callback, delay) { waits.push(delay); queueMicrotask(callback) },
    chrome: {
      runtime: { onMessage: { addListener() {} } },
      tabs: {
        onRemoved: { addListener() {} },
        query: async () => [{ id: 7, windowId: 1, active: true }],
        update: async () => {},
        async sendMessage(_id, message) {
          assert.equal(message.type, 'kiara-whatsapp-status')
          attempts += 1
          if (missing) throw new Error('Receiving end does not exist')
          return { ready: attempts >= 3 }
        },
      },
      windows: { update: async () => {} },
    },
    fetch() { throw new Error('No network or messages are allowed in this test') },
  }
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../extensions/kiara-whatsapp/service-worker.js'), 'utf8') + '\nglobalThis.connectTest = prepareWhatsApp', context)
  return { run: () => context.connectTest(), attempts: () => attempts, waits }
}

test('connecting waits for the user to scan the WhatsApp Web QR instead of failing immediately', async () => {
  const value = connection()
  await value.run()
  assert.equal(value.attempts(), 3)
  assert.deepEqual(value.waits, [1500, 1500])
})

test('a missing content script times out with recovery instructions and no send', async () => {
  const value = connection({ missing: true })
  await assert.rejects(value.run(), /Atualize a guia/)
  assert.equal(value.attempts(), 120)
})
