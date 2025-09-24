from sqlite3 import connect
from datetime import datetime


def init_db(db_path='db/metrics.db'):
    conn = connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            container TEXT,
            cpu_percent REAL,
            mem_usage REAL,
            mem_limit REAL,
            mem_percent REAL,
            rx_bytes REAL,
            tx_bytes REAL,
            io_read REAL,
            io_write REAL,
            restarts INTEGER
        )
    """)
    conn.commit()
    return conn

def insert_metrics(conn, metrics_list):
    cursor = conn.cursor()
    timestamp = datetime.now().isoformat()
    for m in metrics_list:
        cursor.execute('''
            INSERT INTO metrics (timestamp, container, cpu_percent, mem_usage, mem_limit, mem_percent, rx_bytes, tx_bytes, io_read, io_write, restarts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (timestamp, m['container'], m['cpu_percent'], m['mem_usage'], m['mem_limit'], m['mem_percent'], m['rx_bytes'], m['tx_bytes'], m['io_read'], m['io_write'], m['restarts']))
    conn.commit()
