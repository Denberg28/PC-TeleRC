'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const publish = require('../scripts/publish_stable.cjs');
const digest = bytes => crypto.createHash('sha256').update(bytes).digest('hex');

function fixture() {
  const context = {repo: {owner: 'test', repo: 'test'}, sha: 'a'.repeat(40), runId: 123, runAttempt: '2'};
  const files = new Map(publish.expected.map(n => [n, Buffer.from('packaged ' + n)]));
  files.set('build-provenance.json', Buffer.from('\uFEFF' + JSON.stringify({commit: context.sha, run_id: '123', run_attempt: '2'})));
  files.set('frozen-ui-check.json', Buffer.from(JSON.stringify({passed: true, checks: {
    offline_tile_decode: true, offline_no_network: true, offline_no_fake_gps: true,
    map_minimize: true, map_restore: true, map_restore_anchor: true,
    actual_video_decode: true, control_disabled: true, media_no_control_side_effect: true,
  }})));
  function manifests() {
    for (const name of ['SHA256-windows.txt', 'SHA256-firmware.txt']) {
      const names = publish.expected.filter(n => name === 'SHA256-firmware.txt'
        ? n.startsWith('TeleRC-LoRa-') : !n.startsWith('TeleRC-LoRa-') && !n.startsWith('SHA256-'));
      files.set(name, Buffer.from(names.map(n => digest(files.get(n)) + '  ' + n).join('\r\n') + '\r\n'));
    }
  }
  manifests();
  const release = {id: 1, tag_name: 'v0.1.3', draft: true, target_commitish: 'old-build'};
  const updates = [];
  let downloads = 0;
  const repos = {
    listReleases: async () => [release],
    listReleaseAssets: async () => [...files].map(([name, bytes]) => ({name, size: bytes.length,
      digest: 'sha256:' + digest(bytes), state: 'uploaded', url: name})),
    updateRelease: async params => {updates.push(params); return {data: {html_url: 'test-release'}};},
  };
  const github = {paginate: async (fn, args) => fn(args), rest: {repos, git: {
    getRef: async () => {throw Object.assign(new Error('no tag'), {status: 404});},
  }}};
  const fetchImpl = async url => {downloads++; return {ok: true, body: [files.get(url)]};};
  return {context, files, release, updates, manifests, github,
    args: {github, context, fetchImpl, token: 'unused', core: {info() {}}},
    downloads: () => downloads};
}

test('publishes fully verified current build even when draft target is stale', async () => {
  const f = fixture(); await publish(f.args);
  assert.equal(f.downloads(), publish.expected.length);
  assert.equal(f.updates.length, 1);
  assert.equal(f.updates[0].target_commitish, f.context.sha);
  assert.equal(f.updates[0].draft, false);
  assert.equal(f.updates[0].make_latest, 'true');
});

for (const key of ['commit', 'run_id', 'run_attempt']) {
  test('rejects stale provenance ' + key, async () => {
    const f = fixture();
    const p = JSON.parse(f.files.get('build-provenance.json').toString().replace(/^\uFEFF/, ''));
    p[key] = 'stale'; f.files.set('build-provenance.json', Buffer.from(JSON.stringify(p))); f.manifests();
    await assert.rejects(publish(f.args), /provenance/); assert.equal(f.updates.length, 0);
  });
}

test('rejects altered installer bytes', async () => {
  const f = fixture(); f.args.fetchImpl = async url => ({ok: true,
    body: [url.endsWith('.exe') ? Buffer.from('corrupt') : f.files.get(url)]});
  await assert.rejects(publish(f.args), /checksum|size/); assert.equal(f.updates.length, 0);
});

test('rejects internally inconsistent checksum manifests', async () => {
  const f = fixture();
  f.files.set('SHA256-firmware.txt', Buffer.from(f.files.get('SHA256-firmware.txt').toString().replace(/[a-f0-9]{64}/, '0'.repeat(64))));
  await assert.rejects(publish(f.args), /Manifest checksum/); assert.equal(f.updates.length, 0);
});

test('rejects missing checksum manifest entries', async () => {
  const f = fixture(); f.files.set('SHA256-windows.txt', Buffer.from(f.files.get('SHA256-windows.txt').toString().split('\r\n').slice(1).join('\r\n')));
  await assert.rejects(publish(f.args), /checksum manifest/); assert.equal(f.updates.length, 0);
});

test('rejects a missing required download', async () => {
  const f = fixture(); f.files.delete('OFFLINE-MAPS.md');
  await assert.rejects(publish(f.args), /Missing verified download/); assert.equal(f.updates.length, 0);
});

test('rejects frozen report with false media or map checks', async () => {
  const f = fixture(); const report = JSON.parse(f.files.get('frozen-ui-check.json'));
  report.checks.offline_no_fake_gps = false;
  f.files.set('frozen-ui-check.json', Buffer.from(JSON.stringify(report))); f.manifests();
  await assert.rejects(publish(f.args), /Frozen/); assert.equal(f.updates.length, 0);
});

test('never moves an existing tag from another commit', async () => {
  const f = fixture(); f.github.rest.git.getRef = async () => ({data: {object: {type: 'commit', sha: 'b'.repeat(40)}}});
  await assert.rejects(publish(f.args), /Existing.*tag/); assert.equal(f.updates.length, 0);
});

test('allows existing tag already at tested commit', async () => {
  const f = fixture(); f.github.rest.git.getRef = async () => ({data: {object: {type: 'commit', sha: f.context.sha}}});
  await publish(f.args); assert.equal(f.updates.length, 1);
});

test('does not overwrite an already published stable release', async () => {
  const f = fixture(); f.release.draft = false;
  await assert.rejects(publish(f.args), /unpublished stable draft/); assert.equal(f.updates.length, 0);
});

test('rejects failed downloads without publishing', async () => {
  const f = fixture(); f.args.fetchImpl = async () => ({ok: false});
  await assert.rejects(publish(f.args), /Download failed/); assert.equal(f.updates.length, 0);
});
