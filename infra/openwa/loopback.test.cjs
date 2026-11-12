'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const net = require('node:net');
require('./loopback.cjs');

test('upstream port-only listener is bound to loopback', async () => {
  const server = net.createServer();
  await new Promise(resolve => server.listen(0, resolve));
  assert.equal(server.address().address, '127.0.0.1');
  await new Promise(resolve => server.close(resolve));
});
test('options listener defaults to loopback and refuses public interfaces', async () => {
  const server = net.createServer();
  await new Promise(resolve => server.listen({ port: 0 }, resolve));
  assert.equal(server.address().address, '127.0.0.1');
  await new Promise(resolve => server.close(resolve));
  assert.throws(() => net.createServer().listen(0, '0.0.0.0'), /only permits loopback/);
  assert.throws(() => net.createServer().listen({ port: 0, host: '0.0.0.0' }), /only permits loopback/);
});
