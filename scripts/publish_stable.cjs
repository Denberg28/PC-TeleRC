'use strict';

const crypto = require('node:crypto');

const expected = [
  'PC-TeleRC-portable-v0.1.3.zip', 'PC-TeleRC-Setup-v0.1.3.exe',
  'PC-TeleRC-source-v0.1.3.zip', 'SHA256-windows.txt',
  'frozen-ui-check.json', 'OFFLINE-MAPS.md', 'build-provenance.json',
  'TeleRC-LoRa-915-PnP-v0.1.3-sketches.zip',
  'TeleRC-LoRa-915-PnP-v0.1.3-targets.zip', 'SHA256-firmware.txt',
];

module.exports = async function publishStable({github, context, core, token,
                                              fetchImpl = fetch}) {
  const releases = await github.paginate(github.rest.repos.listReleases, context.repo);
  const release = releases.find(r => r.tag_name === 'v0.1.3');
  if (!release || !release.draft) throw new Error('Expected an unpublished stable draft');
  const assets = await github.paginate(github.rest.repos.listReleaseAssets,
    {...context.repo, release_id: release.id});
  const verified = new Map();
  const documents = new Map();
  for (const name of expected) {
    const matches = assets.filter(a => a.name === name);
    const asset = matches[0];
    if (matches.length !== 1 || asset.state !== 'uploaded' || asset.size <= 0 ||
        !/^sha256:[a-f0-9]{64}$/.test(asset.digest || '')) {
      throw new Error('Missing verified download: ' + name);
    }
    const response = await fetchImpl(asset.url, {headers: {
      Authorization: 'Bearer ' + token, Accept: 'application/octet-stream',
    }});
    if (!response.ok) throw new Error('Download failed: ' + name);
    const hash = crypto.createHash('sha256');
    const keep = /\.(json|txt)$/.test(name);
    const chunks = [];
    let size = 0;
    for await (const chunk of response.body) {
      const bytes = Buffer.from(chunk);
      size += bytes.length;
      if (size > asset.size || (keep && size > 1024 * 1024)) {
        throw new Error('Download exceeds expected size: ' + name);
      }
      hash.update(bytes);
      if (keep) chunks.push(bytes);
    }
    const digest = hash.digest('hex');
    if (size !== asset.size || 'sha256:' + digest !== asset.digest) {
      throw new Error('Download checksum mismatch: ' + name);
    }
    verified.set(name, digest);
    if (keep) documents.set(name, Buffer.concat(chunks).toString('utf8').replace(/^\uFEFF/, ''));
  }
  for (const manifest of ['SHA256-windows.txt', 'SHA256-firmware.txt']) {
    const listed = new Map();
    for (const line of documents.get(manifest).trim().split(/\r?\n/)) {
      const match = /^([a-f0-9]{64})  ([^/\\]+)$/.exec(line);
      if (!match || listed.has(match[2])) throw new Error('Invalid checksum manifest: ' + manifest);
      listed.set(match[2], match[1]);
      if (verified.get(match[2]) !== match[1]) throw new Error('Manifest checksum mismatch: ' + match[2]);
    }
    const required = manifest === 'SHA256-firmware.txt'
      ? expected.filter(n => n.startsWith('TeleRC-LoRa-'))
      : expected.filter(n => !n.startsWith('TeleRC-LoRa-') && !n.startsWith('SHA256-'));
    if (required.some(n => !listed.has(n))) throw new Error('Incomplete checksum manifest: ' + manifest);
  }
  const provenance = JSON.parse(documents.get('build-provenance.json'));
  if (provenance.commit !== context.sha || String(provenance.run_id) !== String(context.runId) ||
      String(provenance.run_attempt) !== String(context.runAttempt)) {
    throw new Error('Build provenance does not match this tested workflow');
  }
  const report = JSON.parse(documents.get('frozen-ui-check.json'));
  const requiredChecks = ['offline_tile_decode', 'offline_no_network', 'offline_no_fake_gps',
    'map_minimize', 'map_restore', 'map_restore_anchor', 'actual_video_decode',
    'control_disabled', 'media_no_control_side_effect'];
  if (report.passed !== true || !report.checks ||
      requiredChecks.some(k => report.checks[k] !== true) ||
      Object.values(report.checks).some(v => v !== true)) {
    throw new Error('Frozen offline-map/media checks failed');
  }
  // Draft uploads can retain an older target_commitish. Trust the verified
  // build manifest, but never move an existing tag to a different commit.
  try {
    const ref = await github.rest.git.getRef({...context.repo, ref: 'tags/v0.1.3'});
    if (ref.data.object.type !== 'commit' || ref.data.object.sha !== context.sha) {
      throw new Error('Existing v0.1.3 tag does not match tested commit');
    }
  } catch (error) {
    if (error.status !== 404) throw error;
  }
  const published = await github.rest.repos.updateRelease({...context.repo,
    release_id: release.id, tag_name: 'v0.1.3',
    name: 'PC TeleRC v0.1.3 — Offline maps and LoRa', target_commitish: context.sha,
    draft: false, prerelease: false, make_latest: 'true'});
  core.info('Published stable Latest: ' + published.data.html_url);
};

module.exports.expected = expected;
