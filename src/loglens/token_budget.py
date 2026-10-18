"""Lossless row compaction with full local evidence retained for audit."""
import json
from pathlib import Path
from uuid import uuid4


def compact_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def compact_evidence(value):
    if isinstance(value, list):
        return [compact_evidence(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {k: compact_evidence(v) for k, v in value.items()}
    rows = value.get('rows')
    if rows and all(isinstance(row, dict) for row in rows):
        columns = list(dict.fromkeys(key for row in rows for key in row))
        # Only encode rectangular rows: missing values must not become null silently.
        if all(set(row) == set(columns) for row in rows):
            result['rows'] = {'columns': columns, 'values': [[row[k] for k in columns] for row in rows]}
    return result


def prepare_evidence(payload, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    reference = uuid4().hex
    (directory / (reference + '.json')).write_text(compact_json(payload), encoding='utf-8')
    compact = compact_evidence(payload)
    def remove_sql(value):
        if isinstance(value, dict):
            if 'evidence_id' in value and 'query' in value:
                value.pop('query', None)
                value.pop('parameters', None)
            for child in value.values():
                remove_sql(child)
        elif isinstance(value, list):
            for child in value:
                remove_sql(child)
    # The model needs rows and references; the audit file retains the executable SQL.
    remove_sql(compact)
    return {'evidence': compact, 'local_audit_file': str(directory / (reference + '.json'))}


def report_usage(response):
    usage = getattr(response, 'usage', None)
    if usage is not None:
        import sys
        values = usage.model_dump(exclude_none=True)
        counts = {k: v for k, v in values.items() if k in
                  ('prompt_tokens', 'completion_tokens', 'input_tokens', 'output_tokens', 'total_tokens')}
        print('[tokens] ' + compact_json(counts), file=sys.stderr)
