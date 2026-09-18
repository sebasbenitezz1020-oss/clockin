from pathlib import Path
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured
import os

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-dev-key")
DEBUG = os.getenv("DEBUG", "False") == "True"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "core",
    "usuarios",
    "biometrico",
    "portal_funcionario",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.EmpresaActivaMiddleware",
    "core.middleware.SuscripcionMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                'core.context_processors.config_general',
                'core.context_processors.suscripcion_context',
                'usuarios.context_processors.permisos_menu',
                'usuarios.context_processors.multiempresa_context',
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

CLOCKIN_ENV = os.getenv("CLOCKIN_ENV", "production").strip().lower()
if CLOCKIN_ENV not in {"production", "development"}:
    raise ImproperlyConfigured("CLOCKIN_ENV must be production or development.")

_database_engine = os.getenv("DB_ENGINE", "").strip()
if CLOCKIN_ENV == "development" and not _database_engine:
    _database_engine = "django.db.backends.sqlite3"

if CLOCKIN_ENV == "production" and _database_engine != "django.db.backends.postgresql":
    raise ImproperlyConfigured("Production requires an explicit PostgreSQL DB_ENGINE.")

if _database_engine == "django.db.backends.postgresql":
    _database_fields = ("NAME", "USER", "PASSWORD", "HOST", "PORT")
    _database_values = {
        field: os.getenv("DB_" + field, "") for field in _database_fields
    }
    _missing_database_fields = [
        "DB_" + field
        for field, value in _database_values.items()
        if not value.strip()
    ]
    if _missing_database_fields:
        raise ImproperlyConfigured(
            "Missing PostgreSQL configuration: " + ", ".join(_missing_database_fields)
        )
    DATABASES = {
        "default": {"ENGINE": _database_engine, **_database_values}
    }
elif CLOCKIN_ENV == "development" and _database_engine == "django.db.backends.sqlite3":
    DATABASES = {
        "default": {
            "ENGINE": _database_engine,
            "NAME": os.getenv("DB_NAME") or BASE_DIR / "db.sqlite3",
        }
    }
else:
    raise ImproperlyConfigured("Unsupported database engine for CLOCKIN_ENV.")

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es"
TIME_ZONE = "America/Asuncion"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "usuarios.Usuario"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"
CSRF_TRUSTED_ORIGINS = os.getenv(
    "CSRF_TRUSTED_ORIGINS",
    "http://127.0.0.1,http://localhost"
).split(",")
