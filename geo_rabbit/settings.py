import os
from pathlib import Path

import sentry_sdk
from dj_database_url import config as db_config
from dotenv import load_dotenv
from sentry_sdk.integrations.django import DjangoIntegration

BASE_DIR = Path(__file__).parent.parent

load_dotenv(dotenv_path=BASE_DIR / ".env")


# --- Error Reporting ---

if os.getenv("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        environment=os.getenv("SENTRY_ENVIRONMENT"),
        integrations=[DjangoIntegration()],
    )


# --- Basic things ---

SECRET_KEY = os.getenv("SECRET_KEY")

DEBUG = os.getenv("DEBUG") == "yes"

ALLOWED_HOSTS = ["*"]

BASE_URL = os.getenv("BASE_URL")


# --- Apps ---

INSTALLED_APPS = [
    #
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    #
    # Dependencies
    "leaflet",
    #
    # Internal
    "robbit",
]


# --- Global conf ---

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "geo_rabbit.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

WSGI_APPLICATION = "geo_rabbit.wsgi.application"


# --- Data ---

DATABASES = {"default": db_config(conn_max_age=60)}


# --- Password validation ---

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# --- Internationalization ---

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Europe/Paris"

USE_I18N = True

USE_L10N = True

USE_TZ = True


# --- Static files ---

STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

STATICFILES_DIRS = [BASE_DIR / "geo_rabbit" / "static"]

STATICFILES_STORAGE = "geo_rabbit.storage.GzipManifestStaticFilesStorage"

STATIC_ROOT = BASE_DIR / "static"
STATIC_URL = "/static/"


# --- Storage ---

DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")
AWS_S3_CUSTOM_DOMAIN = os.getenv("AWS_S3_CUSTOM_DOMAIN")
AWS_S3_FILE_OVERWRITE = False
AWS_DEFAULT_ACL = "public-read"

AWS_S3_OBJECT_PARAMETERS = {"CacheControl": f"max-age={3600 * 24 * 365}"}


# --- Emails ---

if os.getenv("ENABLE_EMAILS") != "yes":
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"


# --- Flickr ---

FLICKR_API_KEY = os.getenv("FLICKR_API_KEY")
FLICKR_BASE_URL = os.getenv("FLICKR_BASE_URL", "https://www.flickr.com/services/rest/")
