"""Application configuration for checks outside edx-platform."""

from openedx_course_roles_ext.apps import OpenedxCourseRolesExtConfig


class StandaloneCourseRolesConfig(OpenedxCourseRolesExtConfig):
    """Load plugin models without platform-dependent signal handlers."""

    def ready(self):
        """Skip signal registration, which requires an edx-platform installation."""
