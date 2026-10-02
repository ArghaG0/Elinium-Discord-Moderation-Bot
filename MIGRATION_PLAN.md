# Elinium migration plan

Last updated: 2026-10-02.

## Context

Elinium is a Python Discord bot built with discord.py and cogs. It is migrating from local JSON storage to PostgreSQL hosted on Neon (serverless), with the eventual goal of reliable 24/7 hosting. Dependency management will also move to `uv`.

**Start fresh in PostgreSQL. Do not import old JSON data or create an import script.** Existing JSON files remain in use until their consumers are migrated and Phase 6 removes them.

`main.py` creates the bot, initializes the database, and loads `cogs/general.py` and `cogs/moderation.py`. `utils.py` contains storage helpers, moderation-log rendering, duration parsing, and schema initialization. All persistent command data currently still uses JSON; no command uses PostgreSQL CRUD yet.

## Required workflow for every coding agent

1. Read this plan and inspect the relevant current code before implementing a phase.
2. **Implement only one phase at a time. Never implement multiple phases in one pass.**
3. Verify the implementation with appropriate checks and report what was tested and any limitations.
4. Update this file at the end of every phase, including its status, changes, verification evidence, and remaining issues. Mark implementation awaiting owner verification explicitly; do not equate agent checks with owner verification.
5. **The project owner must verify each phase before the next begins.** Wait for the owner's confirmation before proceeding.
6. Keep the separate bug tracker and `uv` status accurate when those tasks are addressed. Do not silently bundle unrelated fixes or dependency migration into a PostgreSQL phase.

Current checkpoint: The owner approved this document as the source of truth. Phase 1 is owner-verified. The four separately authorized bug fixes are implemented and locally verified, awaiting owner verification. Phase 2 has not started; wait for the owner's confirmation after these fixes before beginning it.

## Current schema

The following matches `utils.py:init_db()` as of the last update. The statements run through an acquired pool connection, sequentially, without an explicit enclosing transaction.

```sql
CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id BIGINT PRIMARY KEY,
    modlog_channel_id BIGINT,
    confession_channel_id BIGINT
);

CREATE TABLE IF NOT EXISTS warnings (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    moderator_id BIGINT NOT NULL,
    reason TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_warnings_guild_user
    ON warnings (guild_id, user_id);

CREATE TABLE IF NOT EXISTS blacklisted_words (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    word VARCHAR(255) NOT NULL,
    UNIQUE (guild_id, word)
);
CREATE INDEX IF NOT EXISTS idx_blacklisted_words_guild
    ON blacklisted_words (guild_id);

CREATE TABLE IF NOT EXISTS blacklisted_links (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    link VARCHAR(255) NOT NULL,
    UNIQUE (guild_id, link)
);
CREATE INDEX IF NOT EXISTS idx_blacklisted_links_guild
    ON blacklisted_links (guild_id);
```

Primary keys and unique constraints also create their supporting indexes. There are no foreign keys or additional check constraints. Channel IDs, warning reasons, and warning timestamps are nullable; the timestamp default does not impose `NOT NULL`. `CREATE TABLE IF NOT EXISTS` does not upgrade existing table definitions.

## Phase overview

| Phase | Scope | Status | Owner verification |
| --- | --- | --- | --- |
| 1 | DB connection pool and schema initialization | DONE | Verified working by owner; tables confirmed created in Neon |
| 2 | Async DB helper functions in `utils.py` | PENDING — not started | Pending |
| 3 | Refactor guild settings: modlog and confession channels | PENDING | Pending |
| 4 | Refactor warning commands | PENDING | Pending |
| 5 | Refactor blacklist commands and AutoMod cache | PENDING | Pending |
| 6 | Remove old JSON files and dead JSON-loading code | PENDING | Pending |

### Phase 1: DB connection pool and schema initialization

Implemented in `main.py:setup_hook()` and `utils.py:init_db()`:

- Read `DATABASE_URL` from the environment after loading `.env`.
- Create `bot.db_pool` with `asyncpg.create_pool()`, `min_size=1`, `max_size=10`, `command_timeout=60`, and connection `timeout=60.0`.
- Initialize the schema above before the Discord gateway connection.
- Print initialization failures and exit with status 1.
- Add `asyncpg==0.30.0` to `requirements.txt`.

