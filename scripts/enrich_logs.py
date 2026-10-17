import argparse
import csv
import re
import psycopg
from loglens.config import Settings


def template(message):
    text = re.sub(r"\b[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}\b", "<UUID>", message)
    text = re.sub(r"\b0x[0-9a-fA-F]+\b", "<HEX>", text)
    return re.sub(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?\b", "<TIME>", text)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ownership', help='CSV with dataset,component,team columns')
    p.add_argument('--templates', choices=['bgl', 'openstack'])
    p.add_argument('--limit', type=int, default=10000, help='Maximum missing templates to fill per run')
    a = p.parse_args()
    if not a.ownership and not a.templates:
        p.error('Choose --ownership or --templates')
    if not 1 <= a.limit <= 100000:
        p.error('--limit must be 1..100000')
    with psycopg.connect(Settings.from_env().dsn) as c:
        if a.ownership:
            with open(a.ownership, newline='', encoding='utf-8-sig') as f:
                rows = list(csv.DictReader(f))
            for r in rows:
                if r.get('dataset') not in ('bgl', 'openstack') or not r.get('component', '').strip() or not r.get('team', '').strip():
                    raise ValueError('Each ownership row needs dataset bgl/openstack, component and real team')
            with c.cursor() as cur:
                cur.executemany('INSERT INTO component_ownership(dataset,component,team) VALUES (%s,%s,%s) ON CONFLICT(dataset,component) DO UPDATE SET team=EXCLUDED.team', [(r['dataset'],r['component'],r['team']) for r in rows])
            print('Imported ownership rows:', len(rows))
        if a.templates:
            table = a.templates + '_logs'
            rows = c.execute('SELECT event_id,message FROM '+table+' WHERE event_template IS NULL ORDER BY event_id LIMIT %s', (a.limit,)).fetchall()
            with c.cursor() as cur:
                cur.executemany('UPDATE '+table+' SET event_template=%s WHERE event_id=%s', [('heuristic: '+template(m), eid) for eid,m in rows])
            print('Filled heuristic templates:', len(rows))
    if a.templates:
        with psycopg.connect(Settings.from_env().dsn, autocommit=True) as c:
            c.execute('VACUUM (REFRESH_TABLE) '+a.templates+'_logs')

if __name__ == '__main__':
    main()
