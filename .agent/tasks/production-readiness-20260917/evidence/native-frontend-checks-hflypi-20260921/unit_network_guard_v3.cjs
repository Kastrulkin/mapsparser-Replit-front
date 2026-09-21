'use strict';

const dgram = require('node:dgram');
const dns = require('node:dns');
const http = require('node:http');
const https = require('node:https');
const net = require('node:net');
const tls = require('node:tls');

function denied(operation) {
  return function denyNetworkAccess() {
    throw new Error(`hfLYPi unit network guard denied ${operation}`);
  };
}

net.connect = denied('net.connect');
net.createConnection = denied('net.createConnection');
net.Socket.prototype.connect = denied('net.Socket.prototype.connect');
tls.connect = denied('tls.connect');
http.request = denied('http.request');
http.get = denied('http.get');
https.request = denied('https.request');
https.get = denied('https.get');
dns.lookup = denied('dns.lookup');
dns.resolve = denied('dns.resolve');
dns.resolve4 = denied('dns.resolve4');
dns.resolve6 = denied('dns.resolve6');
dns.reverse = denied('dns.reverse');
dns.promises.lookup = denied('dns.promises.lookup');
dns.promises.resolve = denied('dns.promises.resolve');
dns.promises.resolve4 = denied('dns.promises.resolve4');
dns.promises.resolve6 = denied('dns.promises.resolve6');
dns.promises.reverse = denied('dns.promises.reverse');
dgram.Socket.prototype.send = denied('dgram.Socket.prototype.send');
globalThis.fetch = denied('globalThis.fetch');
