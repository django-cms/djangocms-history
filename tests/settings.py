#!/usr/bin/env python
HELPER_SETTINGS = {
    'INSTALLED_APPS': [
        'djangocms_history',
    ],
    'CMS_LANGUAGES': {
        1: [{
            'code': 'en',
            'name': 'English',
        }]
    },
    'LANGUAGE_CODE': 'en',
    'ALLOWED_HOSTS': ['localhost'],
}


def run():
    from app_helper import runner
    runner.cms('djangocms_history')


if __name__ == '__main__':
    run()
