import os
from pathlib import Path
import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Cargar variables de entorno desde el archivo .env al inicio
load_dotenv(BASE_DIR / ".env")


# Quick-start development settings - unsuitable for production
_INSECURE_KEY = "django-insecure-gz+enn$&4y%+8w=vv=)-uzdy^ccf29i2@67k6@)xn8wv)=qzlq"
SECRET_KEY = os.getenv("SECRET_KEY", _INSECURE_KEY)

# En desarrollo basta con no definir nada. En producción define DEBUG=False y SECRET_KEY en el .env.
DEBUG = os.getenv("DEBUG", "True") == "True"

if not DEBUG and SECRET_KEY == _INSECURE_KEY:
    raise ImproperlyConfigured("Define SECRET_KEY en el entorno cuando DEBUG=False.")

ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "crispy_forms",
    "crispy_bootstrap5",
    "corsheaders",
    "home",
    "navigation",
    "inventory",
    "accounts",
    "categorias",
    "api",
    "ventas",
    "reportes",
    "negocio",
    "proveedores",
    "compra",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.LoginRequiredMiddleware",  # Custom middleware to enforce login
]

if DEBUG:
    # Solo en desarrollo
    INSTALLED_APPS.insert(INSTALLED_APPS.index("crispy_forms"), "livereload")
    MIDDLEWARE.append("livereload.middleware.LiveReloadScript")

try:  # Archivos estáticos en producción (opcional: pip install whitenoise)
    import whitenoise  # noqa: F401
except ImportError:
    pass
else:
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

ROOT_URLCONF = "core.urls"

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
                "navigation.context_processors.menu_context",
                "accounts.context_processors.theme_context",
                "accounts.context_processors.session_timeout",
                "accounts.context_processors.permisos_context",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"


# Database
# Configuración con fallback a SQLite local si DATABASE_URL no está definida

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            ssl_require=os.getenv("DATABASE_SSL", "False") == "True",
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# Password validation

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization

LANGUAGE_CODE = "es-mx"

TIME_ZONE = "America/Mexico_City"

USE_I18N = True

USE_TZ = True

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "home:index"
LOGOUT_REDIRECT_URL = "accounts:login"
SESSION_COOKIE_AGE = 60 * 15  # 15 minutes
SESSION_SAVE_EVERY_REQUEST = True

# Static files (CSS, JavaScript, Images)

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# Seguridad en producción (con HTTPS detrás de un proxy como Nginx / DigitalOcean App Platform)
if os.getenv("USE_HTTPS", "False") == "True":
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


# Correo (alertas de stock bajo). En desarrollo los correos se imprimen en la consola.
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "BM-Core <no-responder@bm-core.local>")
