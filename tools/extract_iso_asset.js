#!/usr/bin/env node
// Extract one named ISO 9660 file, joining multi-extent records in disc order.
const fs = require('node:fs');
const fsp = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');

async function main() {
  const [manifestPath, discPath, destination] = process.argv.slice(2);
  if (!manifestPath || !discPath || !destination || !discPath.startsWith('/')) {
    throw new Error('Usage: node tools/extract_iso_asset.js <manifest.json> </ISO/PATH> <destination>');
  }
  const manifest = JSON.parse(await fsp.readFile(manifestPath, 'utf8'));
  const extents = manifest.files.filter(entry => entry.path.toUpperCase() === discPath.toUpperCase());
  if (!extents.length || extents.some(entry => entry.directory || !entry.size)) {
    throw new Error(`No regular file extents for ${discPath}`);
  }
  const target = path.resolve(destination);
  if (fs.existsSync(target)) throw new Error(`Destination already exists: ${target}`);
  await fsp.mkdir(path.dirname(target), { recursive: true });
  const temporary = `${target}.partial`;
  const output = await fsp.open(temporary, 'wx');
  const digest = crypto.createHash('sha256');
  let written = 0;
  try {
    for (const extent of extents) {
      const start = extent.sector * 2048;
      const end = start + extent.size - 1;
      for await (const chunk of fs.createReadStream(manifest.iso, { start, end, highWaterMark: 4 << 20 })) {
        digest.update(chunk);
        let offset = 0;
        while (offset < chunk.length) {
          const result = await output.write(chunk, offset, chunk.length - offset);
          offset += result.bytesWritten;
        }
        written += chunk.length;
      }
    }
    await output.sync();
  } finally {
    await output.close();
  }
  const expected = extents.reduce((total, extent) => total + extent.size, 0);
  if (written !== expected) throw new Error(`Short extraction: ${written} of ${expected} bytes`);
  await fsp.rename(temporary, target);
  console.log(JSON.stringify({ discPath, destination: target, extents: extents.length,
    bytes: written, sha256: digest.digest('hex') }, null, 2));
}

main().catch(error => { console.error(error); process.exitCode = 1; });
