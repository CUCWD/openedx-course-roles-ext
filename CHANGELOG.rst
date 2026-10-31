Change Log
##########

..
   All enhancements and patches to openedx_course_roles_ext will be documented
   in this file.  It adheres to the structure of https://keepachangelog.com/ ,
   but in reStructuredText instead of Markdown (for ease of incorporation into
   Sphinx documentation and the PyPI description).

   This project adheres to Semantic Versioning (https://semver.org/).

.. There should always be an "Unreleased" section for changes pending release.

Unreleased
**********

*

0.4.1 – 2026-10-31
******************

Changed
========

* Defer Django, Celery, and edx-opaque-keys versions to the host edx-platform
  environment, removing the Django restriction that conflicted with Ulmo.
* Keep runtime requirements unpinned during requirements regeneration and move
  Atlas translation tooling to development dependencies.
* Document platform dependency ownership and installation guidance.

Fixed
=====

* Stabilize CI and publishing on Ubuntu 22.04 with the latest Python 3.11
  patch.
* Remove the stale Django test pin and select Django 4.2 and 5.2 through tox.
* Run standalone Django and PII checks without importing platform-dependent
  signals, while preserving production signal registration.
* Correct test middleware and template settings, and disable CI fail-fast so
  all jobs report their results.
* Resolve quality checks and documentation builds with targeted handling of
  platform-only imports, formatting and docstring fixes, and corrected
  documentation inventory URLs.

0.1.0 – 2025-11-21
**********************************************

Added
=====

* First release on PyPI.
