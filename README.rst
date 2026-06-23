==================
django CMS History
==================

|pypi| |build| |coverage|

**django CMS History** is an addon application to provide undo/redo functionality in `django CMS
<https://django-cms.org/>`_, by maintaining content history.

Some of the functionality in this application was previously included in django CMS itself. However, it became apparent
that some users did not want it, and some wanted functionality that worked differently.

In keeping with the django CMS philosophy of maintaining only core CMS functionality as part of the package itself,
history management was removed from django CMS in version 3.4 and has been spun off into an independent application.

django CMS History has been rewritten from the ground up. It will continue to be developed. New functionality and
improvements will be introduced in future releases.


.. note:: 

    This project is considered 3rd party (no supervision by the `django CMS Association <https://www.django-cms.org/en/about-us/>`_). Join us on `Slack                 <https://www.django-cms.org/slack/>`_ for more information.

.. image:: preview.png

*******************************************
Contribute to this project and win rewards
*******************************************

Because this is a an open-source project, we welcome everyone to
`get involved in the project <https://www.django-cms.org/en/contribute/>`_ and
`receive a reward <https://www.django-cms.org/en/bounty-program/>`_ for their contribution. 
Become part of a fantastic community and help us make django CMS the best CMS in the world.   

We'll be delighted to receive your
feedback in the form of issues and pull requests. Before submitting your
pull request, please review our `contribution guidelines
<http://docs.django-cms.org/en/latest/contributing/index.html>`_.

We're grateful to all contributors who have helped create and maintain this package.
Contributors are listed at the `contributors <https://github.com/django-cms/djangocms-history/graphs/contributors>`_
section.

Documentation
=============

See ``REQUIREMENTS`` in the `setup.py <https://github.com/divio/djangocms-history/blob/master/setup.py>`_
file for additional dependencies:

|python| |django| |djangocms|


Version support
---------------

djangocms-history 3.x supports django CMS 4.1 and later. If you are using
django CMS 3.x, use djangocms-history 2.x.

* Python: 3.9 - 3.13
* Django: 4.2 - 5.2
* django CMS: 4.1, 5.x

Installation
------------

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

Configuration
-------------

Once installed, django CMS History will make new options available to the web content manager. These will be visible in
the django CMS toolbar when managing content that is supported by the application.

djangocms-versioning
--------------------

When `djangocms-versioning <https://github.com/django-cms/djangocms-versioning>`_
is installed, undo/redo only operates on content that is editable, i.e. on
draft versions. Once a version has been published, operations recorded on
its draft can no longer be undone or redone; the toolbar buttons are
disabled and the endpoints refuse to modify the published content.

Running Tests
-------------

The test suite uses `pytest <https://docs.pytest.org/>`_ (with
``pytest-django``). You can run tests by executing::

    python -m venv env
    source env/bin/activate
    pip install -r tests/requirements/dj52_cms50.txt -e .
    pytest

Run with djangocms-versioning installed::

    pip install djangocms-versioning
    VERSIONING=1 pytest


.. |pypi| image:: https://badge.fury.io/py/djangocms-history.svg
    :target: http://badge.fury.io/py/djangocms-history
.. |build| image:: https://travis-ci.org/divio/djangocms-history.svg?branch=master
    :target: https://travis-ci.org/divio/djangocms-history
.. |coverage| image:: https://codecov.io/gh/divio/djangocms-history/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/divio/djangocms-history

.. |python| image:: https://img.shields.io/badge/python-3.9+-blue.svg
    :target: https://pypi.org/project/djangocms-history/
.. |django| image:: https://img.shields.io/badge/django-4.2%20--%205.2-blue.svg
    :target: https://www.djangoproject.com/
.. |djangocms| image:: https://img.shields.io/badge/django%20CMS-4.1%2B-blue.svg
    :target: https://www.django-cms.org/
