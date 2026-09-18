import os
from pathlib import Path
import runpy
import unittest
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.http.request import validate_host


SETTINGS_FILE = Path(__file__).with_name("settings.py")


class EnvironmentSettingsTests(unittest.TestCase):
    def load_settings(self, environment):
        # Never read a real .env or connect to a database in these tests.
        with patch.dict(os.environ, environment, clear=True):
            with patch("dotenv.load_dotenv", return_value=False):
                with patch(
                    "django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection",
                    side_effect=AssertionError("Configuration tests must not connect to a database"),
                ):
                    return runpy.run_path(str(SETTINGS_FILE))

    def production_environment(self):
        return {
            "CLOCKIN_ENV": "production",
            "DB_ENGINE": "django.db.backends.postgresql",
            "DB_NAME": "configuration_test_only",
            "DB_USER": "configuration_test_only",
            "DB_PASSWORD": "not-a-real-password",
            "DB_HOST": "127.0.0.1",
            "DB_PORT": "5432",
        }

    def test_production_accepts_explicit_postgresql(self):
        environment = self.production_environment()
        settings = self.load_settings(environment)
        database = settings["DATABASES"]["default"]
        self.assertEqual(settings["CLOCKIN_ENV"], "production")
        for field in ("ENGINE", "NAME", "USER", "PASSWORD", "HOST", "PORT"):
            self.assertEqual(database[field], environment["DB_" + field])

    def test_production_rejects_missing_database_variables(self):
        for key in self.production_environment():
            if not key.startswith("DB_"):
                continue
            with self.subTest(variable=key):
                environment = self.production_environment()
                del environment[key]
                with self.assertRaises(ImproperlyConfigured):
                    self.load_settings(environment)

    def test_production_rejects_blank_database_variables(self):
        for key in self.production_environment():
            if not key.startswith("DB_"):
                continue
            with self.subTest(variable=key):
                environment = self.production_environment()
                environment[key] = "   "
                with self.assertRaises(ImproperlyConfigured):
                    self.load_settings(environment)

    def test_production_rejects_sqlite(self):
        environment = self.production_environment()
        environment["DB_ENGINE"] = "django.db.backends.sqlite3"
        with self.assertRaises(ImproperlyConfigured):
            self.load_settings(environment)

    def test_no_environment_does_not_fall_back_to_sqlite(self):
        with self.assertRaises(ImproperlyConfigured):
            self.load_settings({})

    def test_invalid_environment_fails(self):
        environment = self.production_environment()
        environment["CLOCKIN_ENV"] = "prodution"
        with self.assertRaises(ImproperlyConfigured):
            self.load_settings(environment)

    def test_explicit_development_allows_sqlite(self):
        settings = self.load_settings({"CLOCKIN_ENV": "development"})
        self.assertEqual(
            settings["DATABASES"]["default"]["ENGINE"], "django.db.backends.sqlite3"
        )

    def test_development_can_use_postgresql(self):
        environment = self.production_environment()
        environment["CLOCKIN_ENV"] = "development"
        settings = self.load_settings(environment)
        self.assertEqual(
            settings["DATABASES"]["default"]["ENGINE"], "django.db.backends.postgresql"
        )

    def test_allowed_hosts_come_from_environment(self):
        environment = self.production_environment()
        environment["ALLOWED_HOSTS"] = "clockin.com.py,www.clockin.com.py,148.230.79.45"
        settings = self.load_settings(environment)
        for host in environment["ALLOWED_HOSTS"].split(","):
            with self.subTest(host=host):
                self.assertTrue(validate_host(host, settings["ALLOWED_HOSTS"]))
        self.assertFalse(validate_host("untrusted.invalid", settings["ALLOWED_HOSTS"]))


if __name__ == "__main__":
    unittest.main()
