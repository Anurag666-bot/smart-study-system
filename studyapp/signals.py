import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import OperationalError, ProgrammingError, transaction
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib.auth.signals import user_logged_in, user_logged_out

from .models import (
    ActivityLog,
    Note,
    NoteAttachment,
    Profile,
    Role,
    Task,
    TaskAttachment,
    UserRole,
)

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def provision_user_role(sender, instance, created, **kwargs):
    """Provision a new user's profile and one conservative default role."""
    if not created:
        return

    role_code = 'administrator' if (instance.is_staff or instance.is_superuser) else 'student'
    try:
        profile, _ = Profile.objects.get_or_create(user=instance)
        role = Role.objects.get(code=role_code)
        UserRole.objects.get_or_create(profile=profile, role=role)
    except (OperationalError, ProgrammingError, Role.DoesNotExist):
        # During a rolling deployment the role tables may not exist yet. The
        # forward data migration will provision existing users once available.
        logger.debug("Role provisioning deferred for user %s", instance.pk, exc_info=True)


@receiver(post_save, sender=Task)
def task_overdue_notification(sender, instance, created, **kwargs):
    """Best-effort, deduplicated notification for an overdue task update."""
    if created or instance.is_deleted or instance.status == 'Completed':
        return

    try:
        if not instance.is_overdue():
            return
    except Exception:
        logger.exception("Could not determine whether task %s is overdue", instance.pk)
        return

    cache_key = f"overdue-task-notification:{instance.pk}:{instance.due_date.isoformat()}"
    # ``add`` prevents repeated saves in the cache lifetime from sending mail.
    if not cache.add(cache_key, True, timeout=24 * 60 * 60):
        return

    def deliver():
        try:
            if not instance.user.email:
                logger.info("Skipping overdue notification for task %s without email", instance.pk)
                return

            html_message = render_to_string('emails/task_overdue.html', {
                'task': instance,
                'user': instance.user,
            })
            send_mail(
                subject=f'Overdue Task: {instance.title}',
                message=strip_tags(html_message),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[instance.user.email],
                html_message=html_message,
                fail_silently=False,
            )
            logger.info(
                "Overdue task notification sent for task %s to %s",
                instance.pk,
                instance.user.email,
            )
        except Exception:
            # A failed delivery must be retryable on a later save.
            cache.delete(cache_key)
            logger.exception("Failed to send overdue task notification for task %s", instance.pk)

    transaction.on_commit(deliver)


# ===== ACTIVITY LOGGING SIGNALS =====
@receiver(post_save, sender=Note)
def note_activity_logger(sender, instance, created, **kwargs):
    """Log note creation and updates."""
    action = 'CREATE' if created else 'UPDATE'
    ActivityLog.objects.create(
        user=instance.user,
        action=action,
        model_name='Note',
        object_id=instance.id,
        object_repr=str(instance),
    )


@receiver(post_save, sender=Task)
def task_activity_logger(sender, instance, created, **kwargs):
    """Log task creation and updates."""
    action = 'CREATE' if created else 'UPDATE'
    ActivityLog.objects.create(
        user=instance.user,
        action=action,
        model_name='Task',
        object_id=instance.id,
        object_repr=str(instance),
    )


@receiver(pre_delete, sender=Note)
def note_delete_logger(sender, instance, **kwargs):
    """Log note deletion."""
    ActivityLog.objects.create(
        user=instance.user,
        action='DELETE',
        model_name='Note',
        object_id=instance.id,
        object_repr=str(instance),
    )


@receiver(pre_delete, sender=Task)
def task_delete_logger(sender, instance, **kwargs):
    """Log task deletion."""
    ActivityLog.objects.create(
        user=instance.user,
        action='DELETE',
        model_name='Task',
        object_id=instance.id,
        object_repr=str(instance),
    )


@receiver(post_delete, sender=Note)
def delete_note_file(sender, instance, **kwargs):
    """Remove the legacy Note file only after its row is deleted."""
    if instance.file:
        instance.file.delete(save=False)


@receiver(post_delete, sender=NoteAttachment)
def delete_note_attachment_file(sender, instance, **kwargs):
    if instance.file:
        instance.file.delete(save=False)


@receiver(post_delete, sender=TaskAttachment)
def delete_task_attachment_file(sender, instance, **kwargs):
    if instance.file:
        instance.file.delete(save=False)


@receiver(user_logged_in)
def user_login_logger(sender, request, user, **kwargs):
    """Log a successful login."""
    if user is None:
        return
    ActivityLog.objects.create(
        user=user,
        action='LOGIN',
        model_name='User',
        object_id=user.id,
        object_repr=str(user),
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '') if request else '',
    )


@receiver(user_logged_out)
def user_logout_logger(sender, request, user, **kwargs):
    """Log a logout when Django supplies an authenticated user."""
    # Django intentionally emits this signal with user=None for anonymous logout.
    if user is None:
        return
    ActivityLog.objects.create(
        user=user,
        action='LOGOUT',
        model_name='User',
        object_id=user.id,
        object_repr=str(user),
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '') if request else '',
    )


def get_client_ip(request):
    """Get the first client IP from a request, if one is available."""
    if request is None:
        return None
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')
