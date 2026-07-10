==================
django CMS History
==================

|pypi| |coverage| |python| |django| |djangocms|

**django CMS History** is an addon application to provide undo/redo functionality in `django CMS
<https://django-cms.org/>`_, by maintaining content history.

django CMS History has been rewritten from the ground up. It will continue to be developed. New functionality and
improvements will be introduced in future releases.


.. image:: preview.jpg

Version support
===============

djangocms-history 3.x supports Python 3.9 through 3.13, Django 4.2, 5.2, 6.0
and 6.1, and django CMS 4.1, 5.0 and 5.1. **If you are using django CMS 3.x,
use djangocms-history 2.x.**

The supported Python, Django and django CMS versions are shown by the badges at the top of this page (latest
release read directly from the published PyPI classifiers). The latest supported versions of the master branch
are declared in ``pyproject.toml``; the tested combinations are defined in
``tox.ini`` and ``tests/requirements``.

Installation
============

For a manual install:

* run ``pip install djangocms-history``
* add ``djangocms_history`` to your ``INSTALLED_APPS``
* run ``python manage.py migrate djangocms_history``

.. warning::

    Upgrading from djangocms-history 2.x: history records created with
    django CMS 3.x cannot be replayed against the plugin tree of
    django CMS 4 and later. All existing history records are deleted by
    the migrations of version 3.0. Since the undo window is 24 hours,
    this only affects operations performed right before the upgrade.

Usage
=====

Once installed, django CMS History will make new options available to the frontend editor. These will be visible in
the django CMS toolbar when managing content that is supported by the application.

In-place updates
----------------

On django CMS 5.1 and later, undo and redo update the structure board in place
(through the data bridge the endpoints return), preserving scroll position and
board state. On earlier versions the page is reloaded after each undo/redo
instead.

History scope and limitations
-----------------------------

History records plugin operations rather than arbitrary model or page changes.
Undo/redo is available for the last 24 hours and for one content origin per
user session. Editing another page supersedes the previous page's history;
another user's edit supersedes history only when it affects the same content.
Changing a plugin with a many-to-many relation clears the history for that
content because the change cannot be restored reliably.

Operations older than 24 hours are ignored, but age alone does not immediately
delete or archive their database rows. Superseded operations and operations
from an earlier login session are retired when the corresponding cleanup path
runs.

Configuration
=============

Archiving retired operations
----------------------------

By default retired operations are **deleted** outright. If you would rather
retain them for inspection, enable archiving::

    DJANGOCMS_HISTORY_ARCHIVE_OPERATIONS = True

Archived operations are flagged with ``is_archived=True`` and are still never
used by undo/redo. They are not durable audit records: deleting related users,
placeholders or other referenced content may delete them through database
cascades. To remove archived operations later and reclaim database space, run::

    python manage.py purge_archived_operations

The command supports ``--days N`` (only purge archived operations older than
``N`` days) and ``--dry-run`` (report what would be deleted without deleting).

Integrations
============

djangocms-versioning
--------------------

When `djangocms-versioning <https://github.com/django-cms/djangocms-versioning>`_
is installed, undo/redo only operates on content that is editable, i.e. on
draft versions. Once a version has been published, operations recorded on
its draft can no longer be undone or redone; the toolbar buttons are
disabled and the endpoints refuse to modify the published content.

Running tests
=============

The test suite uses `pytest <https://docs.pytest.org/>`_ (with
``pytest-django``). You can run tests by executing::

    python -m venv env
    source env/bin/activate
    pip install -r tests/requirements/dj52_cms50.txt -e .
    pytest

Run with djangocms-versioning installed::

    pip install djangocms-versioning
    VERSIONING=1 pytest

Contributing
============

Because this is an open-source project, we welcome everyone to
`get involved in the project <https://www.django-cms.org/en/contribute/>`_ and
`receive a reward <https://www.django-cms.org/en/bounty-program/>`_ for their contribution.
Become part of a fantastic community and help us make django CMS the best CMS in the world.

We'll be delighted to receive your
feedback in the form of issues and pull requests. Before submitting your
pull request, please review our `contribution guidelines
<https://docs.django-cms.org/en/latest/contributing/index.html>`_.

We're grateful to all contributors who have helped create and maintain this package.
Contributors are listed in the `contributors <https://github.com/django-cms/djangocms-history/graphs/contributors>`_
section.


.. |pypi| image:: https://badge.fury.io/py/djangocms-history.svg
    :target: http://badge.fury.io/py/djangocms-history
.. |coverage| image:: https://codecov.io/gh/django-cms/djangocms-history/graph/badge.svg
    :target: https://codecov.io/gh/django-cms/djangocms-history

.. |python| image:: https://img.shields.io/pypi/pyversions/djangocms-history
    :alt: PyPI - Python Version
    :target: https://pypi.org/project/djangocms-history/
.. |django| image:: https://img.shields.io/pypi/frameworkversions/django/djangocms-history
    :alt: PyPI - Django Versions from Framework Classifiers
    :target: https://www.djangoproject.com/
.. |djangocms| image:: https://img.shields.io/pypi/frameworkversions/django-cms/djangocms-history
    :alt: PyPI - django CMS Versions from Framework Classifiers
    :target: https://www.django-cms.org/
