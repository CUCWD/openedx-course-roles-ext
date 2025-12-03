"""
Signal handlers for automatically managing Course Data Researcher roles.

Zendesk Ticket: https://educateworkforce.zendesk.com/agent/tickets/1384
Request came in from Choose Aerospace to automatically assign Course Data Researcher to
Limited Staff, Staff and Instructor roles upon enrollment.
"""

from venv import logger
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from common.djangoapps.student.models import CourseAccessRole
from common.djangoapps.student.roles import (
    CourseInstructorRole,
    CourseStaffRole,
    CourseLimitedStaffRole,
    CourseDataResearcherRole,
)

TRIGGER_ROLES = {
    CourseInstructorRole.ROLE,   # 'instructor'
    CourseStaffRole.ROLE,        # 'staff'
    CourseLimitedStaffRole.ROLE, # 'limited_staff'
}

DATA_RESEARCHER_ROLE = CourseDataResearcherRole.ROLE  # 'data_researcher'


def _is_course_team_role(instance: CourseAccessRole) -> bool:
    """
    True if this CourseAccessRole is a *course-level* instructor/staff/limited_staff role.

    In the classic CourseAccessRole model:
      - course-level: course_id is set (and org usually set)
      - org-level: course_id is NULL, org is set
    """
    return instance.course_id is not None and instance.role in TRIGGER_ROLES


@receiver(post_save, sender=CourseAccessRole)
def auto_add_data_researcher(sender, instance, created, **kwargs):
    """
    When a user is added as Limited Staff / Staff / Instructor for a course,
    make sure they also get Course Data Researcher for that same course.
    """
    if not created:
        return

    if not _is_course_team_role(instance):
        return

    # Already has the data researcher role for this course?
    exists = CourseAccessRole.objects.filter(
        user=instance.user,
        course_id=instance.course_id,
        role=DATA_RESEARCHER_ROLE,
    ).exists()

    if not exists:
        logger.info(
            f"Auto-adding Course Data Researcher role for user {instance.user.id} "
            f"in course {instance.course_id} due to assignment of role {instance.role}."
        )
        CourseAccessRole.objects.create(
            user=instance.user,
            course_id=instance.course_id,
            role=DATA_RESEARCHER_ROLE,
            org=instance.org,  # mirror whatever org is on the course-level role
        )


@receiver(post_delete, sender=CourseAccessRole)
def auto_remove_data_researcher(sender, instance, **kwargs):
    """
    When a Limited Staff / Staff / Instructor role is removed from a course, and the user
    no longer has *any* of those roles for that course, remove Course Data Researcher.
    """
    if not _is_course_team_role(instance):
        return

    # Does the user still have *any* course-level limited_staff/staff/instructor role?
    still_course_team = CourseAccessRole.objects.filter(
        user=instance.user,
        course_id=instance.course_id,
        role__in=TRIGGER_ROLES,
    ).exists()

    if still_course_team:
        return

    # Safe to remove data researcher for this course
    logger.info(
        f"Auto-removing Course Data Researcher role for user {instance.user.id} "
        f"in course {instance.course_id} due to removal of role {instance.role}."
    )
    CourseAccessRole.objects.filter(
        user=instance.user,
        course_id=instance.course_id,
        role=DATA_RESEARCHER_ROLE,
    ).delete()
