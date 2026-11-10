const { test } = require('node:test')
const assert = require('node:assert/strict')
const vm = require('node:vm')
const fs = require('node:fs')
const path = require('node:path')
const code = fs.readFileSync(path.join(__dirname, '../extensions/kiara-whatsapp/whatsapp-content.js'), 'utf8')

function fixture({ draft = '', authorize = true, peer = '5511999999999', switchDuringAuthorize = false } = {}) {
  let handler
  let clicks = 0
  const messages = [{ id: `false_${peer}@c.us_1`, direction: 'in', text: 'Olá' }]
  const composer = { innerText: draft, isConnected: true, focus() {}, dispatchEvent() {},
    set textContent(value) { this.innerText = value } }
  const button = { closest() { return this }, click() {
    clicks += 1
    messages.push({ id: `true_${peer}@c.us_2`, direction: 'out', text: composer.innerText })
    composer.innerText = ''
  } }
  const document = {
    addEventListener() {}, removeEventListener() {},
    querySelector(selector) {
      if (selector === '#pane-side') return {}
      if (selector.includes("role='textbox'")) return composer
      if (selector.includes('compose-btn-send')) return button
      return null
    },
    querySelectorAll() {
      return messages.map(message => ({
        getAttribute() { return message.id }, matches() { return true },
        classList: { contains(value) { return value === 'message-out' && message.direction === 'out' } },
        querySelectorAll() { return [{ innerText: message.text }] },
      }))
    },
    execCommand(_action, _unused, text) { composer.innerText = text; return true },
  }
  vm.runInNewContext(code, {
    document, chrome: { runtime: {
      onMessage: { addListener(value) { handler = value } },
      sendMessage: async request => {
        if (request.type !== 'kiara-whatsapp-authorize') return {}
        if (switchDuringAuthorize) messages[0].id = 'false_5511888888888@c.us_other'
        return { allowed: authorize }
      },
    } },
    setTimeout, setInterval() {}, KeyboardEvent: class {}, InputEvent: class {},
  })
  return {
    messages, clicks: () => clicks,
    run(command) { return new Promise(resolve => handler({ type: 'kiara-whatsapp-command', command }, {}, resolve)) },
    command: { id: 'command-1', action: 'send', phone: '5511999999999', text: 'Posso ajudar?',
      expected_ids: [`false_5511999999999@c.us_1`], expires_at: Date.now() / 1000 + 30 },
  }
}

test('send clicks once and confirms a new outgoing bubble in the expected chat', async () => {
  const f = fixture()
  const result = await f.run(f.command)
  assert.equal(result.ok, true)
  assert.equal(result.message_id, 'true_5511999999999@c.us_2')
  assert.equal(f.clicks(), 1)
})

for (const [name, options, mutate] of [
  ['human draft', { draft: 'Rascunho humano' }, () => {}],
  ['different verified recipient', { peer: '5511888888888' }, () => {}],
  ['expired action', {}, c => { c.expires_at = 0 }],
  ['changed conversation', {}, c => { c.expected_ids = ['other'] }],
  ['executor authorization revoked', { authorize: false }, () => {}],
  ['recipient changed while authorizing', { switchDuringAuthorize: true }, () => {}],
]) {
  test(`blocks ${name} without clicking send`, async () => {
    const f = fixture(options)
    mutate(f.command)
    assert.equal((await f.run(f.command)).ok, false)
    assert.equal(f.clicks(), 0)
  })
}

test('read is scoped to the verified phone and never clicks send', async () => {
  const f = fixture()
  const result = await f.run({ ...f.command, action: 'read' })
  assert.equal(result.ok, true)
  assert.equal(result.messages.length, 1)
  assert.equal(f.clicks(), 0)
})
