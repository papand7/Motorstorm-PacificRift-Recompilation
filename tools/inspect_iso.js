#!/usr/bin/env node
// Read-only ISO 9660 inspection and targeted extraction for the supplied disc.
const fs = require('node:fs');
const fsp = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');
const { pipeline } = require('node:stream/promises');

const sectorSize = 2048;
function record(buffer, offset) {
  const length = buffer[offset];
  if (!length) return null;
  const entry = buffer.subarray(offset, offset + length);
  return {
    length,
    sector: entry.readUInt32LE(2),
    size: entry.readUInt32LE(10),
    directory: !!(entry[25] & 2),
    name: entry.subarray(33, 33 + entry[32]).toString('latin1').replace(/;\d+$/, ''),
  };
}
async function readAt(file, offset, size) {
  const data = Buffer.alloc(size);
  const { bytesRead } = await file.read(data, 0, size, offset);
  if (bytesRead !== size) throw new Error(`Short read at ${offset}`);
  return data;
}
async function listDirectory(file, directory, prefix = '') {
  const data = await readAt(file, directory.sector * sectorSize, directory.size);
  const entries = [];
  for (let offset = 0; offset < data.length;) {
    const entry = record(data, offset);
    if (!entry) { offset = (Math.floor(offset / sectorSize) + 1) * sectorSize; continue; }
    offset += entry.length;
    if (entry.name === '\0' || entry.name === '\1') continue;
    entry.path = `${prefix}/${entry.name}`;
    entries.push(entry);
    if (entry.directory) entries.push(...await listDirectory(file, entry, entry.path));
  }
  return entries;
}
function parseSfo(data) {
  if (data.subarray(0, 4).toString('hex') !== '00505346') throw new Error('Invalid PARAM.SFO');
  const keys = data.readUInt32LE(8), values = data.readUInt32LE(12);
  const result = {};
  for (let index = 0; index < data.readUInt32LE(16); index++) {
    const offset = 20 + index * 16;
    const keyOffset = keys + data.readUInt16LE(offset);
    const key = data.subarray(keyOffset, data.indexOf(0, keyOffset)).toString();
    const valueOffset = values + data.readUInt32LE(offset + 12);
    const length = data.readUInt32LE(offset + 4);
    result[key] = data.readUInt16LE(offset + 2) === 0x404
      ? data.readUInt32LE(valueOffset)
      : data.subarray(valueOffset, valueOffset + length).toString('utf8').replace(/\0+$/, '');
  }
  return result;
}
async function sha256(filename) {
  const hash = crypto.createHash('sha256');
  for await (const chunk of fs.createReadStream(filename)) hash.update(chunk);
  return hash.digest('hex');
}
async function main() {
  const [iso, output] = process.argv.slice(2);
  if (!iso || !output) throw new Error('Usage: node tools/inspect_iso.js <disc.iso> <output-directory>');
  const file = await fsp.open(iso, 'r');
  let entries;
  try {
    const descriptor = await readAt(file, sectorSize * 16, sectorSize);
    if (descriptor.subarray(1, 6).toString() !== 'CD001') throw new Error('No ISO 9660 primary volume descriptor');
    entries = await listDirectory(file, record(descriptor, 156));
  } finally { await file.close(); }
  const manifest = { iso: path.resolve(iso), files: entries.filter(x => !x.directory) };
  const targets = ['/PS3_GAME/PARAM.SFO', '/PS3_GAME/USRDIR/EBOOT.BIN'];
  for (const target of targets) {
    const entry = entries.find(x => x.path === target);
    if (!entry) throw new Error(`Missing ${target}`);
    const destination = path.join(output, target.slice(1));
    await fsp.mkdir(path.dirname(destination), { recursive: true });
    await pipeline(fs.createReadStream(iso, { start: entry.sector * sectorSize, end: entry.sector * sectorSize + entry.size - 1 }), fs.createWriteStream(destination));
    manifest[target] = { size: entry.size, sha256: await sha256(destination) };
    if (target.endsWith('PARAM.SFO')) manifest.sfo = parseSfo(await fsp.readFile(destination));
  }
  await fsp.mkdir(output, { recursive: true });
  await fsp.writeFile(path.join(output, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
  console.log(JSON.stringify({ files: manifest.files.length, sfo: manifest.sfo, extracted: targets.map(x => ({ path: x, ...manifest[x] })) }, null, 2));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
