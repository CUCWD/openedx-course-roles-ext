from __future__ import annotations

from celery import shared_task
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.http import Http404

from opaque_keys.edx.keys import CourseKey
from xmodule.modulestore.exceptions import ItemNotFoundError

from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.lib.courses import get_course_by_id

from openedx.core.djangoapps.django_comment_common.models import (
    assign_role as comment_assign_role,
    Role as CommentRole,
)
from openedx.core.djangoapps.django_comment_common.utils import (
    are_permissions_roles_seeded as comment_are_permissions_roles_seeded,
    seed_permissions_roles as comment_seed_permissions_roles,
)

from openedx_course_roles_ext.utils.discussion_roles import dedupe_forum_role
from venv import logger


def _backoff_seconds(attempt: int) -> int:
    """
    Exponential-ish backoff, capped.
    attempt starts at 1.
    """
    # 30, 60, 120, 240, 480, 600, 600, ...
    return min(30 * (2 ** max(attempt - 1, 0)), 600)


def _ensure_lms_ready(course_key: CourseKey) -> None:
    """
    Ensure LMS-derived data for the course is available.

    In Sumac reruns/imports, modulestore may already have draft/published branches,
    but LMS still returns Http404 until CourseOverview exists / course load succeeds.

    Raise CourseOverview.DoesNotExist or Http404 to trigger task retry.
    """
    # Fast check: CourseOverview should exist once LMS has indexed the course.
    if not CourseOverview.objects.filter(id=course_key).exists():
        raise CourseOverview.DoesNotExist(f"CourseOverview missing for {course_key}")

    # Stronger check: if LMS still can't load the course, treat as not-ready.
    # (This can be a little heavier; keep if you want the most reliable gating.)
    get_course_by_id(course_key)


@shared_task(bind=True, max_retries=8)
def ensure_discussion_admin_for_course_role(self, *, user_id: int, course_id_str: str) -> None:
    """
    Ensure the user has the Discussion 'Administrator' role for the course.

    Hardened for rerun/import timing:
      - retries if LMS-derived data isn't ready yet (CourseOverview / Http404)
      - retries if modulestore isn't ready (ItemNotFoundError)
      - retries if forum roles are concurrently seeded (IntegrityError / MultipleObjectsReturned)
      - repairs duplicate forum Role rows
      - idempotent
    """
    attempt = getattr(self.request, "retries", 0) + 1
    countdown = _backoff_seconds(attempt)

    course_key = CourseKey.from_string(course_id_str)
    User = get_user_model()
    user = User.objects.get(id=user_id)

    # Idempotency
    if CommentRole.user_has_role_for_course(user, course_id_str, "Administrator"):
        return

    try:
        # ✅ Gate on LMS readiness first. This is the Sumac rerun fix:
        # modulestore can have published branch, but LMS still 404s until CourseOverview exists.
        _ensure_lms_ready(course_key)

        with transaction.atomic():
            # If duplicates exist from prior concurrency issues, repair first
            dedupe_forum_role(course_id_str, "Administrator")

            # Seed forum roles once per course (may touch modulestore)
            if not comment_are_permissions_roles_seeded(course_id_str):
                comment_seed_permissions_roles(course_id_str)

            # Repair again in case seeding created duplicates under concurrency
            dedupe_forum_role(course_id_str, "Administrator")

            # Assign admin role if still missing
            if not CommentRole.user_has_role_for_course(user, course_id_str, "Administrator"):
                comment_assign_role(course_id_str, user, "Administrator")

        logger.info(
            "Ensured Discussion Admin for user=%s course=%s",
            user_id,
            course_id_str,
        )

    except (CourseOverview.DoesNotExist, Http404) as exc:
        logger.warning(
            "Course not LMS-ready yet (overview/course load); retrying discussion admin assignment. "
            "course=%s user_id=%s attempt=%s countdown=%ss err=%s",
            course_id_str,
            user_id,
            attempt,
            countdown,
            type(exc).__name__,
            exc_info=True,
        )
        raise self.retry(exc=exc, countdown=countdown)

    except ItemNotFoundError as exc:
        logger.warning(
            "Course not found in modulestore yet; retrying discussion admin assignment. "
            "course=%s user_id=%s attempt=%s countdown=%ss",
            course_id_str,
            user_id,
            attempt,
            countdown,
            exc_info=True,
        )
        raise self.retry(exc=exc, countdown=countdown)

    except (CommentRole.MultipleObjectsReturned, IntegrityError) as exc:
        logger.warning(
            "Forum role state not consistent yet; retrying discussion admin assignment. "
            "course=%s user_id=%s attempt=%s countdown=%ss err=%s",
            course_id_str,
            user_id,
            attempt,
            countdown,
            type(exc).__name__,
            exc_info=True,
        )
        raise self.retry(exc=exc, countdown=countdown)
