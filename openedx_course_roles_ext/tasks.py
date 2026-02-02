from __future__ import annotations

from celery import shared_task
from django.contrib.auth import get_user_model

from openedx.core.djangoapps.django_comment_common.models import (
    assign_role as comment_assign_role,
    Role as CommentRole,
)
from openedx.core.djangoapps.django_comment_common.utils import (
    are_permissions_roles_seeded as comment_are_permissions_roles_seeded,
    seed_permissions_roles as comment_seed_permissions_roles,
)
from xmodule.modulestore.exceptions import ItemNotFoundError

from venv import logger


def _backoff_seconds(attempt: int) -> int:
    """
    Exponential-ish backoff, capped.
    attempt starts at 1.
    """
    # 30, 60, 120, 240, 480, 600, 600, ...
    return min(30 * (2 ** max(attempt - 1, 0)), 600)


@shared_task(bind=True, max_retries=8)
def ensure_discussion_admin_for_course_role(self, *, user_id: int, course_id_str: str) -> None:
    """
    Ensure the user has the Discussion 'Administrator' role for the course.

    Runs async to avoid breaking the original save when modulestore isn't ready yet.
    Idempotent: safe to call multiple times.
    """
    User = get_user_model()
    user = User.objects.get(id=user_id)

    # Idempotency: if user already has Discussion Admin role for course, nothing to do
    if CommentRole.user_has_role_for_course(user, course_id_str, "Administrator"):
        return

    try:
        # Seed discussion roles once per course (may touch modulestore)
        if not comment_are_permissions_roles_seeded(course_id_str):
            comment_seed_permissions_roles(course_id_str)

        # Check again after seeding (still idempotent)
        if not CommentRole.user_has_role_for_course(user, course_id_str, "Administrator"):

            # Assign Discussion 'Administrator' role for the course user.
            comment_assign_role(course_id_str, user, "Administrator")

            logger.info(
                f"Auto-added Discussion Admin role for user {user.id} "
                f"in course {course_id_str} due to assignment of role Administrator."
            )

    except ItemNotFoundError as exc:
        # Course not in modulestore yet (common during import/creation timing).
        attempt = getattr(self.request, "retries", 0) + 1
        countdown = _backoff_seconds(attempt)

        logger.warning(
            "Course not found in modulestore yet; will retry discussion admin assignment. "
            "course=%s user_id=%s attempt=%s countdown=%ss",
            course_id_str,
            user_id,
            attempt,
            countdown,
            exc_info=True,
        )
        raise self.retry(exc=exc, countdown=countdown)
