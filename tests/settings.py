import os

SECRET_KEY = 'djangocms-history-test-key'

DEBUG = False

ALLOWED_HOSTS = ['localhost', 'testserver']

SITE_ID = 1

ROOT_URLCONF = 'tests.urls'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'treebeard',
    'sekizai',
    'cms',
    'menus',
    'djangocms_history',
    # Test plugins shipped with django CMS (LinkPlugin allows children,
    # which lets the tests build nested plugin trees without extra
    # dependencies).
    'cms.test_utils.project.pluginapp.plugins.link',
    # ArticlePlugin (manytomany_rel) provides a plugin with a ManyToMany
    # relation, used to test undo history handling of M2M changes.
    'cms.test_utils.project.pluginapp.plugins.manytomany_rel',
]

if os.environ.get('VERSIONING'):
    INSTALLED_APPS.append('djangocms_versioning')

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'cms.middleware.user.CurrentUserMiddleware',
    'cms.middleware.page.CurrentPageMiddleware',
    'cms.middleware.toolbar.ToolbarMiddleware',
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(os.path.dirname(__file__), 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.i18n',
                'sekizai.context_processors.sekizai',
                'cms.context_processors.cms_settings',
            ],
        },
    },
]

LANGUAGE_CODE = 'en'

LANGUAGES = [
    ('en', 'English'),
    ('de', 'German'),
]

CMS_LANGUAGES = {
    1: [
        {'code': 'en', 'name': 'English'},
        {'code': 'de', 'name': 'German'},
    ],
    'default': {
        'fallbacks': ['en'],
        'redirect_on_fallback': False,
        'public': True,
        'hide_untranslated': False,
    },
}

USE_TZ = True

TIME_ZONE = 'UTC'

STATIC_URL = '/static/'

CMS_TEMPLATES = [
    ('page.html', 'Page'),
]

# The link test plugin app ships without migrations; since its model
# inherits from cms.CMSPlugin (a migrated app), Django needs migrations
# for it to build the test database.
MIGRATION_MODULES = {
    'link': 'tests.link_migrations',
    'manytomany_rel': 'tests.manytomany_migrations',
}

# Required by django CMS 4.1 (ignored by django CMS 5+)
CMS_CONFIRM_VERSION4 = True

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'
