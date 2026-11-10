"""
Django settings for the Seating Project backend.
Configured for CockroachDB via django-cockroachdb, CORS for Vite, and DRF.
"""

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    'django-insecure-seating-project-dev-key-change-in-production',
)

DEBUG = os.environ.get('DJANGO_DEBUG', '1').strip().lower() not in ('0', 'false', 'no', 'off')

_allowed_hosts_env = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1')
ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts_env.split(',') if h.strip()]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party packages
    'rest_framework',
    'corsheaders',
    # Project apps
    'seating',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # Must precede CommonMiddleware
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'backend.wsgi.application'

# =======================================================================
# Database: SQLite (local development, zero external service dependency)
# =======================================================================
_db_path_env = os.environ.get('DJANGO_DB_PATH')
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': Path(_db_path_env) if _db_path_env else BASE_DIR / 'db.sqlite3',
    }
}

# =======================================================================
# CORS configuration (allowing Vite frontend on localhost:5173)
# =======================================================================
_cors_origins_env = os.environ.get(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:5173,http://127.0.0.1:5173',
)
CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors_origins_env.split(',') if o.strip()]

# =======================================================================
# Django REST Framework configuration
# =======================================================================
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
}

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'

# CockroachDB stores BigAutoField as 64-bit integer with DEFAULT unique_rowid()
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
