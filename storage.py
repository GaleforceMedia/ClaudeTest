"""
Persistence layer for the KEP portal.

Everything that needs to survive a restart goes through here. Two tables:

  campaigns  - one row per campaign, with a share_token used for the
               read-only client tracking link
  shipments  - one row per consignment, accumulated from DHL exports.
               This is the history that makes the Insights page possible.

Uses stdlib sqlite3 so there are no extra dependencies and it works out
of the box. See "Moving to Postgres" at the bottom of this file when you
outgrow it - the swap is contained to get_conn() and the placeholder
style, not spread through the pages.

IMPORTANT: on Streamlit Community Cloud the SQLite file lives on an
ephemeral disk and is wiped on redeploy, exactly like the old CSVs.
Point KEP_DB_PATH at a mounted volume, or move to Postgres, before you
rely on this for real data. See README.md > Hosting.
"""
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

DB_PATH = os.environ.get("KEP_DB_PATH", "kep_portal.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS campaigns (
    id            TEXT PRIMARY KEY,
    client        TEXT NOT NULL,
    name          TEXT NOT NULL,
    am            TEXT,
    dispatch_date TEXT,
    stores        INTEGER DEFAULT 0,
    collation_hrs REAL    DEFAULT 0,
    status        TEXT,
    notes         TEXT,
    share_token   TEXT UNIQUE,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shipments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id     TEXT REFERENCES campaigns(id),
    account         TEXT,
    consignment     TEXT,
    tracking_number TEXT,
    recipient       TEXT,
    postcode        TEXT,
    service         TEXT,
    status          TEXT,
    weight          REAL DEFAULT 0,
    parcels         INTEGER DEFAULT 1,
    eta             TEXT,
    cost            REAL DEFAULT 0,
    surcharges      REAL DEFAULT 0,
    co2_kg          REAL DEFAULT 0,
    dispatch_date   TEXT,
    recorded_at     TEXT NOT NULL
);

-- Re-uploading the same DHL export must not duplicate history.
CREATE UNIQUE INDEX IF NOT EXISTS ux_shipment_consignment
    ON shipments(account, consignment);

CREATE INDEX IF NOT EXISTS ix_shipment_campaign ON shipments(campaign_id);
CREATE INDEX IF NOT EXISTS ix_shipment_date     ON shipments(dispatch_date);
"""


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def get_conn():
    """Yield a connection with rows accessible by column name."""
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    # WAL lets readers carry on while someone else is writing - the
    # multi-CSR problem the old CSV files had.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


# ---------------------------------------------------------------- campaigns

def upsert_campaign(campaign_id, client, name, am="", dispatch_date=None,
                    stores=0, collation_hrs=0.0, status="", notes=""):
    """Insert or update a campaign. Never clears an existing share_token."""
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO campaigns
                (id, client, name, am, dispatch_date, stores,
                 collation_hrs, status, notes, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                client        = excluded.client,
                name          = excluded.name,
                am            = excluded.am,
                dispatch_date = excluded.dispatch_date,
                stores        = excluded.stores,
                collation_hrs = excluded.collation_hrs,
                status        = excluded.status,
                notes         = excluded.notes
            """,
            (campaign_id, client, name, am, dispatch_date, stores,
             collation_hrs, status, notes, _now()),
        )
    return campaign_id


def list_campaigns():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM campaigns ORDER BY dispatch_date DESC, client"
        )]


def get_campaign(campaign_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM campaigns WHERE id = ?", (campaign_id,)
        ).fetchone()
    return dict(row) if row else None


def ensure_share_token(campaign_id):
    """
    Return this campaign's client-link token, creating one if needed.

    32 url-safe bytes - not guessable by brute force, but it IS a
    bearer token: anyone holding the link can see that campaign's
    shipments. Treat it like a document share link, and use
    revoke_share_token() when a campaign closes.
    """
    existing = get_campaign(campaign_id)
    if existing and existing.get("share_token"):
        return existing["share_token"]

    token = secrets.token_urlsafe(32)
    with get_conn() as conn:
        conn.execute(
            "UPDATE campaigns SET share_token = ? WHERE id = ?",
            (token, campaign_id),
        )
    return token


