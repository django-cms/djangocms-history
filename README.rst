******************
django CMS History
******************

django CMS History is an addon application to provide undo/redo functionality in `django CMS
<https://django-cms.org/>`_, by maintaining content history.

Some of the functionality in this application was previously included in django CMS itself. However, it became apparent
that some users did not want it, and some wanted functionality that worked differently.

In keeping with the django CMS philosophy of maintaining only core CMS functionality as part of the package itself,
history management was removed from django CMS in version 3.4 and has been spun off into an independent application.

django CMS History has been rewritten from the ground up. It will continue to be developed. New functionality and
improvements will be introduced in future releases.

============
Installation
============

Requirements
============

django CMS history requires that you have a django CMS 3.4.2 (or higher) project already running and set up.


To install
==========

Run::

    pip install djangocms-history

Add ``djangocms_history`` to your project's ``INSTALLED_APPS``.

Run::

    python manage.py migrate djangocms_history

to perform the application's database migrations.


=====
Usage
=====

Once installed, django CMS History will make new options available to the web content manager. These will be visible in
the django CMS toolbar when managing content that is supported by the application.
