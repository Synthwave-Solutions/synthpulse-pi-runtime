"""Shared test harness for the Memory explorer (A13, plan addendum 6.6.10).

Synthetic stores only: every bank is a small SQLite file in the upstream
schema, created under a pytest temporary directory. Nothing here reads a live
bank, the live hub config or anything under ~/.hermes.
"""
from __future__ import annotations

import copy
import io
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse

MICHAEL = "michael@synthwave.test"
YASER = "yaser@synthwave.test"
ODIS = "odis@synthwave.test"
HRISHIKESH = "hrishikesh@partner.test"
ADA = "ada@synthwave.test"
BOB = "bob@synthwave.test"
DELIVERY = "delivery@synthwave.test"
OWNERLESS = "owner-role@synthwave.test"
CANARY = "CANARY-7f3a9c-memory-content"

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE working_memory (
    id TEXT PRIMARY KEY, content TEXT NOT NULL, source TEXT, timestamp TEXT,
    session_id TEXT DEFAULT 'default', importance REAL DEFAULT 0.5,
    metadata_json TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    recall_count INTEGER DEFAULT 0, last_recalled TIMESTAMP DEFAULT NULL,
    valid_until TIMESTAMP DEFAULT NULL, superseded_by TEXT DEFAULT NULL,
    scope TEXT DEFAULT 'global', author_id TEXT, author_type TEXT, channel_id TEXT,
    veracity TEXT DEFAULT 'unknown'
);
CREATE TABLE episodic_memory (
    rowid INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT UNIQUE NOT NULL, content TEXT NOT NULL, source TEXT, timestamp TEXT,
    session_id TEXT DEFAULT 'default', importance REAL DEFAULT 0.5,
    metadata_json TEXT, summary_of TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    recall_count INTEGER DEFAULT 0, last_recalled TIMESTAMP DEFAULT NULL,
    valid_until TIMESTAMP DEFAULT NULL, superseded_by TEXT DEFAULT NULL,
    scope TEXT DEFAULT 'global', author_id TEXT, author_type TEXT, channel_id TEXT,
    veracity TEXT DEFAULT 'unknown', tier INTEGER DEFAULT 1, degraded_at TEXT
);
CREATE TABLE triples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL, predicate TEXT NOT NULL, object TEXT NOT NULL,
    valid_from TEXT NOT NULL, valid_until TEXT, source TEXT, confidence REAL DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE consolidation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, items_consolidated INTEGER,
    summary_preview TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE memoria_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, subject TEXT, predicate TEXT, object TEXT,
    session_id TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def make_bank(path: Path, *, owner: str, memories: int = 3, extra: list[str] | None = None, wal: bool = True) -> Path:
    """A synthetic store with ``memories`` working memories about ``owner``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    script = SCHEMA if wal else SCHEMA.replace("PRAGMA journal_mode=WAL;", "")
    con.executescript(script)
    for i in range(memories):
        con.execute(
            "INSERT INTO working_memory(id,content,source,timestamp,session_id,importance,scope,veracity) VALUES (?,?,?,?,?,?,?,?)",
            (f"{owner}-w{i}", f"{owner} prefers option {i} for project planning", "preference",
             f"2026-09-{10 + i:02d}T09:00:00", f"s{i}", 0.5 + i / 100, "global", "stated"),
        )
    for i, text in enumerate(extra or []):
        con.execute(
            "INSERT INTO episodic_memory(id,content,source,timestamp,session_id,importance,scope) VALUES (?,?,?,?,?,?,?)",
            (f"{owner}-e{i}", text, "task", f"2026-09-2{i % 9}T10:00:00", "s-extra", 0.6, "session"),
        )
    con.execute("INSERT INTO triples(subject,predicate,object,valid_from,source,confidence) VALUES (?,?,?,?,?,?)",
                (owner, "works_on", "memory explorer", "2026-09-01", "preference", 0.9))
    con.execute("INSERT INTO consolidation_log(session_id,items_consolidated,summary_preview) VALUES (?,?,?)",
                ("s0", 2, f"{owner} planning summary"))
    con.execute("INSERT INTO memoria_facts(subject,predicate,object,session_id) VALUES (?,?,?,?)",
                (owner, "likes", "clear dashboards", "s0"))
    con.commit()
    con.close()
    return path


def make_hq(root: Path, *, shared_profile: bool = True) -> SimpleNamespace:
    """An HQ-shaped set of synthetic stores and a hub config for them.

    * hub banks: Michael's root ``default`` bank, one bank per other person,
      ``team-shared``, the unmapped ``u-info`` and ``engine-only`` (fed only by
      an identity);
    * profile copies: ``ada`` (a person store of Ada), ``sales-ops`` (no
      person), ``pair`` (a bank two identities map to) and ``michael`` (a copy
      of Michael's owner-private bank);
    * an extra root with the mux ``custom`` bank.
    """
    hermes = root / "home"
    data = hermes / "mnemosyne" / "data"
    mux = root / "mux" / "mnemosyne" / "data"
    make_bank(data / "mnemosyne.db", owner="michael", extra=["michael private roadmap note"])
    people = {MICHAEL: "default", ADA: "u-ada", BOB: "u-bob", YASER: "u-yaser", ODIS: "u-odis", HRISHIKESH: "u-hrishikesh"}
    for email, bank in people.items():
        if bank != "default":
            make_bank(data / "banks" / bank / "mnemosyne.db", owner=email.split("@")[0],
                      memories=4 if email == ADA else 2, extra=[f"{CANARY} for {email.split('@')[0]}"] if email == ADA else None)
    make_bank(data / "banks" / "team-shared" / "mnemosyne.db", owner="team")
    make_bank(data / "banks" / "u-info" / "mnemosyne.db", owner="info")
    make_bank(data / "banks" / "engine-only" / "mnemosyne.db", owner="engine")
    profiles = hermes / "profiles"
    make_bank(profiles / "ada" / "mnemosyne" / "data" / "banks" / "u-ada" / "mnemosyne.db", owner="ada-profile")
    make_bank(profiles / "sales-ops" / "mnemosyne" / "data" / "banks" / "sales" / "mnemosyne.db", owner="sales")
    make_bank(profiles / "michael" / "mnemosyne" / "data" / "mnemosyne.db", owner="michael-profile")
    if shared_profile:
        make_bank(profiles / "pair" / "mnemosyne" / "data" / "banks" / "pair-bank" / "mnemosyne.db", owner="pair")
    make_bank(mux / "banks" / "custom" / "mnemosyne.db", owner="mux")
    config = {
        "bind_host": "127.0.0.1",
        "data_dir": str(data),
        "shared_bank": "team-shared",
        "tokens_file": str(root / "never-read.tokens.json"),
        "people": {
            MICHAEL: {"naam": "Michael", "bank": "default"},
            ADA: {"naam": "Ada Lovelace", "bank": "u-ada"},
            BOB: {"naam": "Bob", "bank": "u-bob"},
            YASER: {"naam": "Yaser", "bank": "u-yaser"},
            ODIS: {"naam": "Odis", "bank": "u-odis"},
            HRISHIKESH: {"naam": "Hrishikesh", "bank": "u-hrishikesh"},
        },
        "service_identities": {
            "hermes-core": {"naam": "engine", "email": "engine@agent.local", "bank": "default"},
            "hermes-ada": {"naam": "Ada profile", "email": ADA, "bank": "u-ada"},
            "hermes-sales-ops": {"naam": "Sales", "email": "sales@agent.local", "bank": "sales"},
            "hermes-michael": {"naam": "Michael profile", "email": MICHAEL, "bank": "default"},
            "hermes-pair": {"naam": "Pair", "email": BOB, "bank": "pair-bank"},
            "pair-other": {"naam": "Other", "email": "other@agent.local", "bank": "pair-bank"},
            "engine-feed": {"naam": "Engine feed", "email": "feed@agent.local", "bank": "engine-only"},
        },
    }
    import yaml

    config_path = root / "hub-config.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return SimpleNamespace(root=root, hermes=hermes, data=data, profiles=profiles, mux=mux,
                           config_path=config_path, roots=f"{hermes}:{mux}")


def hq_policy(*, installation: dict | None = None, organization: dict | None = None) -> dict:
    policy = {
        "version": 1,
        "mode": "enforce",
        "default_effect": "deny",
        "bootstrap_admins": [MICHAEL],
        "roles": {
            "member": {"grants": {"permissions": ["chat:use", "sessions:read"], "profiles": ["*"], "routes": ["*"]}},
            "owner": {"grants": {"permissions": ["chat:use", "governance:read"], "profiles": ["*"], "routes": ["*"]}},
            "admin_delivery": {"grants": {"permissions": ["*"], "profiles": ["*"], "routes": ["*"]}},
        },
        "users": {
            YASER: {"roles": ["member"], "access_level": "admin", "access_mode": "blacklist"},
            ODIS: {"roles": ["member"], "access_level": "admin", "access_mode": "blacklist"},
            HRISHIKESH: {"roles": ["admin_delivery"], "access_level": "elevated", "access_mode": "blacklist",
                         "grants": {"permissions": ["*"]}},
            DELIVERY: {"roles": ["admin_delivery"]},
            OWNERLESS: {"roles": ["owner"]},
            ADA: {"roles": ["member"]},
            BOB: {"roles": ["member"]},
        },
    }
    if installation is not None:
        policy["installation"] = installation
    if organization is not None:
        policy["organization"] = organization
    return copy.deepcopy(policy)


def identity(email: str, name: str = "", method: str = "oidc") -> dict:
    return {"email": email, "groups": [], "claims_subset": {"name": name or email.split("@")[0].title()}, "method": method}


class Handler:
    """Records one response the way BaseHTTPRequestHandler would send it."""

    def __init__(self, headers: dict | None = None):
        self.status = None
        self.headers = dict(headers or {})
        self.response_headers: list[tuple[str, str]] = []
        self.wfile = io.BytesIO()

    def send_response(self, status):
        self.status = status

    def send_header(self, key, value):
        self.response_headers.append((key, value))

    def end_headers(self):
        pass

    def header(self, name):
        return next((v for k, v in self.response_headers if k.lower() == name.lower()), None)

    def headers_named(self, name):
        return [v for k, v in self.response_headers if k.lower() == name.lower()]

    @property
    def raw(self):
        data = self.wfile.getvalue()
        if self.header("Content-Encoding") == "gzip":
            import gzip

            return gzip.decompress(data)
        return data

    @property
    def body(self):
        return json.loads(self.raw.decode("utf-8"))


def parsed(path: str):
    return urlparse("http://localhost" + path)


class Env:
    """Drive the Memory explorer routes as a signed-in user, over synthetic stores.

    Isolates everything: the reference key and the access log in a temporary
    state directory, the governance audit under a temporary HERMES_HOME, the
    policy through the loader seam, the explorer config through
    ``memdash_scope.load_config``. The session identity comes from
    ``as_user``; the interactive-session checks are satisfied the way a
    browser with a valid cookie and CSRF token would satisfy them.
    """

    def __init__(self, monkeypatch, tmp_path: Path, *, policy: dict | None = None, backend: str = "sqlite_interim",
                 hq: SimpleNamespace | None = None):
        from api import memdash, memdash_access_log, memdash_backend, memdash_registry, memdash_scope
        from api.governance import loader
        from api.governance.loader import parse_governance_policy

        self.memdash = memdash
        self.access_log = memdash_access_log
        self.backends = memdash_backend
        self.registry = memdash_registry
        self.scope = memdash_scope
        self.loader = loader
        self.tmp = tmp_path
        self.hq = hq or make_hq(tmp_path / "stores")
        self.state = tmp_path / "state"
        self.state.mkdir(exist_ok=True)
        self.hermes_home = tmp_path / "hermes-home"
        self.hermes_home.mkdir(exist_ok=True)
        monkeypatch.setattr(memdash_registry, "_state_dir", lambda: self.state)
        memdash_registry.clear_cache()
        memdash_access_log.set_path(self.state / "memory_access_log.sqlite3")
        monkeypatch.setenv("HERMES_HOME", str(self.hermes_home))
        monkeypatch.setenv("HERMES_WEBUI_MEMDASH_BACKEND", backend)
        monkeypatch.setenv("HERMES_WEBUI_MEMDASH_HUB_CONFIG", str(self.hq.config_path))
        monkeypatch.setenv("HERMES_WEBUI_MEMDASH_BANK_ROOTS", self.hq.roots)
        monkeypatch.delenv("HERMES_WEBUI_MNEMO_URL", raising=False)
        self.policy_data = policy if policy is not None else hq_policy(installation={"kind": "hq"})
        self.set_policy(self.policy_data)
        self._parse = parse_governance_policy
        self.config = memdash_scope.Config(enabled=True, admin_view=True)
        monkeypatch.setattr(memdash_scope, "load_config", lambda: self.config)
        monkeypatch.setattr(memdash, "_auth_enabled", lambda handler: True)
        monkeypatch.setattr(memdash, "_session_identity", lambda handler: copy.deepcopy(self.identity))
        monkeypatch.setattr(memdash, "_csrf_ok", lambda handler: True)
        memdash.reset_state()
        memdash_backend.InterimSqliteBackend._shared = None
        self.identity = identity(ADA, "Ada Lovelace")

    def set_policy(self, data: dict | None, error: Exception | None = None) -> None:
        from api.governance.loader import parse_governance_policy

        if error is not None:
            def broken():
                raise error
            self.loader.set_policy_loader(broken)
            return
        policy = parse_governance_policy(data)
        self.loader.set_policy_loader(lambda: policy)

    def configure(self, **changes) -> None:
        from dataclasses import replace

        self.config = replace(self.config, **changes)

    def as_user(self, email: str, name: str = "", method: str = "oidc") -> "Env":
        self.identity = identity(email, name or email.split("@")[0].title(), method)
        return self

    def get(self, path: str, headers: dict | None = None) -> Handler:
        handler = Handler(headers)
        result = self.memdash.handle_get(handler, parsed(path))
        if result is False:
            handler.status = 404
        return handler

    def post(self, path: str, body, headers: dict | None = None) -> Handler:
        handler = Handler(headers)
        result = self.memdash.handle_post(handler, parsed(path), copy.deepcopy(body))
        if result is False:
            handler.status = 404
        return handler

    def banks(self) -> dict:
        response = self.get("/api/memdash/banks")
        assert response.status == 200, response.raw
        return response.body

    def ref_of(self, predicate) -> str:
        """The reference of the first store (as an admin sees them) matching ``predicate``."""
        stores = self.registry.interim_stores()
        for store in stores:
            if predicate(store):
                return store.ref
        raise AssertionError("no such store")

    def view(self, ref: str, view: str = "stats", **params) -> Handler:
        from urllib.parse import urlencode

        query = urlencode({"bank": ref, "view": view, **params})
        return self.get("/api/memdash/v1/view?" + query)

    def audit_rows(self) -> list[dict]:
        path = self.hermes_home / "dashboard-governance-audit.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def close(self) -> None:
        shared = self.backends.InterimSqliteBackend._shared
        if shared is not None:
            shared.reader.close()
        self.backends.InterimSqliteBackend._shared = None
        self.loader.set_policy_loader(None)
        self.access_log.set_path(None)
        self.registry.clear_cache()
        self.memdash.reset_state()
