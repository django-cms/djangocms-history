=========
Changelog
=========

3.0.0 (2026-07-08)
==================

* Added support for django CMS 4.1 and 5.x
* Added support for Python 3.13 and Django 5.2/6.0/6.1
* Dropped support for django CMS 3.x (use djangocms-history 2.x instead)
* Dropped support for Python < 3.9 and Django < 4.2
* Plugin snapshots now store the global plugin positions introduced in
  django CMS 4. Existing history records cannot be replayed against the
  new plugin tree and are **deleted** when migrating to this version.
* Undo/redo now refuses to modify content that is not editable. With
  djangocms-versioning installed, this prevents operations recorded on a
  draft from corrupting the version after it has been published; the
  toolbar buttons are disabled accordingly.
* On django CMS 5.1 and later, undo/redo updates the structure board in place
  (via the data bridge returned by the endpoints) instead of reloading the
  page. Earlier versions automatically fall back to a full page reload.
* Operations are now matched by a canonical object identifier
  (``<content_type_id>:<object_id>``) rather than the request path, so the
  undo/redo state is consistent across the edit, preview and structure
  endpoints of the same object.
* Changing a plugin that has a many-to-many relation clears the undo history
  for that content, because such a change cannot be reliably undone.
* Operations are no longer retired when a page is moved, deleted or its
  translation removed (these are cleaned up by the 24h window instead).
* Operations that are retired from undo/redo (for example when superseded or
  replaced by a new editing session) are now
  **deleted** by default instead of being kept forever with
  ``is_archived=True``. Set ``DJANGOCMS_HISTORY_ARCHIVE_OPERATIONS = True`` to
  restore the previous archiving behaviour.
* Session identifiers are stored as fixed-length hashes, allowing session
  backends such as signed cookies to use keys longer than 120 characters.
* Deleting a user now safely cascades through their history records without
  requiring explicit history deletion permission.
* Added a ``purge_archived_operations`` management command to delete archived
  operations (supports ``--days`` and ``--dry-run``).
* The undo/redo replay logic was rewritten for the position-based plugin
  tree of django CMS 4/5 and no longer relies on the (unreliable) order
  data sent by the placeholder operation signals
  (https://github.com/django-cms/django-cms/issues/8668).
* Removed ``djangocms_history.compat``
* Removed ``djangocms_history.cms_plugins`` (the ``action_options``
  monkeypatch is obsolete since django CMS 3.5)
* Removed ``djangocms_history.helpers.disable_cms_plugin_signals``
* The test suite was rewritten to drive the real django CMS placeholder
  endpoints, and now runs on ``pytest`` / ``pytest-django``
* Packaging moved to ``pyproject.toml`` (``setup.py`` removed)

2.2.3 (2023-09-08)
==================

* Fix: allow undo/redo for plugins that use django-entangled reference conventions
* Fix: Some browsers showed a "borken image" in the undo/redo buttons  (svandeneertwegh)

2.2.2 (2023-08-31)
=================

* Support django dark mode starting with django CMS 3.11.4 (svandeneertwegh)
* Fix: Unpin django-treebeard

2.1.0 (2022-08-19)
==================

* Added support for Django 4.0


2.0.0 (2020-09-02)
==================

* Added support for Django 3.1
* Dropped support for Python 2.7 and Python 3.4
* Dropped support for Django < 2.2


1.2.0 (2020-04-21)
==================

* Added support for Django 3.0
* Added support for Python 3.8


1.1.0 (2019-05-23)
==================

* Added support for Django 2.2 and django CMS 3.7
* Removed support for Django 2.0
* Extended test matrix
* Make sure placeholder operations are not shown in the admin
* Added isort and adapted imports
* Adapted code base to align with other supported addons
* Added translations


1.0.0 (2018-12-17)
==================

* Added support for Django 2.0 and 2.1
* Cleaned up file structure
* Added proper test setup


0.6.0 (2018-11-14)
==================

* Added support for Django 1.11
* Removed support for Django<1.11
