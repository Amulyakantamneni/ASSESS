// db.js
// Lightweight, dependency-free JSON-file datastore.
// Good enough for a small/medium volume site. Each "table" is a JSON array
// stored in its own file under /data. Writes are queued so concurrent
// requests never corrupt the file.

const fs = require('fs');
const path = require('path');

const DATA_DIR = path.join(__dirname, 'data');
if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });

function filePathFor(table) {
  return path.join(DATA_DIR, `${table}.json`);
}

function readTable(table) {
  const file = filePathFor(table);
  if (!fs.existsSync(file)) return [];
  const raw = fs.readFileSync(file, 'utf-8').trim();
  if (!raw) return [];
  try {
    return JSON.parse(raw);
  } catch (err) {
    console.error(`Failed to parse ${file}, resetting to empty array.`, err);
    return [];
  }
}

// Simple write queue per table to avoid race conditions on concurrent writes.
const writeQueues = {};

function writeTable(table, data) {
  const file = filePathFor(table);
  const tmpFile = `${file}.tmp`;

  const task = () =>
    new Promise((resolve, reject) => {
      fs.writeFile(tmpFile, JSON.stringify(data, null, 2), (err) => {
        if (err) return reject(err);
        fs.rename(tmpFile, file, (err2) => {
          if (err2) return reject(err2);
          resolve();
        });
      });
    });

  const prev = writeQueues[table] || Promise.resolve();
  const next = prev.then(task, task);
  writeQueues[table] = next.catch(() => {}); // keep the chain alive even if one write fails
  return next;
}

function insert(table, record) {
  const rows = readTable(table);
  rows.push(record);
  return writeTable(table, rows).then(() => record);
}

function all(table) {
  return readTable(table);
}

function findById(table, id) {
  return readTable(table).find((r) => r.id === id) || null;
}

function updateById(table, id, updates) {
  const rows = readTable(table);
  const idx = rows.findIndex((r) => r.id === id);
  if (idx === -1) return Promise.resolve(null);
  rows[idx] = { ...rows[idx], ...updates };
  return writeTable(table, rows).then(() => rows[idx]);
}

module.exports = { insert, all, findById, updateById };
