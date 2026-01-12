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

from openedx.core.djangoapps.django_comment_common.models import assign_role as comment_assign_role, Role as CommentRole
from openedx.core.djangoapps.django_comment_common.utils import seed_permissions_roles as comment_seed_permissions_roles, are_permissions_roles_seeded as comment_are_permissions_roles_seeded

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


@receiver(post_save, sender=CourseAccessRole)
def auto_add_discussion_admin(sender, instance, created, **kwargs):
    """
    When a user is added as Limited Staff / Staff / Instructor for a course,
    make sure they also get Discussion Admins for that same course.

    This is needed to ensure that course team members have proper permissions
    when viewing course discussions as well as
    `Instructor Dashboard > Gradebook > Filter > Cohort` dropdown is selectable.
    """
    if not created:
        return

    if not _is_course_team_role(instance):
        return

    # Already has the Discussion Admin role for this course?
    exists = CommentRole.user_has_role_for_course(
        instance.user,
        instance.course_id,
        "Administrator",
    )

    if not exists:
        logger.info(
            f"Auto-adding Discussion Admin role for user {instance.user.id} "
            f"in course {instance.course_id} due to assignment of role {instance.role}."
        )

        # Ensure discussion roles exist for this course (only needed once per course)
        if not comment_are_permissions_roles_seeded(str(instance.course_id)):
            comment_seed_permissions_roles(instance.course_id)

        # Assign Discussion Admin
        comment_assign_role(instance.course_id, instance.user, "Administrator")


@receiver(post_delete, sender=CourseAccessRole)
def auto_remove_discussion_admin(sender, instance, **kwargs):
    """
    When a Limited Staff / Staff / Instructor role is removed from a course, and the user
    no longer has *any* of those roles for that course, remove Course Discussion Admin.
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

    # Safe to remove Discussion Admin for this course
    logger.info(
        f"Auto-removing Discussion Admin role for user {instance.user.id} "
        f"in course {instance.course_id} due to removal of role {instance.role}."
    )

    # Remove Discussion Admin
    CommentRole.objects.filter(
        users=instance.user,
        course_id=instance.course_id,
        name__in=["Administrator"],
    ).delete()