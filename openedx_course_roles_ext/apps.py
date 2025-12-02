"""
openedx_course_roles_ext Django application initialization.
"""

from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class OpenedxCourseRolesExtConfig(AppConfig):
    """
    Configuration for the openedx_course_roles_ext Django application.
    """

    name = 'openedx_course_roles_ext'
    label = 'openedx_course_roles_ext'
    verbose_name = "Open edX Course Roles Extension"

    def ready(self):
        """
        Import signal handlers to ensure they are registered.
        """
        from . import signals

        logger.info("openedx_course_roles_ext application is ready.")
