#!/usr/bin/env python
from setuptools import find_packages, setup

from djangocms_history import __version__


REQUIREMENTS = [
    'django-cms>=4.1',
]


CLASSIFIERS = [
    'Development Status :: 5 - Production/Stable',
    'Environment :: Web Environment',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: BSD License',
    'Operating System :: OS Independent',
    'Programming Language :: Python',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.9',
    'Programming Language :: Python :: 3.10',
    'Programming Language :: Python :: 3.11',
    'Programming Language :: Python :: 3.12',
    'Programming Language :: Python :: 3.13',
    'Framework :: Django',
    'Framework :: Django :: 4.2',
    'Framework :: Django :: 5.1',
    'Framework :: Django :: 5.2',
    'Framework :: Django CMS',
    'Framework :: Django CMS :: 4.1',
    'Framework :: Django CMS :: 5.0',
    'Topic :: Internet :: WWW/HTTP',
    'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    'Topic :: Software Development',
    'Topic :: Software Development :: Libraries',
]


setup(
    name='djangocms-history',
    version=__version__,
    author='Divio AG',
    author_email='info@divio.ch',
    maintainer='Django CMS Association and contributors',
    maintainer_email='info@django-cms.org',
    url='https://github.com/django-cms/djangocms-history',
    license='BSD-3-Clause',
    description='Adds undo/redo functionality to django CMS',
    long_description=open('README.rst').read(),
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=REQUIREMENTS,
    classifiers=CLASSIFIERS,
    python_requires='>=3.9',
)
