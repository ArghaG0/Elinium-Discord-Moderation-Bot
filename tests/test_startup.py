"""Startup validation and import-safety checks without reading real secrets."""

import importlib
import logging
import os
from pathlib import Path
import runpy
import unittest
from unittest.mock import AsyncMock, patch

from config import ConfigError, load_config


VALID_ENV = {
    "DISCORD_TOKEN": "test-token-not-a-secret",
    "DATABASE_URL": "postgresql://test:test@localhost/elinium_test?sslmode=require",
}


class ConfigTests(unittest.TestCase):
    def test_defaults_and_repr_hide_credentials(self):
        with patch("config.load_dotenv", side_effect=AssertionError("Unexpected .env read")):
            config = load_config(VALID_ENV)
        self.assertIsNone(config.bot_owner_id)
        self.assertEqual(config.log_level, logging.INFO)
        self.assertNotIn(config.discord_token, repr(config))
        self.assertNotIn(config.database_url, repr(config))

    def test_optional_values_and_quoted_url(self):
        config = load_config({**VALID_ENV, "DATABASE_URL": "'" + VALID_ENV["DATABASE_URL"] + "'",
                              "BOT_OWNER_ID": "123456789012345678", "LOG_LEVEL": "debug"})
        self.assertEqual(config.database_url, VALID_ENV["DATABASE_URL"])
        self.assertEqual(config.bot_owner_id, 123456789012345678)
        self.assertEqual(config.log_level, logging.DEBUG)

    def test_invalid_settings_report_names_not_values(self):
        for key, values in {
            "DISCORD_TOKEN": ("", "   "),
            "DATABASE_URL": ("", "https://secret.example/db", "postgresql://host", "postgresql://host:bad/db"),
            "BOT_OWNER_ID": ("secret-owner", "0", "-1", str(2**63)),
            "LOG_LEVEL": ("secret-level", ""),
        }.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    with self.assertRaises(ConfigError) as caught:
                        load_config({**VALID_ENV, key: value})
                    self.assertIn(key, str(caught.exception))
                    if value.startswith("secret") or value.startswith("https"):
                        self.assertNotIn(value, str(caught.exception))

    def test_dotenv_is_only_loaded_on_explicit_startup(self):
        with patch.dict(os.environ, VALID_ENV, clear=True), patch("config.load_dotenv") as dotenv:
            self.assertEqual(load_config().discord_token, VALID_ENV["DISCORD_TOKEN"])
        dotenv.assert_called_once_with(Path(__file__).resolve().parents[1] / ".env", override=False)


class StartupTests(unittest.TestCase):
    def test_import_does_not_load_env_configure_logging_or_connect(self):
        with (
            patch("dotenv.load_dotenv", side_effect=AssertionError("Unexpected .env read")),
            patch("config.load_config", side_effect=AssertionError("Unexpected config load")),
            patch("logging.basicConfig", side_effect=AssertionError("Unexpected logging setup")),
            patch("discord.ext.commands.Bot.run", side_effect=AssertionError("Unexpected Discord startup")),
            patch("asyncpg.create_pool", side_effect=AssertionError("Unexpected database connection")),
        ):
            result = runpy.run_path(str(Path(__file__).resolve().parents[1] / "main.py"), run_name="import_test")
        self.assertTrue(callable(result["main"]))

    def test_bad_config_stops_before_bot_run(self):
        main = importlib.import_module("main")
        with (
            patch.object(main, "setup_logging"),
            patch.object(main, "load_config", side_effect=ConfigError("DISCORD_TOKEN is required.")),
            patch.object(main.bot, "run") as run,
            self.assertLogs(main.log, level="ERROR"),
            self.assertRaises(SystemExit) as caught,
        ):
            main.main()
        self.assertEqual(caught.exception.code, 1)
        run.assert_not_called()

    def test_valid_config_is_attached_before_startup(self):
        main = importlib.import_module("main")
        config = load_config(VALID_ENV)
        previous_level = logging.getLogger().level
        try:
            with patch.object(main, "setup_logging"), patch.object(main, "load_config", return_value=config), \
                    patch.object(main.bot, "run") as run:
                main.main()
            self.assertIs(main.bot.config, config)
            run.assert_called_once_with(config.discord_token, log_handler=None)
        finally:
            logging.getLogger().setLevel(previous_level)


class SetupHookTests(unittest.IsolatedAsyncioTestCase):
    async def test_pool_uses_validated_config(self):
        main = importlib.import_module("main")
        main.bot.config = load_config(VALID_ENV)
        with patch.object(main.asyncpg, "create_pool", new_callable=AsyncMock) as pool, \
                patch.object(main, "init_db", new_callable=AsyncMock) as init:
            await main.setup_hook()
        self.assertEqual(pool.call_args.args[0], VALID_ENV["DATABASE_URL"])
        init.assert_awaited_once_with(pool.return_value)
