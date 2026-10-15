import json
import sqlite3
import time
from .config import DATA

def connect():
    db=sqlite3.connect(DATA/'jobs.sqlite3',timeout=20)
    db.row_factory=sqlite3.Row
    return db

def initialize():
    with connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, payload TEXT NOT NULL, created REAL NOT NULL)')
        for row in db.execute('SELECT * FROM jobs').fetchall():
            job=json.loads(row['payload'])
            if job['status'] in ('queued','running'):
                job.update(status='error',stage='중단됨',error='서버가 재시작되어 작업이 중단되었습니다. 완료된 페이지는 보존됩니다. 다시 요청해 주세요.')
                db.execute('UPDATE jobs SET payload=? WHERE id=?',(json.dumps(job,ensure_ascii=False),row['id']))

def save(job):
    with connect() as db:
        db.execute('INSERT INTO jobs VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',(job['id'],json.dumps(job,ensure_ascii=False),job['created']))

def get(job_id):
    with connect() as db:
        row=db.execute('SELECT payload FROM jobs WHERE id=?',(job_id,)).fetchone()
    return json.loads(row['payload']) if row else None

def recent():
    with connect() as db:
        return [json.loads(row[0]) for row in db.execute('SELECT payload FROM jobs ORDER BY created DESC LIMIT 30')]