Verification: the owner confirmed successful connection and table creation in Neon. The code review did not independently connect to Neon.

### Phase 2: Async DB helper functions in utils.py

Add asynchronous helpers using the existing pool and parameterized SQL for all four data categories:

- Guild settings: read, set, and clear modlog/confession channel settings as needed. Updating or clearing one setting must preserve the other column.
- Warnings: add, fetch in deterministic order, count, and delete all, a selected warning, or the latest N warnings within a guild/user scope. Keep database IDs distinct from displayed 1-based warning numbers.
- Blacklisted words and links: read, add, and remove guild-scoped entries, including the reads needed to populate the later cache. Handle duplicate entries consistently with the unique constraints and account for the 255-character limits.

Define helper inputs, return values, ordering, and error behavior for the later cog refactors. Use integer Discord IDs for `BIGINT` fields and account for database datetime values instead of JSON timestamp strings. Use transactions where a multi-statement operation requires atomicity.

Retain existing JSON helpers and cog behavior during this phase. Do not switch consumers yet. Verify helper behavior against the schema, including guild isolation and relevant edge cases; report results and wait for owner verification.

### Phase 3: Refactor guild settings

- Switch `setmodlogchannel` and `send_modlog_embed()` to DB helpers.
- Switch `/setconfessionchannel` and `/confess`, including invalid-channel cleanup, to DB helpers.
- Remove obsolete cog initialization/state for these settings when no longer needed; retain JSON helper removal for Phase 6.
- Verify settings persist across restarts, logs reach the configured channel, confessions use the configured channel, and changing one setting preserves the other.

All moderation actions that call `send_modlog_embed()` depend on this change, even if they do not directly manage settings.

### Phase 4: Refactor warnings

- Switch `warn`, `warnings`, and `clearwarnings` to DB helpers.
- Preserve warning display order, counts, moderator attribution, reasons, and timestamps.
- Preserve deletion modes: omitted argument clears all; positive argument selects a displayed warning number; negative argument removes the latest N.
- Preserve the zero-count rejection added by the separate bug fix; do not reintroduce that bug in DB helpers or the command refactor.
- Remove obsolete warning state from cog initialization when no longer needed.
- Verify persistence, guild/user isolation, ordering, counts, and deletion modes, including invalid inputs.

### Phase 5: Refactor blacklists and AutoMod cache

- Switch `blacklist addword`, `removeword`, `listwords`, `addlink`, `removelink`, and `listlinks` to DB-backed behavior.
- Replace the JSON-backed `all_blacklists_data` initialization with a DB-backed in-memory cache.
- Keep normal `on_message` blacklist checks in memory rather than issuing a DB query for every message.
- Populate the cache before it is needed and update/invalidate it consistently after successful DB mutations; failed writes must not appear successful in the cache.
- Preserve current input normalization and guild isolation. Define the cache lifecycle and document any single-process assumption.
- Verify cache initialization, add/remove visibility, restart persistence, and AutoMod behavior.

### Phase 6: Final JSON cleanup

- Confirm all storage consumers have migrated before deleting anything.
- Remove `warnings.json`, `blacklists.json`, `modlog_settings.json`, and `confession_channels.json`.
- Remove unused JSON load/save functions, file constants, imports, and remaining obsolete initialization/state.
- Update storage/setup documentation to reflect PostgreSQL and the actual dependency workflow.
- Search for remaining JSON-storage references and verify startup and migrated command flows without those files.
- Do not add a JSON import step.

## Current JSON dependency map

| Storage | Current consumers |
| --- | --- |
| `warnings.json` | `warn`, `warnings`, `clearwarnings` load on invocation; mutations save. Cog initialization also loads an otherwise unused `all_warnings_data`. |
| `modlog_settings.json` | `setmodlogchannel` loads/saves; `send_modlog_embed()` loads for every log. Cog initialization also loads an otherwise unused `all_modlog_settings`. |
| `blacklists.json` | Cog initialization loads `all_blacklists_data`; mutations update/save it; list commands and AutoMod read the dictionary. |
| `confession_channels.json` | Cog initialization loads `confession_channels_data`; configuration and invalid-channel cleanup save it; `/confess` reads it. |

