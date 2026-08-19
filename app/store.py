import hashlib, json, os, secrets, sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def connect():
    db = sqlite3.connect(Path(os.getenv("U_DATABASE_PATH", "u.db")))
    db.row_factory = sqlite3.Row
    return db

def init_db():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS sessions(
          id TEXT PRIMARY KEY, user_id TEXT, request_json TEXT,
          response_json TEXT, created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS audit(
          id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT,
          event TEXT, payload_hash TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS approvals(
          proposal_id TEXT PRIMARY KEY, session_id TEXT, user_id TEXT,
          approved INTEGER, note TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS outcomes(
  id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT,
  outcome TEXT, helpfulness INTEGER, memory_consent INTEGER,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS rag_sources(
          source_id TEXT PRIMARY KEY, user_id TEXT, title TEXT,
          source_type TEXT, content_hash TEXT, chunk_count INTEGER,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS rag_chunks(
          source_id TEXT, chunk_index INTEGER, chunk_text TEXT,
          PRIMARY KEY(source_id, chunk_index)
        );
        CREATE TABLE IF NOT EXISTS memory(
          user_id TEXT, category TEXT, memory_key TEXT, value_json TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY(user_id,category,memory_key)
        );
        CREATE TABLE IF NOT EXISTS action_tokens(
          token_hash TEXT PRIMARY KEY, user_id TEXT, session_id TEXT,
          proposal_id TEXT, used INTEGER DEFAULT 0,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """)
    init_psi_tables()

def digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, default=str).encode()
    return hashlib.sha256(raw).hexdigest()

def save_session(session_id, user_id, request, response, created_at):
    with connect() as db:
        db.execute("INSERT INTO sessions VALUES(?,?,?,?,?)",
            (session_id, user_id, json.dumps(request), json.dumps(response), created_at))
        db.execute("INSERT INTO audit(session_id,event,payload_hash) VALUES(?,?,?)",
            (session_id, "decision_created", digest(response)))

def save_approval(data):
    with connect() as db:
        db.execute("INSERT OR REPLACE INTO approvals(proposal_id,session_id,user_id,approved,note) VALUES(?,?,?,?,?)",
            (data["proposal_id"], data["session_id"], data.get("user_id",""), int(data["approved"]), data["note"]))
        db.execute("INSERT INTO audit(session_id,event,payload_hash) VALUES(?,?,?)",
            (data["session_id"], "proposal_reviewed", digest(data)))

def save_outcome(data):
    with connect() as db:
        db.execute("INSERT INTO outcomes(session_id,outcome,helpfulness,memory_consent) VALUES(?,?,?,?)",
            (data["session_id"], data["outcome"], data["helpfulness"], int(data["memory_consent"])))

def delete_user(user_id):
    with connect() as db:
        rows = db.execute("SELECT id FROM sessions WHERE user_id=?", (user_id,)).fetchall()
        ids = [r["id"] for r in rows]
        for sid in ids:
            db.execute("DELETE FROM audit WHERE session_id=?", (sid,))
            db.execute("DELETE FROM approvals WHERE session_id=?", (sid,))
            db.execute("DELETE FROM outcomes WHERE session_id=?", (sid,))
        db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        db.execute("DELETE FROM memory WHERE user_id=?", (user_id,))
        db.execute("DELETE FROM action_tokens WHERE user_id=?", (user_id,))
        # Also clean up RAG data (GDPR right to be forgotten)
        rag_sources = db.execute("SELECT source_id FROM rag_sources WHERE user_id=?", (user_id,)).fetchall()
        for rs in rag_sources:
            db.execute("DELETE FROM rag_chunks WHERE source_id=?", (rs["source_id"],))
        db.execute("DELETE FROM rag_sources WHERE user_id=?", (user_id,))
        return len(ids)

def remember(user_id, category, key, value):
    with connect() as db:
        db.execute("""INSERT OR REPLACE INTO memory(user_id,category,memory_key,value_json)
          VALUES(?,?,?,?)""", (user_id, category, key, json.dumps(value)))

def recall(user_id):
    with connect() as db:
        rows=db.execute("SELECT category,memory_key,value_json FROM memory WHERE user_id=?",(user_id,)).fetchall()
        return [{"category":r["category"],"key":r["memory_key"],"value":json.loads(r["value_json"])} for r in rows]

def issue_token(user_id, session_id, proposal_id, token):
    with connect() as db:
        db.execute("INSERT INTO action_tokens(token_hash,user_id,session_id,proposal_id) VALUES(?,?,?,?)",
          (digest(token), user_id, session_id, proposal_id))

def consume_token(user_id, session_id, proposal_id, token):
    token_hash=digest(token)
    with connect() as db:
        row=db.execute("""SELECT used,user_id,session_id,proposal_id FROM action_tokens
          WHERE token_hash=?""",(token_hash,)).fetchone()
        valid=bool(row and not row["used"] and row["user_id"]==user_id
          and row["session_id"]==session_id and row["proposal_id"]==proposal_id)
        if valid:
            db.execute("UPDATE action_tokens SET used=1 WHERE token_hash=?",(token_hash,))
            db.execute("INSERT INTO audit(session_id,event,payload_hash) VALUES(?,?,?)",
              (session_id,"approval_token_consumed",token_hash))
        return valid

def is_approved(session_id, proposal_id, user_id=None):
    with connect() as db:
        if user_id is not None:
            row=db.execute("SELECT approved FROM approvals WHERE session_id=? AND proposal_id=? AND user_id=?",
              (session_id,proposal_id,user_id)).fetchone()
        else:
            row=db.execute("SELECT approved FROM approvals WHERE session_id=? AND proposal_id=?",
              (session_id,proposal_id)).fetchone()
        return bool(row and row["approved"])

# ── RAG persistence (SQLite-backed, replaces in-memory store) ──────────

def rag_ingest_source(user_id: str, title: str, source_type: str,
                      chunks: list[str], content_hash: str) -> str:
    """Create a RAG source with chunks in SQLite. Returns source_id."""
    source_id = f"rag_{secrets.token_hex(8)}"
    with connect() as db:
        db.execute(
            "INSERT INTO rag_sources(source_id,user_id,title,source_type,content_hash,chunk_count) VALUES(?,?,?,?,?,?)",
            (source_id, user_id, title, source_type, content_hash, len(chunks))
        )
        for i, chunk in enumerate(chunks):
            db.execute(
                "INSERT INTO rag_chunks(source_id,chunk_index,chunk_text) VALUES(?,?,?)",
                (source_id, i, chunk)
            )
    return source_id

def rag_get_user_chunks(user_id: str) -> list[dict]:
    """Return all RAG sources and chunks for a user."""
    with connect() as db:
        sources = db.execute(
            "SELECT * FROM rag_sources WHERE user_id=? ORDER BY created_at DESC",
            (user_id,)
        ).fetchall()
        results = []
        for src in sources:
            chunks = db.execute(
                "SELECT chunk_index, chunk_text FROM rag_chunks WHERE source_id=? ORDER BY chunk_index",
                (src["source_id"],)
            ).fetchall()
            results.append({
                "source_id": src["source_id"],
                "title": src["title"],
                "source_type": src["source_type"],
                "content_hash": src["content_hash"],
                "chunk_count": src["chunk_count"],
                "chunks": [(c["chunk_index"], c["chunk_text"]) for c in chunks],
            })
        return results

def rag_delete_source(user_id: str, source_id: str) -> tuple[bool, bool]:
    """Delete a RAG source. Returns (found, authorized)."""
    with connect() as db:
        src = db.execute(
            "SELECT user_id FROM rag_sources WHERE source_id=?",
            (source_id,)
        ).fetchone()
        if not src:
            return False, True
        if src["user_id"] != user_id:
            return True, False
        db.execute("DELETE FROM rag_chunks WHERE source_id=?", (source_id,))
        db.execute("DELETE FROM rag_sources WHERE source_id=?", (source_id,))
        return True, True

# ═════════════════════════════════════════════════════════════════════
#  PSI PERSISTENCE — Cognitive state survives container restarts
# ═════════════════════════════════════════════════════════════════════

def init_psi_tables():
    """Create PSI persistence tables if they don't exist."""
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS psi_cognitive_profiles(
          user_id TEXT PRIMARY KEY,
          profile_json TEXT NOT NULL,
          interaction_count INTEGER DEFAULT 0,
          cognitive_depth REAL DEFAULT 0.0,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS psi_identity_states(
          user_id TEXT PRIMARY KEY,
          identity_json TEXT NOT NULL,
          identity_hash TEXT,
          identity_generation INTEGER DEFAULT 0,
          total_embeddings INTEGER DEFAULT 0,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS psi_embeddings(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id TEXT NOT NULL,
          session_id TEXT,
          substrate TEXT,
          directive_hash TEXT,
          governance_result TEXT,
          cognitive_profile TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS psi_multi_agent_log(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id TEXT NOT NULL,
          session_id TEXT,
          agent_states_json TEXT,
          active_count INTEGER,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """)

def save_cognitive_profile(user_id: str, profile_data: dict):
    """Persist a cognitive profile to SQLite."""
    with connect() as db:
        db.execute("""
            INSERT OR REPLACE INTO psi_cognitive_profiles
            (user_id, profile_json, interaction_count, cognitive_depth, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'))
        """, (user_id, json.dumps(profile_data),
              profile_data.get("interaction_count", 0),
              profile_data.get("cognitive_depth", 0.0)))

def load_cognitive_profile(user_id: str) -> dict | None:
    """Load a persisted cognitive profile."""
    with connect() as db:
        row = db.execute(
            "SELECT profile_json FROM psi_cognitive_profiles WHERE user_id=?",
            (user_id,)
        ).fetchone()
        if row:
            return json.loads(row["profile_json"])
    return None

def save_identity_state(user_id: str, identity_data: dict):
    """Persist an emergent identity state."""
    with connect() as db:
        db.execute("""
            INSERT OR REPLACE INTO psi_identity_states
            (user_id, identity_json, identity_hash, identity_generation,
             total_embeddings, updated_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        """, (user_id, json.dumps(identity_data),
              identity_data.get("identity_hash", ""),
              identity_data.get("identity_generation", 0),
              identity_data.get("total_embeddings", 0)))

def load_identity_state(user_id: str) -> dict | None:
    """Load a persisted identity state."""
    with connect() as db:
        row = db.execute(
            "SELECT identity_json FROM psi_identity_states WHERE user_id=?",
            (user_id,)
        ).fetchone()
        if row:
            return json.loads(row["identity_json"])
    return None

def log_psi_embedding(user_id: str, session_id: str, substrate: str,
                      directive_hash: str, governance_result: dict,
                      cognitive_profile: dict):
    """Log a PSI embedding event for audit and observability."""
    with connect() as db:
        db.execute("""
            INSERT INTO psi_embeddings
            (user_id, session_id, substrate, directive_hash,
             governance_result, cognitive_profile)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, session_id, substrate, directive_hash,
              json.dumps(governance_result), json.dumps(cognitive_profile)))

def log_multi_agent_state(user_id: str, session_id: str,
                          agent_states: dict, active_count: int):
    """Log multi-agent governance state for audit."""
    with connect() as db:
        db.execute("""
            INSERT INTO psi_multi_agent_log
            (user_id, session_id, agent_states_json, active_count)
            VALUES (?, ?, ?, ?)
        """, (user_id, session_id, json.dumps(agent_states), active_count))

def get_psi_stats(user_id: str) -> dict:
    """Get PSI statistics for a user."""
    with connect() as db:
        profile = db.execute(
            "SELECT interaction_count, cognitive_depth FROM psi_cognitive_profiles WHERE user_id=?",
            (user_id,)
        ).fetchone()
        identity = db.execute(
            "SELECT identity_generation, total_embeddings FROM psi_identity_states WHERE user_id=?",
            (user_id,)
        ).fetchone()
        embeddings = db.execute(
            "SELECT COUNT(*) as cnt FROM psi_embeddings WHERE user_id=?",
            (user_id,)
        ).fetchone()
        agent_logs = db.execute(
            "SELECT COUNT(*) as cnt FROM psi_multi_agent_log WHERE user_id=?",
            (user_id,)
        ).fetchone()
    return {
        "cognitive_profile_exists": profile is not None,
        "interaction_count": profile["interaction_count"] if profile else 0,
        "cognitive_depth": profile["cognitive_depth"] if profile else 0.0,
        "identity_generation": identity["identity_generation"] if identity else 0,
        "total_embeddings": identity["total_embeddings"] if identity else 0,
        "embedding_logs": embeddings["cnt"] if embeddings else 0,
        "multi_agent_logs": agent_logs["cnt"] if agent_logs else 0,
    }

def delete_psi_state(user_id: str):
    """Delete all PSI state for a user (cognitive right-to-forget)."""
    with connect() as db:
        db.execute("DELETE FROM psi_cognitive_profiles WHERE user_id=?", (user_id,))
        db.execute("DELETE FROM psi_identity_states WHERE user_id=?", (user_id,))
        db.execute("DELETE FROM psi_embeddings WHERE user_id=?", (user_id,))
        db.execute("DELETE FROM psi_multi_agent_log WHERE user_id=?", (user_id,))
