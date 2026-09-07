"""Verify source/runtime/static/API/Qdrant agreement for the monthly datasets.

Run --vectors after ingestion finishes; --semantic also calls the configured LLM.
Reports contain counts and test results, never credentials or raw source text.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import uuid

import pandas as pd
import requests

from config import DATA_DIR
from data_loader import load_all
from filter_registry import FILTER_REGISTRY
from fast_answers import _scope_base


def chat(base, dumps, filters, question):
    started = time.perf_counter()
    response = requests.post(base + '/api/chat', json={
        'question': question, 'session_id': 'verify-' + uuid.uuid4().hex,
        'dump_ids': dumps, 'filters': filters,
    }, timeout=240)
    response.raise_for_status()
    answer, info = '', {}
    for line in response.text.splitlines():
        if not line.startswith('data: ') or line == 'data: [DONE]':
            continue
        event = json.loads(line[6:])
        if event.get('type') == 'token':
            answer += event.get('token', '')
        if event.get('type') == 'retrieval':
            info = event.get('info', {})
    assert answer and '[Error:' not in answer, answer
    assert 'data: [DONE]' in response.text
    return answer, info, round(time.perf_counter() - started, 2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://localhost:8000')
    parser.add_argument('--vectors', action='store_true')
    parser.add_argument('--semantic', action='store_true')
    args = parser.parse_args()
    df, timelines = load_all(DATA_DIR, compact=True)
    static_dir = DATA_DIR.parents[1] / 'frontend/public/data/dashboard'
    manifest = json.loads((static_dir / 'manifest.json').read_text(encoding='utf-8'))
    records = json.loads((static_dir / manifest['analytics_file']).read_text(encoding='utf-8'))
    assert len(df) == len(records) == manifest['record_count']
    columns = {'sector': 'sector', 'company': 'company', 'employment_type': 'employmentType',
               'career_level': 'careerLevel', 'experience': 'experience', 'salary_bucket': 'salaryBracket'}
    def clean(value):
        return '' if pd.isna(value) else str(value).strip().casefold()
    # Compare every filterable value, not just totals that could hide mismatches.
    expected = Counter(tuple([str(row['_dump_id'])] + [clean(row[field.column]) for field in FILTER_REGISTRY.values()])
                       for _, row in df.iterrows())
    actual = Counter(tuple([row['dump']] + [clean(row.get(columns[key])) for key in FILTER_REGISTRY]) for row in records)
    assert actual == expected, f'Static/runtime filter mismatch: {sum((actual - expected).values())} rows'
    api_dumps = requests.get(args.base_url + '/api/datasets', timeout=30).json()['dumps']
    counts = df.groupby('_dump_id').size().to_dict()
    assert {d['_dump_id']: d['count'] for d in api_dumps} == counts
    report = {'time': datetime.now(timezone.utc).isoformat(), 'records': len(df), 'timelines': timelines,
              'dump_counts': counts, 'static_runtime_all_filter_values_match': True, 'checks': []}
    historical = [d for d in api_dumps if d['_timeline'] in ('Nov 2025', 'Feb 2026')]
    assert len(historical) == 2
    for dump in historical:
        ids = [dump['_dump_id']]
        sample = df[df['_dump_id'].isin(ids)]
        cases = [{}]
        for key, field in FILTER_REGISTRY.items():
            values = sample[field.column].dropna()
            if not values.empty:
                cases.append({key: str(values.value_counts().index[0])})
        row = sample.dropna(subset=['company', '_sector_norm']).iloc[0]
        cases += [{'company': str(row['company']), 'sector': str(row['_sector_norm'])}, {'company': '__no_such_company__'}]
        for filters in cases:
            n = len(_scope_base(df, ids, filters))
            dashboard = requests.get(args.base_url + '/api/dashboard', params={'dumps': ids[0], **filters}, timeout=30).json()
            assert dashboard.get('total', 0) == n, (ids, filters, n, dashboard.get('total'))
            answer, info, seconds = chat(args.base_url, ids, filters, 'How many total job postings are in the selected datasets?')
            assert info.get('evidence_count') == n, (ids, filters, n, info)
            report['checks'].append({'dump': ids[0], 'filters': filters, 'count': n, 'chat_seconds': seconds})
            print(f'PASS {ids[0]} {filters}: dashboard/chat={n}', flush=True)
    for payload, code in [({'dump_ids': []}, 400), ({'dump_ids': ['unknown_dump']}, 400),
                          ({'dump_ids': [historical[0]['_dump_id']], 'filters': {'typo_sector': 'Technology'}}, 422)]:
        response = requests.post(args.base_url + '/api/chat', json={
            'question': 'How many jobs?', 'session_id': 'verify-invalid', **payload,
        }, timeout=30)
        assert response.status_code == code, response.text
    if args.vectors:
        from vector_store import _QdrantREST, _build_metadata, _make_row_id, _str_to_uuid, QDRANT_COLLECTION
        import os
        client = _QdrantREST(os.environ['QDRANT_URL'], os.environ['QDRANT_API_KEY'])
        wanted = {_str_to_uuid(_make_row_id(row, i)): _build_metadata(row) for i, (_, row) in enumerate(df.iterrows())}
        actual_ids, offset, mismatches = set(), None, []
        while True:
            body = {'limit': 1000, 'with_payload': list(next(iter(wanted.values())).keys()), 'with_vector': False}
            # All registry fields must be requested, including ones missing in the first row.
            body['with_payload'] = sorted(set(body['with_payload']) | {field.column for field in FILTER_REGISTRY.values()})
            if offset is not None:
                body['offset'] = offset
            response = client._s.post(client._base + f'/collections/{QDRANT_COLLECTION}/points/scroll', json=body, timeout=60)
            response.raise_for_status()
            page = response.json()['result']
            for point in page['points']:
                actual_ids.add(point['id'])
                metadata = wanted.get(point['id'])
                if metadata is None:
                    continue
                for key in ['_dump_id', '_source', '_country', '_timeline'] + [field.column for field in FILTER_REGISTRY.values()]:
                    if clean(point['payload'].get(key)) != clean(metadata.get(key)):
                        mismatches.append({'id': point['id'], 'field': key})
            offset = page.get('next_page_offset')
            if offset is None:
                break
        assert actual_ids == set(wanted), f'Qdrant missing={len(set(wanted)-actual_ids)}, stale={len(actual_ids-set(wanted))}'
        assert not mismatches, f'Qdrant payload mismatch: {mismatches[:10]} (total {len(mismatches)})'
        report['qdrant'] = {'verified_point_ids': len(actual_ids), 'all_filter_payloads_match': True}
        print(f'PASS Qdrant: all {len(actual_ids)} IDs and filter payloads match runtime', flush=True)
    if args.semantic:
        for dump in historical:
            ids = [dump['_dump_id']]
            sample = df[df['_dump_id'].isin(ids)]
            company = str(sample['company'].value_counts().index[0])
            answer, info, seconds = chat(args.base_url, ids, {'company': company},
                                        'Describe the responsibilities and qualifications mentioned by employers in these postings, using examples from the descriptions.')
            hits = info.get('semantic_hits', [])
            assert hits, (dump['_timeline'], info)
            assert all(hit['company'] == company and hit['timeline'] == dump['_timeline'] and hit['country'] == dump['_country'] for hit in hits), hits
            assert info.get('mode') != 'deterministic', info
            report['checks'].append({'semantic_dump': ids[0], 'company': company, 'evidence_hits': len(hits), 'seconds': seconds, 'mode': info.get('mode')})
            print(f'PASS semantic RAG {ids[0]}: {len(hits)} scoped evidence hits; {seconds}s', flush=True)
    output = Path(__file__).parent / 'reports' / ('dataset_alignment_full.json' if args.vectors else 'dataset_alignment_structured.json')
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'PASS: report saved to {output}', flush=True)


if __name__ == '__main__':
    main()
