from pathlib import Path
import sqlite3
import hashlib
import xdg

directory = Path(xdg.BaseDirectory.xdg_cache_home) / 'getnear'
directory.mkdir(exist_ok=True)
db = sqlite3.connect(directory / 'checkpoint.sqlite')
db.execute('''
    create table if not exists checkpoint(
        key text,
        cksum text,
        time default current_timestamp
    )
    ''')

def cksum(value):
    return hashlib.sha1(repr(value).encode()).hexdigest()

def is_unchanged(key, value):
    cur = db.execute('''
        select cksum, time from checkpoint
        where key = ? order by time desc limit 1
        ''', [key])
    row = cur.fetchone()
    if not row:
        return
    last_cksum, time = row
    if cksum(value) == last_cksum:
        return time

def update(key, value):
    db.execute(
            'insert into checkpoint(key, cksum) values (?, ?)',
            [key, cksum(value)])
    db.commit()