## Non-migration issue tracker

These findings are tracked separately from PostgreSQL phase completion. The four fixes below were explicitly authorized after plan approval. FIXED means implemented and locally verified; owner verification of these fixes is still pending.

| Issue | Status | Finding |
| --- | --- | --- |
| Blacklist permission bypass | FIXED | Set the parent group to `invoke_without_command=False`, so its existing permission/guild checks run before subcommand dispatch. Verified all six subcommands and both subcommand aliases reject unauthorized members and DMs, allow authorized dispatch, and retain the bare group's help response. |
| `clearwarnings` zero-count bug | FIXED | Reject `0` with usage guidance before reading or saving warnings. Verified no storage access or modlog call for zero, and preserved all/positive-index/negative-count deletion modes. |
| Missing `asyncio` import in `say` | FIXED | Imported `asyncio` in `cogs/general.py`. A simulated timeout sends the expected feedback without deleting the command message or raising a name error. |
| Missing `EMOJIS['ERROR']` | FIXED | Added a Unicode cross emoji constant and the `ERROR` entry in `bot.EMOJIS`. Exercised both forbidden-send and generic-send failure paths in `/confess`; both return ephemeral error feedback without a key error. |
| Confession anonymity logging | FLAGGED — not yet addressed | Public posts omit identity, but console output and modlogs record the author and confession text. Owner intent should guide any behavior change. |
| `on_ready` re-sync issue | FLAGGED — not yet addressed | Cog loading and global slash-command synchronization run on every `on_ready` event instead of only during initial setup. |

The blacklist group behavior was checked against the pinned [discord.py 2.5.2 implementation](https://raw.githubusercontent.com/Rapptz/discord.py/v2.5.2/discord/ext/commands/core.py).

Regression verification: `tests/test_review_fixes.py` contains six passing offline tests, run with Python 3.13.5 and discord.py 2.5.2 using `python -B -m unittest discover -s tests -v`. The Windows `python` app alias was unavailable, so the run used the installed Python executable directly. Tests exercise actual group dispatch and cog callbacks with mocked Discord I/O and storage. Emoji configuration is evaluated from only the relevant assignments in `main.py`, avoiding bot startup and `.env` reads. No Discord/Neon connection or JSON file write occurred. Live owner verification is still pending. No dependency changes were needed.

## Migration and hosting considerations

- PostgreSQL is already required for startup even though all command persistence remains JSON-based.
- There is no explicit database pool shutdown handling or explicit validation for a missing `DATABASE_URL`.
- JSON operations remain synchronous and overwrite whole files; invalid JSON is treated as empty data and may be overwritten by later saves.
- The README currently documents `BOT_TOKEN` and environment-provided emojis, whereas the code reads `DISCORD_TOKEN` and uses hardcoded emojis. It also describes pip and JSON storage.
- Completing these six phases does not itself deploy the bot or establish 24/7 hosting. Hosting setup and operational verification remain separate work.

## uv migration

**Status: PENDING.** Neither `pyproject.toml` nor `uv.lock` has been created. Dependencies currently live in `requirements.txt`, including `discord.py==2.5.2` and `asyncpg==0.30.0`.

Use `uv` for dependency management going forward. The dependency migration must establish project metadata and direct dependencies in `pyproject.toml`, generate `uv.lock`, verify installation and startup through `uv`, and update setup documentation. Schedule this explicitly with the owner rather than treating it as already included in a PostgreSQL phase. Update this section when implementation and owner verification occur.

## Progress record

| Date | Change | Verification / next checkpoint |
| --- | --- | --- |
| 2026-10-02 | Recorded current migration state, exact schema, phase boundaries, and separate review findings. No application code changed. | Phase 1 previously owner-verified. Document awaiting owner review; Phase 2 not started. |
| 2026-10-02 | Owner approved the plan as the source of truth. Implemented the four authorized pending non-migration bug fixes and added offline regression checks. | All six tests passed. Bug fixes await owner verification; Phase 2 remains not started. Confession logging and `on_ready` re-sync remain flagged and unchanged. |
