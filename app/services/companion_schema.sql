CREATE TABLE IF NOT EXISTS companion_owners (
 owner TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 1,
 revision INTEGER NOT NULL DEFAULT 0, context_after INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS companion_messages (
 id INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT NOT NULL, pet_id INTEGER NOT NULL,
 role TEXT NOT NULL CHECK(role IN ('user','assistant')), content TEXT NOT NULL,
 request_id TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 UNIQUE(owner,pet_id,request_id,role)
);
CREATE INDEX IF NOT EXISTS companion_messages_owner ON companion_messages(owner,pet_id,id);
CREATE TABLE IF NOT EXISTS companion_memories (
 id INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT NOT NULL, pet_id INTEGER NOT NULL DEFAULT 0,
 category TEXT NOT NULL, value TEXT NOT NULL, source_quote TEXT NOT NULL DEFAULT '',
 source_message INTEGER, confirmed INTEGER NOT NULL DEFAULT 0,
 updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 UNIQUE(owner,pet_id,category,value)
);
CREATE INDEX IF NOT EXISTS companion_memories_owner ON companion_memories(owner,pet_id);
