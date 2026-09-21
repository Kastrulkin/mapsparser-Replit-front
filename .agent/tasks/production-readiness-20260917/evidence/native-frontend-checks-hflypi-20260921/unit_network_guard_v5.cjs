'use strict';

const dgram = require('node:dgram');
const dns = require('node:dns');
const http = require('node:http');
const https = require('node:https');
const net = require('node:net');
const tls = require('node:tls');

function deniedError(operation) {
  return new Error(`hfLYPi unit network guard denied ${operation}`);
}

function denied(operation) {
  return function denyNetworkAccess() {
    throw deniedError(operation);
  };
}

function deniedPromise(operation) {
  return function denyNetworkPromise() {
    return Promise.reject(deniedError(operation));
  };
}

function loopbackResult(hostname, options) {
  if (hostname !== 'localhost' && hostname !== '127.0.0.1' && hostname !== '::1') {
    throw deniedError('dns lookup');
  }
  const requestedFamily = typeof options === 'number' ? options : typeof options === 'object' && options ? options.family : 0;
  const family = requestedFamily === 6 ? 6 : hostname === '::1' ? 6 : 4;
  return { address: family === 6 ? '::1' : '127.0.0.1', family };
}

function lookup(hostname, options, callback) {
  let resolvedOptions = options;
  let resolvedCallback = callback;
  if (typeof options === 'function') {
    resolvedCallback = options;
    resolvedOptions = {};
  }
  if (typeof resolvedCallback !== 'function') {
    throw deniedError('dns lookup callback');
  }
  queueMicrotask(() => {
    let result;
    try {
      result = loopbackResult(hostname, resolvedOptions || {});
    } catch (error) {
      resolvedCallback(error);
      return;
    }
    if (typeof resolvedOptions === 'object' && resolvedOptions && resolvedOptions.all) {
      resolvedCallback(null, [result]);
      return;
    }
    resolvedCallback(null, result.address, result.family);
  });
}

function promisesLookup(hostname, options) {
  try {
    const result = loopbackResult(hostname, options || {});
    return Promise.resolve(typeof options === 'object' && options && options.all ? [result] : result);
  } catch (error) {
    return Promise.reject(error);
  }
}

net.connect = denied('net.connect');
net.createConnection = denied('net.createConnection');
net.Socket.prototype.connect = denied('net.Socket.prototype.connect');
tls.connect = denied('tls.connect');
http.request = denied('http.request');
http.get = denied('http.get');
https.request = denied('https.request');
https.get = denied('https.get');
dns.lookup = lookup;
dns.resolve = denied('dns.resolve');
dns.resolve4 = denied('dns.resolve4');
dns.resolve6 = denied('dns.resolve6');
dns.reverse = denied('dns.reverse');
dns.promises.lookup = promisesLookup;
dns.promises.resolve = deniedPromise('dns.promises.resolve');
dns.promises.resolve4 = deniedPromise('dns.promises.resolve4');
dns.promises.resolve6 = deniedPromise('dns.promises.resolve6');
dns.promises.reverse = deniedPromise('dns.promises.reverse');
dgram.Socket.prototype.send = denied('dgram.Socket.prototype.send');
globalThis.fetch = deniedPromise('globalThis.fetch');
