
import queue
import re
import threading
from decimal import Decimal

import pymssql

from ask_ai.config import (
    DW_SERVER, DW_PORT, DW_USER, DW_PASSWORD, DW_DATABASE,
    POOL_SIZE, QUERY_TIMEOUT, LOGIN_TIMEOUT, LOCK_TIMEOUT_MS, MAX_RESULT_ROWS,
)


_PERMANENT = re.compile(r'invalid (column|object) name|\b20[78]\b', re.IGNORECASE)


class QueryError(Exception):
    """A query the server refused. Carries the message the model needs to fix it."""

    def __init__(self, message, permanent=False):
        super().__init__(message)
        self.permanent = permanent


class _Pool:
    """Fixed-size connection pool."""

    def __init__(self, size):
        self._idle = queue.LifoQueue(maxsize=size)
        self._lock = threading.Lock()
        self._created = 0
        self._size = size

    def _connect(self):
        if not DW_PASSWORD:
            raise QueryError(
                'DW_PASSWORD is not set. Copy .env.example to .env and fill in the '
                'DW_* credentials.'
            )
        conn = pymssql.connect(
            server=DW_SERVER,
            port=DW_PORT,
            user=DW_USER,
            password=DW_PASSWORD,
            database=DW_DATABASE,
            timeout=QUERY_TIMEOUT,
            login_timeout=LOGIN_TIMEOUT,
            as_dict=False,
        )
        cur = conn.cursor()
        # Read uncommitted so an analytical scan never blocks a production writer.
        cur.execute(
            f'SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED; '
            f'SET LOCK_TIMEOUT {LOCK_TIMEOUT_MS};'
        )
        cur.close()
        return conn

    def acquire(self):
        try:
            return self._idle.get_nowait()
        except queue.Empty:
            pass
        with self._lock:
            if self._created < self._size:
                self._created += 1
                grow = True
            else:
                grow = False
        if grow:
            try:
                return self._connect()
            except Exception:
                with self._lock:
                    self._created -= 1
                raise
        try:
            return self._idle.get(timeout=QUERY_TIMEOUT)
        except queue.Empty:
            raise QueryError(
                f'All {self._size} warehouse connections are busy. '
                'Try again, or raise ASK_AI_POOL_SIZE.'
            )

    def release(self, conn):
        try:
            self._idle.put_nowait(conn)
        except queue.Full:
            self.discard(conn)

    def discard(self, conn):
        try:
            conn.close()
        except Exception:
            pass
        with self._lock:
            self._created -= 1

    def stats(self):
        return {'created': self._created, 'idle': self._idle.qsize(), 'size': self._size}


_pool = _Pool(POOL_SIZE)


def pool_stats():
    return _pool.stats()


def _execute(sql, params=None):
    """Run one statement on a pooled connection and return (columns, raw_rows)."""
    conn = _pool.acquire()
    reusable = False
    try:
        cur = conn.cursor()
        failure = None
        columns, rows = [], []
        try:
            cur.execute('BEGIN TRANSACTION;')
            if params:
                cur.execute(sql, params)
            else:
                cur.execute(sql)
            columns = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchall() if columns else []
        except pymssql.Error as e:
            failure = e

        # Unwinding also proves the socket is alive — a bad column costs a retry, not a reconnect.
        try:
            cur.execute('IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;')
            reusable = True
        except pymssql.Error:
            reusable = False
        try:
            cur.close()
        except pymssql.Error:
            reusable = False

        if failure is not None:
            raise QueryError(
                _clean_error(failure),
                permanent=_PERMANENT.search(str(failure)) is not None,
            )
        return columns, rows
    except pymssql.Error as e:
        raise QueryError(_clean_error(e))
    finally:
        # A timed-out connection is dead — never hand it to the next request.
        _pool.release(conn) if reusable else _pool.discard(conn)


def _clean_error(e):
    """pymssql raises (code, b'message...DB-Lib error message 20018...')."""
    raw = e.args[-1] if e.args else e
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8', 'replace')
    text = str(raw).split('DB-Lib error')[0]
    return ' '.join(text.strip().strip('"\' ').split())[:300]


def validate_sql(sql):
    """Dry-run the query. Returns (ok, error, columns) without executing it."""
    try:
        _, rows = _execute('EXEC sp_describe_first_result_set @tsql = %s', (sql,))
    except QueryError as e:
        return False, _parse_error(sql) or str(e), []
    # name is the 3rd column of sp_describe_first_result_set's result set.
    return True, None, [r[2] for r in rows]


def _parse_error(sql):
    """sp_describe_first_result_set reports syntax problems as a useless "batch could not be analyzed"."""
    try:
        _execute(f'IF 1 = 0 BEGIN\n{sql}\nEND')
    except QueryError as e:
        return str(e)
    return None


def run_sql(sql, max_rows=MAX_RESULT_ROWS):
    columns, raw = _execute(sql)
    truncated = len(raw) > max_rows
    rows = [dict(zip(columns, _coerce(r))) for r in raw[:max_rows]]
    return columns, rows, truncated


def query(sql, params=None):
    """Parameterized read for the module's own hand-written SQL (member analysis)."""
    columns, raw = _execute(sql, params)
    return [dict(zip(columns, _coerce(r))) for r in raw]


def _coerce(row):
    """Decimal is not JSON-serializable and pandas/JS both want floats."""
    return [float(v) if isinstance(v, Decimal) else v for v in row]
