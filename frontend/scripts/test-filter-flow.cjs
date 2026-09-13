/* eslint-disable @typescript-eslint/no-require-imports -- This Node test loads the client TS modules through a CommonJS transpilation hook. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

// Exercise the actual client data and request modules in Node, with the same
// committed snapshot served by Next. No duplicated dashboard aggregation.
require.extensions['.ts'] = (module, filename) => {
  const output = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  });
  module._compile(output.outputText, filename);
};
const root = path.resolve(__dirname, '..');
global.fetch = async url => {
  const file = path.join(root, 'public', String(url));
  return new Response(fs.readFileSync(file), { status: 200 });
};
const { selectDatasetIds, postingScope } = require('../lib/filters.ts');
const { fetchStaticDashboard, fetchStaticPostings, fetchFilterOptions } = require('../lib/static-dashboard.ts');
const { streamChat } = require('../lib/api.ts');

async function main() {
  const manifest = JSON.parse(fs.readFileSync(path.join(root, 'public/data/dashboard/manifest.json')));
  const records = JSON.parse(fs.readFileSync(path.join(root, 'public/data/dashboard', manifest.analytics_file)));
  const dumps = manifest.datasets.dumps;
  assert.equal(records.length, manifest.record_count);
  assert.ok(dumps.some(dump => dump._timeline === 'Nov 2025'));
  assert.ok(dumps.some(dump => dump._timeline === 'Feb 2026'));
  let checks = 0;
  for (const timeline of manifest.datasets.timelines) {
    for (const source of ['Bayt', 'LinkedIn']) {
      const ids = selectDatasetIds(dumps, { country: 'Qatar', timeline, source });
      const expected = dumps.filter(d => d._country === 'Qatar' && d._timeline === timeline && d._source === source);
      assert.deepEqual(ids, expected.map(d => d._dump_id));
      assert.equal((await fetchStaticDashboard({ dumps: ids })).total, expected.reduce((sum, d) => sum + d.count, 0));
      checks++;
    }
  }
  const columns = { sector: 'sector', company: 'company', employment_type: 'employmentType', career_level: 'careerLevel', experience: 'experience', salary_bucket: 'salaryBracket' };
  for (const dump of dumps) {
    const selected = records.filter(row => row.dump === dump._dump_id);
    assert.equal(selected.length, dump.count);
    const options = await fetchFilterOptions([dump._dump_id]);
    for (const [filter, column] of Object.entries(columns)) {
      const value = selected.find(row => row[column])?.[column];
      if (!value) continue;
      assert.ok(options[filter].includes(value));
      const expected = selected.filter(row => String(row[column] ?? '').toLowerCase() === value.toLowerCase());
      const filters = { [filter]: value };
      const dashboard = await fetchStaticDashboard({ dumps: [dump._dump_id], ...filters });
      assert.equal(dashboard.total, expected.length, `${dump._dump_id}: ${filter}`);
      const postings = await fetchStaticPostings([dump._dump_id], postingScope(filters), 1, 5);
      assert.equal(postings.total, dashboard.total, `postings: ${dump._dump_id}: ${filter}`);
      checks++;
    }
    const sample = selected.find(row => row.sector && row.company);
    if (sample) {
      const expected = selected.filter(row => row.sector?.toLowerCase() === sample.sector.toLowerCase() && row.company?.toLowerCase() === sample.company.toLowerCase());
      assert.equal((await fetchStaticDashboard({ dumps: [dump._dump_id], sector: sample.sector, company: sample.company })).total, expected.length);
      checks++;
    }
    assert.equal((await fetchStaticDashboard({ dumps: [dump._dump_id], company: '__no_such_company__' })).total, 0);
  }
  let request;
  global.fetch = async (_url, options) => {
    request = JSON.parse(options.body);
    return new Response('data: [DONE]\n\n');
  };
  const ids = selectDatasetIds(dumps, { country: 'Qatar', timeline: 'Nov 2025', source: 'Bayt' });
  const filters = { company: 'Example', employment_type: 'Full-Time', salary_bucket: '$1K-1.5K' };
  for await (const event of streamChat('Describe the qualifications', 'filter-test', 'test', ids, undefined, filters)) { assert.equal(event.type, 'done'); }
  assert.deepEqual(request.dump_ids, ids);
  assert.deepEqual(request.filters, filters);
  console.log(`PASS: ${checks} dashboard/postings filter scenarios; combined dataset scope; zero matches; exact chat request propagation; ${records.length} records.`);
}
main().catch(error => { console.error(error); process.exitCode = 1; });
