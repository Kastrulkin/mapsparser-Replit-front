import { test } from 'node:test';
import assert from 'node:assert/strict';
import { repairEntryGraph } from './repair_frontend_entry_graph.mjs';

test('renames the complete reverse dependency closure, preserving the patched entry and unrelated assets', () => {
  const files = new Map([
    ['index-old.js', 'export const context="old";'],
    ['index-new.js', 'import("./layout.js");export const context="new"; // language URL fix'],
    ['layout.js', 'import {context} from "./index-old.js";import("./page.js");'],
    ['page.js', 'import "./layout.js";import "./vendor.js";'],
    ['vendor.js', 'export const untouched=1;'],
    ['unused.js', 'import "./index-old.js";'],
  ]);
  const result = repairEntryGraph(files, 'index-new.js', 'index-old.js', 'fix');
  assert.equal(result.output.size, 3);
  assert.ok(result.output.get('index-new-fix.js').includes('language URL fix'));
  assert.ok(result.output.get('layout-fix.js').includes('./index-new-fix.js'));
  assert.ok(result.output.get('page-fix.js').includes('./layout-fix.js'));
  assert.ok(result.output.get('page-fix.js').includes('./vendor.js'));
  assert.equal(result.output.has('vendor-fix.js'), false);
  assert.equal(result.output.has('unused-fix.js'), false);
  assert.equal(result.rewrite('<script src="/assets/index-new.js"></script>'), '<script src="/assets/index-new-fix.js"></script>');
  assert.equal(files.get('layout.js'), 'import {context} from "./index-old.js";import("./page.js");');
});

test('rejects absent entries and unsafe release labels', () => {
  assert.throws(() => repairEntryGraph(new Map(), 'a.js', 'b.js', 'fix'), /Missing entry/);
  assert.throws(() => repairEntryGraph(new Map([['a.js',''],['b.js','']]), 'a.js', 'b.js', '../fix'), /Invalid release/);
});
