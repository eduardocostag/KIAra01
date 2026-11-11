'use strict';

// Upstream calls app.listen(port) without a host. Keep this local integration
// on loopback without modifying the pinned upstream checkout.
const net = require('node:net');
const listen = net.Server.prototype.listen;
net.Server.prototype.listen = function (...args) {
  const portOnly = typeof args[0] === 'number'
    || (typeof args[0] === 'string' && /^\d+$/.test(args[0]));
  if (portOnly && (args[1] === undefined || typeof args[1] === 'function')) {
    args.splice(1, 0, '127.0.0.1');
  } else if (args[0] && typeof args[0] === 'object' && 'port' in args[0]) {
    if (args[0].host && !['127.0.0.1', '::1', 'localhost'].includes(args[0].host)) {
      throw new Error('Kiara OpenWA only permits loopback listeners.');
    }
    args[0] = { ...args[0], host: args[0].host || '127.0.0.1' };
  } else if (portOnly && typeof args[1] === 'string'
      && !['127.0.0.1', '::1', 'localhost'].includes(args[1])) {
    throw new Error('Kiara OpenWA only permits loopback listeners.');
  }
  return listen.apply(this, args);
};
