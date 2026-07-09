"""
ねこのひげ - Django settings
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "tracker",
]

# settings.py
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # ★追加：これより下のビューは全てログイン必須になる
    #   必ず AuthenticationMiddleware の「後ろ」に置くこと
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {    
         "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "ja"
TIME_ZONE = "Asia/Tokyo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

import os

# --- 本番/ローカル切り替え（環境変数で制御）---
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-CHANGE-ME-IN-PRODUCTION"
)
        
DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"

# Azureのドメインを許可（当日のApp Service名に合わせる）
ALLOWED_HOSTS = os.environ.get(
        "DJANGO_ALLOWED_HOSTS",
        "127.0.0.1,localhost"
).split(",")

ALLOWED_HOSTS = ["*"]

# CSRF（Django 4.0+ はHTTPS本番で必須になりがち）
CSRF_TRUSTED_ORIGINS = [
    h for h in os.environ.get("DJANGO_CSRF_TRUSTED", "").split(",") if h
]

CSRF_TRUSTED_ORIGINS = ["https://nekonohige01.azurewebsites.net"]

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# 静的ファイル設定（STATIC_URL は既にあるはず、その下に追加）
STATICFILES_DIRS = [BASE_DIR / "static"]

# config/settings.py（末尾あたりに追記）

# ログイン関連のリダイレクト先設定
LOGIN_URL = 'tracker:landing'           # 未ログイン → LP
LOGIN_REDIRECT_URL = 'tracker:home'     # ログイン成功後 → ホーム
LOGOUT_REDIRECT_URL = 'tracker:landing' # ログアウト後 → LP

# ===== ログイン状態の維持 =====
SESSION_EXPIRE_AT_BROWSER_CLOSE = False        # ブラウザを閉じても維持
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14         # 14日間（秒）