def revoke_share_token(campaign_id):
    with get_conn() as conn:
        conn.execute(
            "UPDATE campaigns SET share_token = NULL WHERE id = ?",
            (campaign_id,),
        )


def get_campaign_by_token(token):
    """Look up a campaign from a client share link. None if not valid."""
    if not token:
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM campaigns WHERE share_token = ?", (token,)
        ).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------- shipments

SHIPMENT_FIELDS = (
    "campaign_id account consignment tracking_number recipient postcode "
    "service status weight parcels eta cost surcharges co2_kg dispatch_date"
).split()


def record_shipments(rows):
    """
    Store shipments, skipping ones already recorded.

    `rows` is a list of dicts using SHIPMENT_FIELDS keys. Re-running the
    same DHL export updates status/ETA rather than creating duplicates,
    so a CSR can safely re-upload to refresh tracking.

    Returns (inserted_or_updated, skipped_without_consignment).
    """
    written = skipped = 0
    with get_conn() as conn:
        for r in rows:
            if not r.get("consignment"):
                skipped += 1
                continue
            values = [r.get(f) for f in SHIPMENT_FIELDS] + [_now()]
            conn.execute(
                f"""
                INSERT INTO shipments ({','.join(SHIPMENT_FIELDS)}, recorded_at)
                VALUES ({','.join('?' * (len(SHIPMENT_FIELDS) + 1))})
                ON CONFLICT(account, consignment) DO UPDATE SET
                    status          = excluded.status,
                    eta             = excluded.eta,
                    cost            = excluded.cost,
                    surcharges      = excluded.surcharges,
                    co2_kg          = excluded.co2_kg,
                    campaign_id     = COALESCE(excluded.campaign_id, shipments.campaign_id),
                    tracking_number = COALESCE(excluded.tracking_number, shipments.tracking_number),
                    recorded_at     = excluded.recorded_at
                """,
                values,
            )
            written += 1
    return written, skipped


def shipments_for_campaign(campaign_id):
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM shipments WHERE campaign_id = ? ORDER BY recipient",
            (campaign_id,),
        )]


def all_shipments(since=None):
    """Every shipment, optionally from an ISO date onwards."""
    sql = "SELECT s.*, c.client, c.name AS campaign_name FROM shipments s " \
          "LEFT JOIN campaigns c ON c.id = s.campaign_id"
    params = []
    if since:
        sql += " WHERE s.dispatch_date >= ?"
        params.append(since)
    sql += " ORDER BY s.dispatch_date DESC"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql, params)]


def stats():
    """Headline counts, cheap enough to call on every page load."""
    with get_conn() as conn:
        return dict(conn.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM campaigns) AS campaigns,
                (SELECT COUNT(*) FROM shipments) AS shipments,
                (SELECT COALESCE(SUM(cost + surcharges), 0) FROM shipments) AS spend,
                (SELECT COALESCE(SUM(surcharges), 0) FROM shipments) AS surcharges
            """
        ).fetchone())


# ------------------------------------------------------- moving to Postgres
#
# When SQLite stops being enough (roughly: more than a handful of people
# writing at once, or you need the data to outlive the container):
#
#   1. pip install sqlalchemy psycopg2-binary
#   2. Replace get_conn() with a SQLAlchemy engine against DATABASE_URL.
#   3. Swap the ? placeholders for %s (or use SQLAlchemy text() with
#      named params).
#   4. AUTOINCREMENT -> SERIAL / IDENTITY in the schema.
#
# The ON CONFLICT syntax above is already Postgres-compatible. Nothing
# in pages/ touches SQL directly, so pages don't change at all.
