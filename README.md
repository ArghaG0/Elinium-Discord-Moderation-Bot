# Elinium

Elinium is a Python discord.py bot with moderation, utility commands, confessions, and PostgreSQL persistence. The bot is currently run on a local machine, not hosted 24/7. Prefix commands use `eli `; `eli cmds` lists available commands.

## Local setup

Use Python 3.13.5 (selected by `.python-version`; supported range `>=3.13.5,<3.14`), [uv](https://docs.astral.sh/uv/getting-started/installation/), a Discord bot token, and a PostgreSQL database. Production storage uses Neon.

1. In the Discord Developer Portal, enable the Message Content, Server Members, and Presence privileged intents requested by `main.py`.
2. Invite the bot with bot/application-command scopes and the permissions needed for your chosen commands. Moderation actions also depend on Discord role hierarchy.
3. Copy `.env.example` to `.env` **only if you do not already have one**, and replace the placeholders. Alternatively, supply environment variables through your host. Existing environment variables take precedence.
4. From the repository root, run:

```sh
uv sync
uv run main.py
```

`pyproject.toml` declares the three direct dependencies; `uv.lock` records their complete resolved dependency graph. `uv sync` installs into the ignored `.venv/`; no manual environment activation is needed. Commit both project files when changing dependencies. For deployments, use `uv sync --locked` and `uv run --locked main.py` to require the checked-in lockfile. See [uv locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/).

| Variable | Purpose |
| --- | --- |
| `DISCORD_TOKEN` | Required Discord bot token. |
| `DATABASE_URL` | Required PostgreSQL connection URL, including the SSL options supplied by Neon. |
| `BOT_OWNER_ID` | Optional positive Discord user ID. Omit or leave empty to use discord.py owner discovery. |
| `LOG_LEVEL` | Optional console log level: DEBUG, INFO, WARNING, ERROR, CRITICAL. Default INFO. |

Startup validates configuration before opening connections. Keep `.env` private; it is ignored by Git. Emojis are defined in `main.py`, not environment variables.

## Storage and commands

Startup opens an asyncpg pool and creates missing tables/indexes through `utils.utils.init_db()`. The database role needs permission to initialize the schema. `CREATE TABLE IF NOT EXISTS` does not upgrade an existing table definition.

| Data | PostgreSQL table | Commands |
| --- | --- | --- |
| Modlog and confession channels | `guild_settings` | `eli setmodlogchannel`, `/setconfessionchannel`, `/confess` |
| Warnings | `warnings` | `eli warn`, `eli warnings`, `eli clearwarnings` |
| Blacklisted words | `blacklisted_words` | `eli blacklist addword`, `removeword`, `listwords` |
| Blacklisted links | `blacklisted_links` | `eli blacklist addlink`, `removelink`, `listlinks` |

All settings and moderation records are guild-scoped. Configure channels again if the new database has no settings; the migration starts fresh and does not import historical data. Persistence requires PostgreSQL; no local data files are used.

`eli clearwarnings <member>` clears all warnings; a positive argument deletes that displayed warning number, and a negative argument removes the latest N. Zero and out-of-range selections are rejected. Display numbers are distinct from database IDs.

AutoMod loads its blacklist cache before the moderation cog registers. Successful command writes update the cache; list commands refresh the relevant guild/type. Normal message matching reads memory. Restarting or reloading rebuilds the cache. This assumes one active bot process: external database edits or other processes do not automatically invalidate the cache. A matched violation can separately query modlog settings.

Other features include moderation actions, user/server information, and utility commands; see `eli cmds` for the current list. Confessions omit identity from public posts, but existing console output and moderation logs record the author and text. That behavior remains under review.

## Project layout

- `pyproject.toml`, `uv.lock`, `.python-version`: dependency metadata, resolved versions, and default interpreter.
- `main.py`: entry point, pool startup, extension loading, bot-level commands.
- `config/config.py`: validated environment configuration.
- `cogs/`: general and moderation commands/listeners.
- `db/`: settings, warnings, and blacklist data access.
- `utils/utils.py`: schema initialization, modlog embeds, duration parsing.
- `tests/`: local regression and opt-in PostgreSQL integration tests (ignored by Git; not included in fresh clones).
- `docs/MIGRATION_PLAN.md`: migration decisions, verification history, deferred work.

## Verification

If the local `tests/` folder is present, run the regression suite through the same dependency environment. Tests are retained locally but no longer tracked by Git:

```sh
uv run python -B -m unittest discover -s tests -v
```

For database integration checks, explicitly set `TEST_DATABASE_URL` to a disposable PostgreSQL database before running that command. The test role must be able to create/drop schemas. Each test creates and removes its own unique schema. Without that variable, integration tests skip; they never read `.env` or fall back to `DATABASE_URL`. Discord I/O is mocked; the suite does not log in or sync live slash commands.

## Limitations

- The bot runs only while a local machine keeps the process running and stays connected. It goes offline when that machine is off, disconnected, or the process stops.
- No 24/7 cloud hosting is currently set up. Running Docker locally has the same uptime limitation.
- PostgreSQL is cloud-hosted on Neon and persists independently of the bot process. Stored settings, warnings, and blacklists are retained while the bot is offline.

## Docker (alternative run method)

Docker is available as an alternative to the local uv commands above, including for a future 24/7 host. Building an image does not deploy it or establish continuous hosting.

```sh
docker build -t elinium:local .
docker run --rm --name elinium --env-file .env elinium:local
```

Stop it from another terminal with `docker stop elinium`. Run only one bot instance at a time, including local uv processes, to preserve the blacklist cache's single-process assumption. No ports need publishing; the bot makes outbound connections to Discord and Neon.

Supply the same environment variables at runtime. `.env` is excluded from the build context and image. Docker's `--env-file` expects literal `KEY=value` entries without shell expansion or surrounding quotes; alternatively configure these variables through your host's secret settings. Do not put credentials in the Dockerfile.

The image uses official Python 3.13.5 slim and a pinned uv build stage, installing from `uv.lock` with `uv sync --locked --no-dev`. The final image runs as a non-root user with the installed Python environment and no uv installer/build tools. See [uv's Docker guide](https://docs.astral.sh/uv/guides/integration/docker/) for the build approach.

Pool shutdown handling and repeated `on_ready` synchronization remain deferred. See the [migration plan](docs/MIGRATION_PLAN.md) for remaining work.
