from __future__ import annotations

from openedx.core.djangoapps.django_comment_common.models import Role as CommentRole
from venv import logger


def dedupe_forum_role(course_id_str: str, role_name: str) -> None:
    """
    Ensure there is only one CommentRole row for (course_id, name).
    Merge users into the kept row, delete the rest.

    NOTE: course_id_str should be str(CourseKey).
    """
    roles = list(CommentRole.objects.filter(course_id=course_id_str, name=role_name).order_by("id"))
    if len(roles) <= 1:
        return

    keep = roles[0]
    extras = roles[1:]

    # Merge users from duplicates into keep
    for r in extras:
        keep.users.add(*list(r.users.all()))

    CommentRole.objects.filter(id__in=[r.id for r in extras]).delete()
    logger.warning(
        "Deduped forum roles for course=%s name=%s kept_id=%s removed_ids=%s",
        course_id_str,
        role_name,
        keep.id,
        [r.id for r in extras],
    )
