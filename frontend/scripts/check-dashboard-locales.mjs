import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const root = new URL('../', import.meta.url);
const [english, arabic] = await Promise.all([
  readFile(new URL('locales/dashboard.en.json', root), 'utf8').then(JSON.parse),
  readFile(new URL('locales/dashboard.ar.json', root), 'utf8').then(JSON.parse),
]);

const englishKeys = Object.keys(english).sort();
const arabicKeys = Object.keys(arabic).sort();

assert.deepEqual(arabicKeys, englishKeys, 'Arabic and English dashboard catalogs must have identical keys');

for (const key of englishKeys) {
  assert.equal(typeof arabic[key], 'string', `Arabic message ${key} must be a string`);
  assert.ok(arabic[key].trim(), `Arabic message ${key} must not be empty`);
  assert.match(arabic[key], /[\u0600-\u06ff]/, `Arabic message ${key} must contain Arabic text`);
  assert.notEqual(arabic[key], english[key], `Arabic message ${key} must not reuse the English text`);
}

console.log(`Dashboard locale coverage passed for ${englishKeys.length} messages.`);
