"""
database.py — Unified Database Layer
Supports Supabase PostgreSQL (via DATABASE_URL) with fallback to SQLite.
"""
import os
import json
import sqlite3
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# Check if using PostgreSQL (Supabase)
USE_POSTGRES = bool(DATABASE_URL and DATABASE_URL.startswith("postgres"))

if USE_POSTGRES:
    import psycopg2
    from psycopg2.extras import RealDictCursor


def _get_clean_pg_url(url: str) -> str:
    """Ensure postgresql url has sslmode and proper format."""
    clean = url.replace("postgres://", "postgresql://")
    if "sslmode=" not in clean:
        clean += "?sslmode=require" if "?" not in clean else "&sslmode=require"
    return clean


def get_db():
    if USE_POSTGRES:
        conn = psycopg2.connect(_get_clean_pg_url(DATABASE_URL), cursor_factory=RealDictCursor)
        return conn
    else:
        conn = sqlite3.connect("reviews.db")
        conn.row_factory = sqlite3.Row
        return conn


def init_db():
    """Initializes tables on startup."""
    conn = get_db()
    cur = conn.cursor()

    if USE_POSTGRES:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS shops (
                id                SERIAL PRIMARY KEY,
                card_id           TEXT UNIQUE NOT NULL,
                place_id          TEXT NOT NULL,
                shop_name         TEXT NOT NULL,
                shop_type         TEXT NOT NULL,
                description       TEXT,
                keywords          TEXT DEFAULT '[]',
                google_review_url TEXT NOT NULL,
                is_active         BOOLEAN DEFAULT TRUE,
                created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("ALTER TABLE shops ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id          SERIAL PRIMARY KEY,
                shop_id     INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
                content     TEXT NOT NULL,
                aspect      TEXT DEFAULT 'general',
                language    TEXT DEFAULT 'en',
                source      TEXT DEFAULT 'ai',
                used        BOOLEAN DEFAULT FALSE,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("ALTER TABLE reviews ADD COLUMN IF NOT EXISTS used BOOLEAN DEFAULT FALSE;")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS scans (
                id          SERIAL PRIMARY KEY,
                shop_id     INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
                scanned_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip          TEXT,
                user_agent  TEXT
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_scans_shop_id ON scans(shop_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_scans_scanned_at ON scans(scanned_at);")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS error_logs (
                id          SERIAL PRIMARY KEY,
                endpoint    TEXT,
                error_type  TEXT,
                message     TEXT,
                traceback   TEXT,
                is_read     BOOLEAN DEFAULT FALSE,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_error_logs_created_at ON error_logs(created_at);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_error_logs_is_read ON error_logs(is_read);")
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS shops (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id     TEXT UNIQUE NOT NULL,
                place_id    TEXT NOT NULL,
                shop_name   TEXT NOT NULL,
                shop_type   TEXT NOT NULL,
                description TEXT,
                keywords    TEXT DEFAULT '[]',
                google_review_url TEXT NOT NULL,
                is_active   BOOLEAN DEFAULT 1,
                created_at  TEXT DEFAULT (datetime('now'))
            );
        """)
        try:
            cur.execute("ALTER TABLE shops ADD COLUMN is_active BOOLEAN DEFAULT 1;")
        except Exception:
            pass
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                shop_id     INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
                content     TEXT NOT NULL,
                aspect      TEXT DEFAULT 'general',
                language    TEXT DEFAULT 'en',
                source      TEXT DEFAULT 'ai',
                used        BOOLEAN DEFAULT 0,
                created_at  TEXT DEFAULT (datetime('now'))
            );
        """)
        try:
            cur.execute("ALTER TABLE reviews ADD COLUMN used BOOLEAN DEFAULT 0;")
        except Exception:
            pass
        cur.execute("""
            CREATE TABLE IF NOT EXISTS scans (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                shop_id     INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
                scanned_at  TEXT DEFAULT (datetime('now')),
                ip          TEXT,
                user_agent  TEXT
            );
        """)
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_scans_shop_id ON scans(shop_id);")
        except Exception:
            pass
        cur.execute("""
            CREATE TABLE IF NOT EXISTS error_logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint    TEXT,
                error_type  TEXT,
                message     TEXT,
                traceback   TEXT,
                is_read     BOOLEAN DEFAULT 0,
                created_at  TEXT DEFAULT (datetime('now'))
            );
        """)
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_error_logs_created_at ON error_logs(created_at);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_error_logs_is_read ON error_logs(is_read);")
        except Exception:
            pass

    conn.commit()
    conn.close()
    backend_name = "Supabase PostgreSQL" if USE_POSTGRES else "Local SQLite"
    print(f"[DB] Initialized successfully using {backend_name}")


# ── Shop operations ──────────────────────────────────────────

def create_shop(card_id, place_id, shop_name, shop_type, description, keywords, google_review_url):
    conn = get_db()
    cur = conn.cursor()
    kw_json = json.dumps(keywords) if isinstance(keywords, list) else str(keywords)

    try:
        if USE_POSTGRES:
            cur.execute("""
                INSERT INTO shops (card_id, place_id, shop_name, shop_type, description, keywords, google_review_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (card_id, place_id, shop_name, shop_type, description, kw_json, google_review_url))
        else:
            cur.execute("""
                INSERT INTO shops (card_id, place_id, shop_name, shop_type, description, keywords, google_review_url)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (card_id, place_id, shop_name, shop_type, description, kw_json, google_review_url))

        conn.commit()
        return True, "Card created successfully"
    except Exception as e:
        conn.rollback()
        err_str = str(e).lower()
        if "unique" in err_str or "duplicate" in err_str:
            return False, "Card ID already exists"
        return False, f"Database error: {e}"
    finally:
        conn.close()


def _format_shop_row(row):
    if not row:
        return None
    shop = dict(row)
    if isinstance(shop.get("keywords"), str):
        try:
            shop["keywords"] = json.loads(shop["keywords"])
        except Exception:
            shop["keywords"] = []
    elif shop.get("keywords") is None:
        shop["keywords"] = []

    # Ensure is_active is boolean (defaults to True)
    shop["is_active"] = True if shop.get("is_active") is None else bool(shop.get("is_active"))

    # Ensure created_at is string formatted for JSON serialization
    if shop.get("created_at") and not isinstance(shop["created_at"], str):
        shop["created_at"] = str(shop["created_at"])
    return shop


def record_scan(shop_id: int, ip: str = None, user_agent: str = None):
    """Logs an NFC card scan / visit event."""
    try:
        conn = get_db()
        cur = conn.cursor()
        if USE_POSTGRES:
            cur.execute("""
                INSERT INTO scans (shop_id, ip, user_agent)
                VALUES (%s, %s, %s)
            """, (shop_id, ip, user_agent))
        else:
            cur.execute("""
                INSERT INTO scans (shop_id, ip, user_agent)
                VALUES (?, ?, ?)
            """, (shop_id, ip, user_agent))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB] Error recording scan for shop {shop_id}: {e}")


def get_shop_scan_stats(shop_id: int) -> dict:
    """Returns today, this month, this year, and total scan counts."""
    try:
        conn = get_db()
        cur = conn.cursor()
        if USE_POSTGRES:
            cur.execute("""
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE scanned_at >= CURRENT_DATE) AS today,
                    COUNT(*) FILTER (WHERE scanned_at >= DATE_TRUNC('month', CURRENT_DATE)) AS month,
                    COUNT(*) FILTER (WHERE scanned_at >= DATE_TRUNC('year', CURRENT_DATE)) AS year
                FROM scans
                WHERE shop_id = %s
            """, (shop_id,))
        else:
            cur.execute("""
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN date(scanned_at) = date('now') THEN 1 ELSE 0 END) AS today,
                    SUM(CASE WHEN strftime('%Y-%m', scanned_at) = strftime('%Y-%m', 'now') THEN 1 ELSE 0 END) AS month,
                    SUM(CASE WHEN strftime('%Y', scanned_at) = strftime('%Y', 'now') THEN 1 ELSE 0 END) AS year
                FROM scans
                WHERE shop_id = ?
            """, (shop_id,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return {"today": 0, "month": 0, "year": 0, "total": 0}
        r = dict(row)
        return {
            "today": int(r.get("today") or 0),
            "month": int(r.get("month") or 0),
            "year": int(r.get("year") or 0),
            "total": int(r.get("total") or 0),
        }
    except Exception as e:
        print(f"[DB] Error getting scan stats: {e}")
        return {"today": 0, "month": 0, "year": 0, "total": 0}


def toggle_shop_status(card_id: str, is_active: bool = None) -> bool | None:
    """Toggles or sets the active/service status of a card."""
    conn = get_db()
    cur = conn.cursor()
    if is_active is None:
        q_find = "SELECT is_active FROM shops WHERE card_id = %s" if USE_POSTGRES else "SELECT is_active FROM shops WHERE card_id = ?"
        cur.execute(q_find, (card_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return None
        current = row["is_active"] if isinstance(row, dict) else row[0]
        new_status = not bool(current if current is not None else True)
    else:
        new_status = bool(is_active)

    if USE_POSTGRES:
        cur.execute("UPDATE shops SET is_active = %s WHERE card_id = %s", (new_status, card_id))
    else:
        cur.execute("UPDATE shops SET is_active = ? WHERE card_id = ?", (1 if new_status else 0, card_id))

    conn.commit()
    conn.close()
    return new_status


def get_shop_by_card_id(card_id):
    conn = get_db()
    cur = conn.cursor()
    query = "SELECT * FROM shops WHERE card_id = %s" if USE_POSTGRES else "SELECT * FROM shops WHERE card_id = ?"
    cur.execute(query, (card_id,))
    row = cur.fetchone()
    conn.close()
    return _format_shop_row(row)


def get_shop_by_id(shop_id):
    conn = get_db()
    cur = conn.cursor()
    query = "SELECT * FROM shops WHERE id = %s" if USE_POSTGRES else "SELECT * FROM shops WHERE id = ?"
    cur.execute(query, (shop_id,))
    row = cur.fetchone()
    conn.close()
    return _format_shop_row(row)


def get_all_shops():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM shops ORDER BY created_at DESC")
    rows = cur.fetchall()
    conn.close()
    shops = []
    for r in rows:
        shop = _format_shop_row(r)
        if shop:
            shop["scan_stats"] = get_shop_scan_stats(shop["id"])
            shops.append(shop)
    return shops


def update_shop(card_id, shop_name, shop_type, description, keywords):
    conn = get_db()
    cur = conn.cursor()
    kw_json = json.dumps(keywords) if isinstance(keywords, list) else str(keywords)

    if USE_POSTGRES:
        cur.execute("""
            UPDATE shops SET shop_name=%s, shop_type=%s, description=%s, keywords=%s
            WHERE card_id=%s
        """, (shop_name, shop_type, description, kw_json, card_id))
    else:
        cur.execute("""
            UPDATE shops SET shop_name=?, shop_type=?, description=?, keywords=?
            WHERE card_id=?
        """, (shop_name, shop_type, description, kw_json, card_id))

    conn.commit()
    conn.close()


def delete_shop(card_id):
    conn = get_db()
    cur = conn.cursor()
    q_find = "SELECT id FROM shops WHERE card_id = %s" if USE_POSTGRES else "SELECT id FROM shops WHERE card_id = ?"
    cur.execute(q_find, (card_id,))
    shop = cur.fetchone()
    if shop:
        shop_id = shop["id"] if isinstance(shop, dict) else shop[0]
        q_del_rev = "DELETE FROM reviews WHERE shop_id = %s" if USE_POSTGRES else "DELETE FROM reviews WHERE shop_id = ?"
        cur.execute(q_del_rev, (shop_id,))
        q_del_shop = "DELETE FROM shops WHERE card_id = %s" if USE_POSTGRES else "DELETE FROM shops WHERE card_id = ?"
        cur.execute(q_del_shop, (card_id,))
        conn.commit()
    conn.close()


# ── Review operations ─────────────────────────────────────────

def save_reviews(shop_id, reviews_list):
    """Save initial batch of reviews (wipe old, insert new with used=False)."""
    conn = get_db()
    cur = conn.cursor()

    q_del = "DELETE FROM reviews WHERE shop_id = %s" if USE_POSTGRES else "DELETE FROM reviews WHERE shop_id = ?"
    cur.execute(q_del, (shop_id,))

    for r in reviews_list:
        content = r if isinstance(r, str) else r.get("content", "")
        aspect = r.get("aspect", "general") if isinstance(r, dict) else "general"
        lang = r.get("language", "en") if isinstance(r, dict) else "en"
        if not content:
            continue
        if USE_POSTGRES:
            cur.execute("""
                INSERT INTO reviews (shop_id, content, aspect, language, source, used)
                VALUES (%s, %s, %s, %s, 'ai', FALSE)
            """, (shop_id, content, aspect, lang))
        else:
            cur.execute("""
                INSERT INTO reviews (shop_id, content, aspect, language, source, used)
                VALUES (?, ?, ?, ?, 'ai', 0)
            """, (shop_id, content, aspect, lang))

    conn.commit()
    conn.close()


def append_reviews(shop_id, reviews_list):
    """Append newly generated batch of reviews to DB with used=False."""
    conn = get_db()
    cur = conn.cursor()

    for r in reviews_list:
        content = r if isinstance(r, str) else r.get("content", "")
        aspect = r.get("aspect", "general") if isinstance(r, dict) else "general"
        lang = r.get("language", "en") if isinstance(r, dict) else "en"
        if not content:
            continue
        if USE_POSTGRES:
            cur.execute("""
                INSERT INTO reviews (shop_id, content, aspect, language, source, used)
                VALUES (%s, %s, %s, %s, 'ai', FALSE)
            """, (shop_id, content, aspect, lang))
        else:
            cur.execute("""
                INSERT INTO reviews (shop_id, content, aspect, language, source, used)
                VALUES (?, ?, ?, ?, 'ai', 0)
            """, (shop_id, content, aspect, lang))

    conn.commit()
    conn.close()


def get_random_unused_reviews(shop_id, limit=5):
    """
    Returns random unused reviews directly from DB (no AI call on scan!).
    If fewer than limit unused exist, backfills with any available reviews.
    """
    conn = get_db()
    cur = conn.cursor()

    if USE_POSTGRES:
        cur.execute("""
            SELECT * FROM reviews
            WHERE shop_id = %s AND (used IS FALSE OR used IS NULL)
            ORDER BY RANDOM() LIMIT %s
        """, (shop_id, limit))
    else:
        cur.execute("""
            SELECT * FROM reviews
            WHERE shop_id = ? AND (used = 0 OR used IS NULL)
            ORDER BY RANDOM() LIMIT ?
        """, (shop_id, limit))

    rows = cur.fetchall()

    # If fewer than limit, backfill from all reviews
    if len(rows) < limit:
        needed = limit - len(rows)
        existing_ids = [r["id"] if isinstance(r, dict) else r[0] for r in rows]
        if existing_ids:
            if USE_POSTGRES:
                cur.execute("""
                    SELECT * FROM reviews
                    WHERE shop_id = %s AND id NOT IN %s
                    ORDER BY RANDOM() LIMIT %s
                """, (shop_id, tuple(existing_ids), needed))
            else:
                placeholders = ",".join(["?"] * len(existing_ids))
                cur.execute(f"""
                    SELECT * FROM reviews
                    WHERE shop_id = ? AND id NOT IN ({placeholders})
                    ORDER BY RANDOM() LIMIT ?
                """, (shop_id, *existing_ids, needed))
            more = cur.fetchall()
            rows.extend(more)

    conn.close()
    results = []
    for r in rows:
        item = dict(r)
        if item.get("created_at") and not isinstance(item["created_at"], str):
            item["created_at"] = str(item["created_at"])
        results.append(item)
    return results


def mark_review_used(review_id, shop_id=None):
    """
    Marks a review as used when clicked/posted to Google.
    If 10 reviews have been used (or unused pool is low), removes the used 10 and signals replenish!
    """
    conn = get_db()
    cur = conn.cursor()

    if not shop_id:
        q_find = "SELECT shop_id FROM reviews WHERE id = %s" if USE_POSTGRES else "SELECT shop_id FROM reviews WHERE id = ?"
        cur.execute(q_find, (review_id,))
        r = cur.fetchone()
        if r:
            shop_id = r["shop_id"] if isinstance(r, dict) else r[0]

    if not shop_id:
        conn.close()
        return {"should_replenish": False, "used_count": 0, "unused_count": 0, "shop_id": None}

    if USE_POSTGRES:
        cur.execute("UPDATE reviews SET used = TRUE WHERE id = %s", (review_id,))
        cur.execute("SELECT COUNT(*) FROM reviews WHERE shop_id = %s AND used = TRUE", (shop_id,))
        used_row = cur.fetchone()
        cur.execute("SELECT COUNT(*) FROM reviews WHERE shop_id = %s AND (used IS FALSE OR used IS NULL)", (shop_id,))
        unused_row = cur.fetchone()
    else:
        cur.execute("UPDATE reviews SET used = 1 WHERE id = ?", (review_id,))
        cur.execute("SELECT COUNT(*) FROM reviews WHERE shop_id = ? AND used = 1", (shop_id,))
        used_row = cur.fetchone()
        cur.execute("SELECT COUNT(*) FROM reviews WHERE shop_id = ? AND (used = 0 OR used IS NULL)", (shop_id,))
        unused_row = cur.fetchone()

    used_count = used_row["count"] if isinstance(used_row, dict) and "count" in used_row else (used_row[0] if used_row else 0)
    unused_count = unused_row["count"] if isinstance(unused_row, dict) and "count" in unused_row else (unused_row[0] if unused_row else 0)

    should_replenish = False
    # When 10 reviews have been used (or unused count drops below 3), remove the used reviews and replenish!
    if used_count >= 10 or (used_count > 0 and unused_count < 3):
        if USE_POSTGRES:
            cur.execute("DELETE FROM reviews WHERE shop_id = %s AND used = TRUE", (shop_id,))
        else:
            cur.execute("DELETE FROM reviews WHERE shop_id = ? AND used = 1", (shop_id,))
        should_replenish = True

    conn.commit()
    conn.close()

    return {
        "should_replenish": should_replenish,
        "used_count": used_count,
        "unused_count": unused_count,
        "shop_id": shop_id
    }


def has_reviews(shop_id):
    conn = get_db()
    cur = conn.cursor()
    q = "SELECT COUNT(*) FROM reviews WHERE shop_id = %s" if USE_POSTGRES else "SELECT COUNT(*) FROM reviews WHERE shop_id = ?"
    cur.execute(q, (shop_id,))
    row = cur.fetchone()
    conn.close()
    count = row["count"] if isinstance(row, dict) and "count" in row else (row[0] if row else 0)
    return count > 0


# ── System Error Logging ──────────────────────────────────────

def log_error(endpoint: str, error_type: str, message: str, traceback_str: str = ""):
    """Safely log an application or AI system error."""
    try:
        conn = get_db()
        cur = conn.cursor()
        if USE_POSTGRES:
            cur.execute("""
                INSERT INTO error_logs (endpoint, error_type, message, traceback, is_read)
                VALUES (%s, %s, %s, %s, FALSE)
            """, (endpoint, error_type, message, traceback_str))
        else:
            cur.execute("""
                INSERT INTO error_logs (endpoint, error_type, message, traceback, is_read)
                VALUES (?, ?, ?, ?, 0)
            """, (endpoint, error_type, message, traceback_str))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB Error Logging Failed] {e}")


def get_errors(limit: int = 50):
    """Retrieve recent error logs and unread count."""
    try:
        conn = get_db()
        cur = conn.cursor()

        # Count unread errors
        count_q = "SELECT COUNT(*) FROM error_logs WHERE is_read IS FALSE" if USE_POSTGRES else "SELECT COUNT(*) FROM error_logs WHERE is_read = 0"
        cur.execute(count_q)
        cnt_row = cur.fetchone()
        unread_count = cnt_row["count"] if isinstance(cnt_row, dict) and "count" in cnt_row else (cnt_row[0] if cnt_row else 0)

        # Fetch logs
        select_q = f"""
            SELECT id, endpoint, error_type, message, traceback, is_read, created_at
            FROM error_logs
            ORDER BY id DESC
            LIMIT {limit}
        """
        cur.execute(select_q)
        rows = cur.fetchall()
        conn.close()

        errors = []
        for r in rows:
            errors.append({
                "id": r["id"],
                "endpoint": r["endpoint"],
                "error_type": r["error_type"],
                "message": r["message"],
                "traceback": r["traceback"],
                "is_read": bool(r["is_read"]),
                "created_at": str(r["created_at"])
            })

        return {"errors": errors, "unread_count": unread_count}
    except Exception as e:
        print(f"[DB get_errors Error] {e}")
        return {"errors": [], "unread_count": 0}


def mark_all_errors_read():
    """Mark all error logs as read."""
    try:
        conn = get_db()
        cur = conn.cursor()
        q = "UPDATE error_logs SET is_read = TRUE WHERE is_read IS FALSE" if USE_POSTGRES else "UPDATE error_logs SET is_read = 1 WHERE is_read = 0"
        cur.execute(q)
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB mark_all_errors_read Error] {e}")
        return False


def clear_all_errors():
    """Delete all error logs."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM error_logs")
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB clear_all_errors Error] {e}")
        return False


