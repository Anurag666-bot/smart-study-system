import csv
import io
import json
import os
import time
from datetime import date, datetime, timedelta, timezone as dt_timezone
from functools import wraps

import magic              # MIME type validation
import PyPDF2             # PDF text extraction

from django import forms
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import get_valid_filename
from django.views.decorators.http import require_POST

from .models import (
    ActivityLog,
    AdminLog,
    Announcement,
    Attendance,
    EventReminder,
    Exam,
    NoteAttachment,
    TaskAttachment,
    ExamResult,
    Goal,
    Note,
    Notification,
    PlannerEvent,
    Profile,
    Role,
    StudentSubject,
    SystemSetting,
    TeacherSubject,
    StudyPlan,
    StudySession,
    Subject,
    Task,
    TaskComment,
    Topic,
    UserAchievement,
    UserRole,
)
from .policies import has_permission, permission_required
from .forms import (
    AnnouncementForm,
    AttendanceForm,
    AttachmentForm,
    EnrollmentForm,
    EventReminderForm,
    ExamForm,
    ExamResultForm,
    GoalForm,
    NoteEditForm,
    NoteForm,
    NoteImportRowForm,
    ProfileForm,
    PlannerEventForm,
    RoleAssignmentForm,
    StudyPlanForm,
    StudySessionForm,
    SubjectForm,
    SystemSettingForm,
    TaskForm,
    TaskCommentForm,
    TeacherAssignmentForm,
    TeacherAttendanceForm,
    TeacherExamResultForm,
    TaskImportRowForm,
    TopicForm,
)
from .algorithms.textrank_summary import textrank_summary
from .algorithms.tfidf_search import tfidf_search
from .algorithms.priority_scheduler import prioritize_tasks
from .services.analytics import get_student_analytics
from .services.attendance import calculate_attendance
from .services.planner import build_adaptive_plan


# ============================================================
# RATE LIMIT DECORATOR
# ============================================================

def rate_limit(key_prefix, limit=5, period=60):
    """
    Rate limit authentication-sensitive requests by client IP.

    Only POST requests consume the rate-limit budget. GET requests are
    allowed so users can continue to access the login/registration forms.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *view_args, **view_kwargs):
            if request.method != 'POST':
                return view_func(request, *view_args, **view_kwargs)

            ip = request.META.get('REMOTE_ADDR')
            if not ip:
                return view_func(request, *view_args, **view_kwargs)

            cache_key = f"rate_limit:{key_prefix}:{ip}"
            current_count = cache.get(cache_key, 0)

            if current_count >= limit:
                form = (
                    AuthenticationForm(request)
                    if view_func.__name__ == 'login_view'
                    else RegisterForm()
                )

                form.add_error(
                    None,
                    'Too many requests. Please try again later.'
                )

                template = (
                    "auth/login.html"
                    if view_func.__name__ == 'login_view'
                    else "auth/register.html"
                )

                return render(request, template, {"form": form}, status=429)

            cache.set(cache_key, current_count + 1, period)

            return view_func(request, *view_args, **view_kwargs)

        return _wrapped_view

    return decorator


# ============================================================
# REGISTER FORM
# ============================================================

class RegisterForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        min_length=3,
        strip=True,
    )
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    def clean_username(self):
        username = self.cleaned_data['username'].strip()

        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError(
                "A user with that username already exists."
            )

        return username

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "A user with that email already exists."
            )

        return email

    def clean_password(self):
        password = self.cleaned_data.get('password')

        if password:
            candidate = User(
                username=self.cleaned_data.get('username', ''),
                email=self.cleaned_data.get('email', ''),
            )

            try:
                validate_password(password, user=candidate)
            except ValidationError as exc:
                raise forms.ValidationError(exc.messages) from exc

        return password

    def clean(self):
        cleaned_data = super().clean()

        password = cleaned_data.get("password")
        confirm = cleaned_data.get("confirm_password")

        if password and confirm and password != confirm:
            self.add_error(
                'confirm_password',
                "Passwords do not match"
            )

        return cleaned_data


# ============================================================
# PUBLIC VIEWS
# ============================================================

def home_view(request):
    """Landing page — no login required."""
    return render(request, 'home.html')


@rate_limit('login', limit=5, period=60)
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.info(request, f"You are now logged in as {username}.")
                return redirect('dashboard')
            messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()

    return render(request, "auth/login.html", {"form": form})


@rate_limit('register', limit=3, period=60)
def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        username=form.cleaned_data['username'],
                        email=form.cleaned_data['email'],
                        password=form.cleaned_data['password'],
                    )
            except IntegrityError:
                # Keep account existence details out of the response and handle
                # races with the database's username constraint.
                form.add_error(
                    None,
                    'Unable to create the account with those details. '
                    'Please choose another username and try again.',
                )
            else:
                login(request, user)
                messages.success(request, 'Registration successful.')
                return redirect('dashboard')

        return render(request, 'auth/register.html', {'form': form})

    return render(request, 'auth/register.html', {'form': RegisterForm()})


@login_required
@require_POST
def logout_view(request):
    logout(request)
    return redirect('login')


# ============================================================
# DASHBOARD & USER VIEWS
# ============================================================

@login_required
def dashboard(request):
    pending_tasks = Task.objects.filter(
        user=request.user, status__in=['Pending', 'In Progress']
    ).count()
    notes_count = Note.objects.filter(user=request.user).count()
    attendance_today = Attendance.objects.filter(
        user=request.user, date=timezone.localdate()
    ).first()

    from .algorithms.study_recommendations import get_recommendation_summary
    recommendations_data = get_recommendation_summary(request.user)
    analytics_data = get_student_analytics(request.user)
    try:
        announcements = Announcement.objects.filter(is_published=True).order_by(
            '-published_at', '-created_at'
        )[:5]
    except OperationalError:
        # Keep dashboards usable until the forward announcement migration lands.
        announcements = []

    return render(request, 'dashboard/dashboard.html', {
        'pending_tasks': pending_tasks,
        'notes_count': notes_count,
        'attendance_today': attendance_today,
        'recommendations_data': recommendations_data,
        'analytics_data': analytics_data,
        'announcements': announcements,
    })


@login_required
def profile(request):
    total_notes = Note.objects.filter(user=request.user).count()
    total_tasks = Task.objects.filter(user=request.user).count()
    completed_tasks = Task.objects.filter(
        user=request.user, status='Completed'
    ).count()
    attendance_today = Attendance.objects.filter(
        user=request.user, date=timezone.localdate()
    ).first()
    is_present_today = attendance_today.is_present if attendance_today else False

    return render(request, 'dashboard/profile.html', {
        'total_notes': total_notes,
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'is_present_today': is_present_today,
    })


@login_required
def profile_edit(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated.')
            return redirect('profile')
    else:
        form = ProfileForm(instance=request.user)
    return render(request, 'dashboard/profile_edit.html', {'form': form})


@login_required
def analytics(request):
    analytics_data = get_student_analytics(request.user)
    return render(request, 'dashboard/analytics.html', {
        'analytics_data': analytics_data,
        'completed_percent': analytics_data['task_completion_percent'],
        'attendance_percent': analytics_data['attendance_percent_recent'],
    })


# ============================================================
# NOTES
# ============================================================

@login_required
def notes_list(request):
    notes = Note.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'notes/notes_list.html', {'notes': notes})


def sanitize_filename(filename):
    """Sanitize filename to prevent path traversal and collisions."""
    basename = os.path.basename(filename)
    sanitized = get_valid_filename(basename)
    timestamp = str(int(time.time()))
    name, ext = os.path.splitext(sanitized)
    if not name:
        name = "file"
    return f"{name}_{timestamp}{ext}"


@login_required
def upload_note(request):
    if request.method == 'POST':
        form = NoteForm(request.POST, request.FILES)
        if form.is_valid():
            note = form.save(commit=False)
            note.user = request.user

            # ---- File validation ----
            if note.file:
                MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
                if note.file.size > MAX_FILE_SIZE:
                    messages.error(
                        request,
                        f'File too large. Maximum size is '
                        f'{MAX_FILE_SIZE // (1024 * 1024)}MB'
                    )
                    return render(request, 'notes/upload_note.html', {'form': form})

                try:
                    note.file.seek(0)
                    file_type = magic.from_buffer(note.file.read(1024), mime=True)
                    note.file.seek(0)
                    if file_type != 'application/pdf':
                        messages.error(
                            request,
                            'Invalid file type. Only PDF files are supported '
                            'for automatic text extraction.'
                        )
                        return render(request, 'notes/upload_note.html', {'form': form})
                except Exception:
                    messages.error(
                        request,
                        'Could not validate the uploaded file. Please try again '
                        'with a readable PDF.',
                    )
                    return render(request, 'notes/upload_note.html', {'form': form})

                original_filename = note.file.name
                safe_filename = sanitize_filename(original_filename)
                if original_filename != safe_filename:
                    note.file.name = safe_filename

            # ---- PDF text extraction ----
            pdf_text = ""
            if note.file and note.file.name.lower().endswith('.pdf'):
                try:
                    note.file.seek(0)
                    pdf_reader = PyPDF2.PdfReader(note.file)
                    if len(pdf_reader.pages) == 0:
                        messages.warning(
                            request,
                            'The PDF file appears to be empty or corrupted.'
                        )
                    else:
                        for page_num, page in enumerate(pdf_reader.pages):
                            try:
                                page_text = page.extract_text()
                                if page_text:
                                    pdf_text += page_text + " "
                            except Exception as page_error:
                                messages.warning(
                                    request,
                                    f'Could not extract text from page '
                                    f'{page_num + 1}: {page_error}'
                                )
                                continue

                        if not pdf_text.strip():
                            messages.warning(
                                request,
                                'Could not extract any text from the PDF. '
                                'The file might be image-based or protected.'
                            )
                except Exception as e:
                    messages.error(
                        request,
                        'Error processing PDF file. The file might be '
                        'corrupted or password-protected.'
                    )
                    return render(request, 'notes/upload_note.html', {'form': form})

            # ---- Summary ----
            content_to_summarize = note.content
            if pdf_text and len(pdf_text.strip()) > 50:
                if note.content:
                    note.content = note.content + "\n\n" + pdf_text
                else:
                    note.content = pdf_text
                content_to_summarize = note.content

            if content_to_summarize and len(content_to_summarize.strip()) > 20:
                note.summary = textrank_summary(content_to_summarize, num_sentences=2)
            else:
                note.summary = (
                    "Content too short for summarization. Please paste at least "
                    "2-3 sentences or upload a PDF with extractable text."
                )

            note.save()
            messages.success(request, 'Note uploaded and summarized!')
            return redirect('notes_list')
    else:
        form = NoteForm()

    return render(request, 'notes/upload_note.html', {'form': form})


@login_required
def note_detail(request, note_id):
    note = get_object_or_404(Note, id=note_id, user=request.user)
    return render(request, 'notes/note_detail.html', {'note': note})


@login_required
def edit_note(request, note_id):
    note = get_object_or_404(Note, id=note_id, user=request.user)
    if request.method == 'POST':
        form = NoteEditForm(request.POST, instance=note)
        if form.is_valid():
            note = form.save(commit=False)
            if note.content and len(note.content.strip()) > 20:
                note.summary = textrank_summary(note.content, num_sentences=2)
            else:
                note.summary = (
                    'Content too short for summarization. Please paste at least '
                    '2-3 sentences.'
                )
            note.save()
            messages.success(request, 'Note updated.')
            return redirect('note_detail', note_id=note.pk)
    else:
        form = NoteEditForm(instance=note)
    return render(request, 'notes/edit_note.html', {'form': form, 'note': note})


@login_required
def note_file(request, note_id):
    """Serve an uploaded note file only to its owner or a superuser."""
    if request.method != 'GET':
        return HttpResponse(status=405)

    # Deleted notes are not downloadable through the normal media route.
    # This keeps trash access separate from active academic content.
    note = get_object_or_404(Note.objects, id=note_id)
    if note.user_id != request.user.id and not request.user.is_superuser:
        return HttpResponse(status=404)
    if not note.file:
        return HttpResponse(status=404)

    try:
        file_handle = note.file.open('rb')
    except (FileNotFoundError, OSError):
        return HttpResponse(status=404)

    filename = get_valid_filename(os.path.basename(note.file.name)) or 'note.pdf'
    response = FileResponse(file_handle, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


ATTACHMENT_MAX_BYTES = 5 * 1024 * 1024
ALLOWED_ATTACHMENT_TYPES = {
    'application/pdf',
    'text/plain',
    'image/png',
    'image/jpeg',
}


def _validated_attachment(upload):
    if not upload or upload.size > ATTACHMENT_MAX_BYTES:
        raise ValueError('Attachments must be no larger than 5 MB.')
    try:
        upload.seek(0)
        detected_type = magic.from_buffer(upload.read(2048), mime=True)
        upload.seek(0)
    except Exception as exc:
        raise ValueError('Could not validate the attachment.') from exc
    if detected_type not in ALLOWED_ATTACHMENT_TYPES:
        raise ValueError('Unsupported attachment type.')
    original_name = get_valid_filename(os.path.basename(upload.name)) or 'attachment'
    original_name = original_name[:255]
    upload.name = sanitize_filename(original_name)
    return upload, original_name, detected_type


def _attachment_response(attachment):
    try:
        file_handle = attachment.file.open('rb')
    except (FileNotFoundError, OSError):
        return HttpResponse(status=404)
    content_type = attachment.content_type if attachment.content_type in ALLOWED_ATTACHMENT_TYPES else 'application/octet-stream'
    response = FileResponse(file_handle, content_type=content_type)
    filename = get_valid_filename(attachment.original_name) or 'attachment'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def note_attachment_add(request, note_id):
    note = get_object_or_404(Note.objects, pk=note_id, user=request.user)
    if request.method == 'POST':
        form = AttachmentForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                upload, original_name, content_type = _validated_attachment(form.cleaned_data['file'])
            except ValueError as exc:
                form.add_error('file', str(exc))
            else:
                NoteAttachment.objects.create(
                    note=note,
                    file=upload,
                    original_name=original_name,
                    size=upload.size,
                    content_type=content_type,
                )
                messages.success(request, 'Attachment added.')
                return redirect('note_detail', note_id=note.pk)
    else:
        form = AttachmentForm()
    return render(request, 'notes/attachment_form.html', {
        'form': form,
        'note': note,
    })


@login_required
def note_attachment_file(request, attachment_id):
    attachment = get_object_or_404(
        NoteAttachment.objects.select_related('note'),
        pk=attachment_id,
        note__user=request.user,
        note__is_deleted=False,
    )
    if request.method != 'GET':
        return HttpResponse(status=405)
    return _attachment_response(attachment)


@login_required
@require_POST
def note_attachment_delete(request, attachment_id):
    attachment = get_object_or_404(
        NoteAttachment.objects.select_related('note'),
        pk=attachment_id,
        note__user=request.user,
    )
    note_id = attachment.note_id
    attachment.file.delete(save=False)
    attachment.delete()
    messages.success(request, 'Attachment deleted.')
    return redirect('note_detail', note_id=note_id)


@login_required
def search_notes(request):
    query = request.GET.get('q')
    results = []
    if query:
        user_notes = list(Note.objects.filter(user=request.user))
        docs = [note.content for note in user_notes]
        ids = [note.id for note in user_notes]
        notes_by_id = {note.id: note for note in user_notes}
        ranked = tfidf_search(query, docs, ids)
        results = [
            notes_by_id[doc_id]
            for doc_id, score in ranked
            if score > 0 and doc_id in notes_by_id
        ]
    return render(request, 'notes/notes_list.html', {
        'notes': results,
        'search_query': query,
    })


# ============================================================
# TASKS
# ============================================================

@login_required
def task_list(request):
    tasks = Task.objects.filter(user=request.user).select_related('subject').order_by('due_date')
    today = timezone.localdate()
    prioritized = prioritize_tasks(tasks, today=today)
    return render(request, 'tasks/task_list.html', {
        'tasks': prioritized,
        'today': today,
    })


@login_required
def add_task(request):
    if request.method == 'POST':
        form = TaskForm(request.POST)
        _set_subject_scope(form, request.user)
        if form.is_valid():
            task = form.save(commit=False)
            task.user = request.user
            task.save()
            messages.success(request, 'Task added!')
            return redirect('task_list')
    else:
        form = TaskForm()
        _set_subject_scope(form, request.user)
    return render(request, 'tasks/add_task.html', {'form': form})


@login_required
def edit_task(request, task_id):
    task = get_object_or_404(Task, id=task_id, user=request.user)
    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task)
        _set_subject_scope(form, request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Task updated!')
            return redirect('task_list')
    else:
        form = TaskForm(instance=task)
        _set_subject_scope(form, request.user)
    return render(request, 'tasks/edit_task.html', {'form': form, 'task': task})


@login_required
def task_detail(request, task_id):
    task = get_object_or_404(
        Task.objects.select_related('subject'),
        pk=task_id,
        user=request.user,
    )
    if request.method == 'POST':
        form = TaskCommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.task = task
            comment.author = request.user
            comment.save()
            messages.success(request, 'Comment added.')
            return redirect('task_detail', task_id=task.pk)
    else:
        form = TaskCommentForm()
    comments = task.comments.select_related('author').all()
    return render(request, 'tasks/task_detail.html', {
        'task': task,
        'comments': comments,
        'form': form,
    })


@login_required
@require_POST
def task_comment_delete(request, comment_id):
    comment = get_object_or_404(
        TaskComment.objects.filter(
            Q(author=request.user) | Q(task__user=request.user)
        ).select_related('task'),
        pk=comment_id,
    )
    task_id = comment.task_id
    comment.delete()
    messages.success(request, 'Comment deleted.')
    return redirect('task_detail', task_id=task_id)


@login_required
def task_attachment_add(request, task_id):
    task = get_object_or_404(Task.objects, pk=task_id, user=request.user)
    if request.method == 'POST':
        form = AttachmentForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                upload, original_name, content_type = _validated_attachment(form.cleaned_data['file'])
            except ValueError as exc:
                form.add_error('file', str(exc))
            else:
                TaskAttachment.objects.create(
                    task=task,
                    uploaded_by=request.user,
                    file=upload,
                    original_name=original_name,
                    size=upload.size,
                    content_type=content_type,
                )
                messages.success(request, 'Attachment added.')
                return redirect('task_detail', task_id=task.pk)
    else:
        form = AttachmentForm()
    return render(request, 'tasks/attachment_form.html', {
        'form': form,
        'task': task,
    })


@login_required
def task_attachment_file(request, attachment_id):
    attachment = get_object_or_404(
        TaskAttachment.objects.select_related('task'),
        pk=attachment_id,
        task__user=request.user,
    )
    if request.method != 'GET':
        return HttpResponse(status=405)
    return _attachment_response(attachment)


@login_required
@require_POST
def task_attachment_delete(request, attachment_id):
    attachment = get_object_or_404(
        TaskAttachment.objects.select_related('task'),
        pk=attachment_id,
        task__user=request.user,
    )
    task_id = attachment.task_id
    attachment.file.delete(save=False)
    attachment.delete()
    messages.success(request, 'Attachment deleted.')
    return redirect('task_detail', task_id=task_id)


# ============================================================
# PLANNER
# ============================================================

@login_required
def planner(request):
    if request.method == 'POST':
        form = StudyPlanForm(request.POST)
        if form.is_valid():
            plan = form.save(commit=False)
            plan.user = request.user
            plan.save()
            messages.success(request, 'Study plan added!')
            return redirect('planner')
    else:
        form = StudyPlanForm()

    plans = StudyPlan.objects.filter(user=request.user, is_deleted=False).order_by('-date')
    archived_plans = StudyPlan.objects.filter(
        user=request.user,
        is_deleted=True,
    ).order_by('-deleted_at')
    return render(request, 'planner/planner.html', {
        'form': form,
        'plans': plans,
        'archived_plans': archived_plans,
    })


@login_required
def study_plan_edit(request, plan_id):
    plan = get_object_or_404(StudyPlan, id=plan_id, user=request.user)
    if request.method == 'POST':
        form = StudyPlanForm(request.POST, instance=plan)
        if form.is_valid():
            form.save()
            messages.success(request, 'Study plan updated.')
            return redirect('planner')
    else:
        form = StudyPlanForm(instance=plan)
    return render(request, 'planner/study_plan_form.html', {
        'form': form,
        'plan': plan,
        'form_title': 'Edit study plan',
        'submit_label': 'Save changes',
    })


@login_required
def study_plan_delete(request, plan_id):
    plan = get_object_or_404(
        StudyPlan.objects.filter(is_deleted=False),
        id=plan_id,
        user=request.user,
    )
    if request.method == 'POST':
        plan.is_deleted = True
        plan.deleted_at = timezone.now()
        plan.save(update_fields=['is_deleted', 'deleted_at'])
        messages.success(request, 'Study plan archived.')
        return redirect('planner')
    return render(request, 'academic/confirm_delete.html', {
        'object': plan,
        'action_label': 'Archive',
        'confirmation_text': 'This hides the study plan until you restore it.',
        'cancel_url': 'planner',
    })


@login_required
def study_plan_restore(request, plan_id):
    plan = get_object_or_404(
        StudyPlan.objects.filter(is_deleted=True),
        id=plan_id,
        user=request.user,
    )
    if request.method == 'POST':
        plan.is_deleted = False
        plan.deleted_at = None
        plan.save(update_fields=['is_deleted', 'deleted_at'])
        messages.success(request, 'Study plan restored.')
        return redirect('planner')
    return render(request, 'academic/confirm_delete.html', {
        'object': plan,
        'action_label': 'Restore',
        'confirmation_text': 'Restore this study plan to your planner?',
        'cancel_url': 'planner',
    })


@login_required
def calendar_view(request):
    study_plans = StudyPlan.objects.filter(
        user=request.user,
        is_deleted=False,
    ).order_by('date')
    return render(request, 'planner/calendar.html', {'study_plans': study_plans})


# ============================================================
# ATTENDANCE
# ============================================================

@login_required
def attendance(request):
    if request.method not in {'GET', 'POST'}:
        return HttpResponse(status=405)

    today = timezone.localdate()
    record = Attendance.objects.filter(user=request.user, date=today).first()

    if request.method == 'POST':
        # Validation happens before the row is created or changed.  In
        # particular, a GET is completely read-only and has no side effects.
        if record is None:
            record = Attendance(user=request.user, date=today)
        form = AttendanceForm(request.POST, instance=record)
        _set_subject_scope(form, request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Attendance marked!')
            return redirect('attendance')
    else:
        if record is None:
            record = Attendance(user=request.user, date=today)
        form = AttendanceForm(instance=record)
        _set_subject_scope(form, request.user)

    return render(request, 'attendance/attendance.html', {
        'record': record,
        'form': form,
    })


@login_required
def attendance_report(request):
    if request.method != 'GET':
        return HttpResponse(status=405)

    today = timezone.localdate()
    raw_month = request.GET.get('month', str(today.month))
    raw_year = request.GET.get('year', str(today.year))
    try:
        month = int(raw_month)
        year = int(raw_year)
    except (TypeError, ValueError):
        return HttpResponseBadRequest('Month and year must be integers.')

    if not 1 <= month <= 12 or not 1900 <= year <= 2100:
        return HttpResponseBadRequest('Month or year is outside the supported range.')

    records = Attendance.objects.filter(
        user=request.user, date__year=year, date__month=month
    ).order_by('date')
    summary = calculate_attendance(records)
    return render(request, 'attendance/attendance_report.html', {
        'records': records,
        'total_days': summary['scheduled_classes'],
        'present_days': summary['attended_classes'],
        'percentage': summary['percentage'],
        'attendance_summary': summary,
        'month': month,
        'year': year,
    })


# ============================================================
# ADMIN PANEL
# ============================================================

def _record_admin_log(request, action, target_type, target_id='', details=None):
    """Persist an administrator action without coupling it to model signals."""
    AdminLog.objects.create(
        actor=request.user,
        action=action,
        target_type=target_type,
        target_id=str(target_id or ''),
        details=details or {},
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
    )


@permission_required('admin.dashboard.view')
def admin_dashboard(request):
    return render(request, 'adminpanel/admin_dashboard.html', {
        'total_users':       User.objects.count(),
        'total_notes':       Note.objects.count(),
        'total_tasks':       Task.objects.count(),
        'total_attendance':  Attendance.objects.count(),
        'total_study_plans': StudyPlan.objects.count(),
        'total_logs':        ActivityLog.objects.count(),
        'total_admin_logs':  AdminLog.objects.count(),
        'total_announcements': Announcement.objects.count(),
    })


@permission_required('users.manage')
def manage_users(request):
    if request.method == 'POST':
        form = RoleAssignmentForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data['user']
            role = form.cleaned_data['role']
            profile, _ = Profile.objects.get_or_create(user=user)
            assignment, created = UserRole.objects.get_or_create(
                profile=profile,
                role=role,
            )
            _record_admin_log(
                request,
                'role-assigned',
                'UserRole',
                assignment.pk,
                {'user_id': user.pk, 'role': role.code},
            )
            messages.success(request, f'Role {role.code} assigned to {user.username}.')
            return redirect('manage_users')
    else:
        form = RoleAssignmentForm()
    users = User.objects.all().prefetch_related(
        'profile__user_roles__role'
    ).order_by('-date_joined')
    return render(request, 'adminpanel/manage_users.html', {
        'users': users,
        'role_form': form,
    })


@permission_required('announcements.view')
def announcements(request):
    if request.method == 'POST':
        form = AnnouncementForm(request.POST)
        if form.is_valid():
            announcement = form.save(commit=False)
            announcement.created_by = request.user
            announcement.save()
            _record_admin_log(
                request,
                'announcement-created',
                'Announcement',
                announcement.pk,
                {'title': announcement.title},
            )
            messages.success(request, 'Announcement saved.')
            return redirect('announcements')
    else:
        form = AnnouncementForm()
    announcements_qs = Announcement.objects.all().select_related('created_by')[:100]
    return render(request, 'adminpanel/announcements.html', {
        'form': form,
        'announcements': announcements_qs,
    })


@permission_required('announcements.view')
def announcement_edit(request, announcement_id):
    announcement = get_object_or_404(Announcement, pk=announcement_id)
    if request.method == 'POST':
        form = AnnouncementForm(request.POST, instance=announcement)
        if form.is_valid():
            form.save()
            _record_admin_log(request, 'announcement-updated', 'Announcement', announcement.pk)
            messages.success(request, 'Announcement updated.')
            return redirect('announcements')
    else:
        form = AnnouncementForm(instance=announcement)
    return render(request, 'adminpanel/announcement_form.html', {
        'form': form,
        'announcement': announcement,
    })


@permission_required('announcements.view')
@require_POST
def announcement_delete(request, announcement_id):
    announcement = get_object_or_404(Announcement, pk=announcement_id)
    announcement_id = announcement.pk
    announcement.delete()
    _record_admin_log(request, 'announcement-deleted', 'Announcement', announcement_id)
    messages.success(request, 'Announcement deleted.')
    return redirect('announcements')


@permission_required('admin.dashboard.view')
def admin_settings(request):
    if request.method == 'POST':
        form = SystemSettingForm(request.POST)
        if form.is_valid():
            setting, _ = SystemSetting.objects.update_or_create(
                key=form.cleaned_data['key'],
                defaults={'value': form.cleaned_data['value'], 'updated_by': request.user},
            )
            _record_admin_log(request, 'setting-updated', 'SystemSetting', setting.pk, {'key': setting.key})
            messages.success(request, 'Setting saved.')
            return redirect('admin_settings')
    else:
        form = SystemSettingForm()
    return render(request, 'adminpanel/settings.html', {
        'form': form,
        'settings': SystemSetting.objects.select_related('updated_by').order_by('key'),
    })


@permission_required('admin.dashboard.view')
@require_POST
def admin_setting_delete(request, setting_id):
    setting = get_object_or_404(SystemSetting, pk=setting_id)
    key = setting.key
    setting.delete()
    _record_admin_log(request, 'setting-deleted', 'SystemSetting', setting_id, {'key': key})
    messages.success(request, 'Setting deleted.')
    return redirect('admin_settings')


@permission_required('admin.dashboard.view')
def admin_audit_logs(request):
    logs = AdminLog.objects.select_related('actor').order_by('-timestamp')
    page_obj = Paginator(logs, 50).get_page(request.GET.get('page'))
    return render(request, 'adminpanel/audit_logs.html', {
        'page_obj': page_obj,
        'logs': page_obj.object_list,
    })


# ============================================================
# SOFT DELETE / TRASH
# ============================================================

@login_required
def delete_note(request, note_id):
    note = get_object_or_404(Note, id=note_id, user=request.user)
    if request.method == 'POST':
        note.is_deleted = True
        note.save()
        messages.success(request, 'Note moved to trash.')
        return redirect('notes_list')
    return render(request, 'notes/delete_note.html', {'note': note})


@login_required
def delete_task(request, task_id):
    task = get_object_or_404(Task, id=task_id, user=request.user)
    if request.method == 'POST':
        task.is_deleted = True
        task.save()
        messages.success(request, 'Task moved to trash.')
        return redirect('task_list')
    return render(request, 'tasks/delete_task.html', {'task': task})


@login_required
def trash_notes(request):
    trashed_notes = Note.all_objects.filter(
        user=request.user, is_deleted=True
    ).order_by('-updated_at')
    return render(request, 'notes/trash.html', {'notes': trashed_notes})


@login_required
def trash_tasks(request):
    trashed_tasks = Task.all_objects.filter(
        user=request.user, is_deleted=True
    ).order_by('-updated_at')
    return render(request, 'tasks/trash.html', {'tasks': trashed_tasks})


@login_required
def restore_note(request, note_id):
    note = get_object_or_404(Note.all_objects, id=note_id, user=request.user)
    if request.method == 'POST':
        note.is_deleted = False
        note.save()
        messages.success(request, 'Note restored from trash.')
        return redirect('notes_list')
    return render(request, 'notes/restore_note.html', {'note': note})


@login_required
def restore_task(request, task_id):
    task = get_object_or_404(Task.all_objects, id=task_id, user=request.user)
    if request.method == 'POST':
        task.is_deleted = False
        task.save()
        messages.success(request, 'Task restored from trash.')
        return redirect('task_list')
    return render(request, 'tasks/restore_task.html', {'task': task})


@login_required
def delete_note_permanently(request, note_id):
    note = get_object_or_404(Note.all_objects, id=note_id, user=request.user)
    if request.method == 'POST':
        note_title = note.title
        note.delete()
        messages.success(request, f'Note "{note_title}" permanently deleted.')
        return redirect('trash_notes')
    return render(request, 'notes/delete_permanently.html', {'note': note})


@login_required
def delete_task_permanently(request, task_id):
    task = get_object_or_404(Task.all_objects, id=task_id, user=request.user)
    if request.method == 'POST':
        task_title = task.title
        task.delete()
        messages.success(request, f'Task "{task_title}" permanently deleted.')
        return redirect('trash_tasks')
    return render(request, 'tasks/delete_permanently.html', {'task': task})


# ============================================================
# EXPORT / IMPORT
# ============================================================

@login_required
def export_notes_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="notes.csv"'

    writer = csv.writer(response)
    writer.writerow(['Title', 'Content', 'Summary', 'Created At', 'Updated At'])

    for note in Note.objects.filter(user=request.user):
        writer.writerow([
            note.title,
            note.content,
            note.summary,
            note.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            note.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
        ])
    return response


@login_required
def export_tasks_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="tasks.csv"'

    writer = csv.writer(response)
    writer.writerow(['Title', 'Description', 'Priority', 'Status',
                     'Due Date', 'Created At'])

    for task in Task.objects.filter(user=request.user):
        writer.writerow([
            task.title,
            task.description,
            task.priority,
            task.status,
            task.due_date.strftime('%Y-%m-%d') if task.due_date else '',
            task.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        ])
    return response


@login_required
def export_notes_json(request):
    notes_data = [{
        'title': note.title,
        'content': note.content,
        'summary': note.summary,
        'created_at': note.created_at.isoformat(),
        'updated_at': note.updated_at.isoformat(),
        'file_url': (
            request.build_absolute_uri(reverse('note_file', args=[note.pk]))
            if note.file else None
        ),
    } for note in Note.objects.filter(user=request.user)]

    response = HttpResponse(
        json.dumps(notes_data, indent=2),
        content_type='application/json'
    )
    response['Content-Disposition'] = 'attachment; filename="notes.json"'
    return response


@login_required
def export_tasks_json(request):
    tasks_data = [{
        'title': task.title,
        'description': task.description,
        'priority': task.priority,
        'status': task.status,
        'due_date': task.due_date.isoformat() if task.due_date else None,
        'created_at': task.created_at.isoformat(),
        'updated_at': task.updated_at.isoformat(),
    } for task in Task.objects.filter(user=request.user)]

    response = HttpResponse(
        json.dumps(tasks_data, indent=2),
        content_type='application/json'
    )
    response['Content-Disposition'] = 'attachment; filename="tasks.json"'
    return response


MAX_IMPORT_BYTES = 5 * 1024 * 1024
MAX_IMPORT_ROWS = 1000


def _read_import_rows(upload, csv_headers):
    """Read a bounded UTF-8 CSV/JSON upload without writing any rows."""
    extension = os.path.splitext(upload.name)[1].lower()
    if extension not in {'.csv', '.json'}:
        raise ValueError('Please upload a CSV or JSON file.')
    if upload.size and upload.size > MAX_IMPORT_BYTES:
        raise ValueError('Import files must be no larger than 5 MB.')

    raw = upload.read(MAX_IMPORT_BYTES + 1)
    if len(raw) > MAX_IMPORT_BYTES:
        raise ValueError('Import files must be no larger than 5 MB.')
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise ValueError('Import files must be valid UTF-8.') from exc

    if extension == '.csv':
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames or not set(csv_headers).issubset(reader.fieldnames):
            expected = ', '.join(csv_headers)
            raise ValueError(f'CSV must include these columns: {expected}.')
        rows = []
        for row_number, row in enumerate(reader, start=1):
            if row_number > MAX_IMPORT_ROWS:
                raise ValueError(f'Imports are limited to {MAX_IMPORT_ROWS} rows.')
            rows.append(row)
        return rows, extension

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError('Invalid JSON file.') from exc
    if not isinstance(data, list):
        raise ValueError('JSON imports must be an array of objects.')
    if len(data) > MAX_IMPORT_ROWS:
        raise ValueError(f'Imports are limited to {MAX_IMPORT_ROWS} rows.')
    if not all(isinstance(row, dict) for row in data):
        raise ValueError('Every JSON import row must be an object.')
    return data, extension


def _form_error_text(form):
    return '; '.join(
        f'{field}: {error}'
        for field, errors in form.errors.items()
        for error in errors
    )


def _validate_import_rows(rows, row_form, normalizer):
    """Return cleaned rows, or raise before any database write occurs."""
    cleaned = []
    errors = []
    for row_number, row in enumerate(rows, start=1):
        form = row_form(data=normalizer(row))
        if form.is_valid():
            cleaned.append(form.cleaned_data)
        else:
            errors.append(f'Row {row_number}: {_form_error_text(form)}')
    if errors:
        raise ValueError('No records were imported. ' + ' | '.join(errors[:10]))
    return cleaned


@login_required
def import_notes(request):
    if request.method == 'POST':
        import_file = request.FILES.get('import_file')
        if not import_file:
            messages.error(request, 'Please choose a CSV or JSON file.')
        else:
            try:
                rows, _ = _read_import_rows(
                    import_file,
                    ('Title', 'Content'),
                )
                cleaned = _validate_import_rows(
                    rows,
                    NoteImportRowForm,
                    lambda row: {
                        'title': row.get('Title', row.get('title', '')),
                        'content': row.get('Content', row.get('content', '')),
                        'summary': row.get('Summary', row.get('summary', '')),
                    },
                )
                with transaction.atomic():
                    for values in cleaned:
                        Note.objects.create(user=request.user, **values)
                messages.success(
                    request,
                    f'Successfully imported {len(cleaned)} notes from {import_file.name}.',
                )
            except (ValueError, IntegrityError) as exc:
                messages.error(request, str(exc))

    return render(request, 'notes/import_notes.html')


@login_required
def import_tasks(request):
    if request.method == 'POST':
        import_file = request.FILES.get('import_file')
        if not import_file:
            messages.error(request, 'Please choose a CSV or JSON file.')
        else:
            try:
                rows, _ = _read_import_rows(
                    import_file,
                    ('Title', 'Description', 'Priority', 'Status', 'Due Date'),
                )
                cleaned = _validate_import_rows(
                    rows,
                    TaskImportRowForm,
                    lambda row: {
                        'title': row.get('Title', row.get('title', '')),
                        'description': row.get('Description', row.get('description', '')),
                        'priority': row.get('Priority', row.get('priority', '')),
                        'status': row.get('Status', row.get('status', '')),
                        'due_date': row.get('Due Date', row.get('due_date', '')),
                    },
                )
                with transaction.atomic():
                    for values in cleaned:
                        Task.objects.create(user=request.user, **values)
                messages.success(
                    request,
                    f'Successfully imported {len(cleaned)} tasks from {import_file.name}.',
                )
            except (ValueError, IntegrityError) as exc:
                messages.error(request, str(exc))

    return render(request, 'tasks/import_tasks.html')


@login_required
def activity_log(request):
    if has_permission(request.user, 'activity.read_any'):
        logs = ActivityLog.objects.all().select_related('user')
    else:
        logs = ActivityLog.objects.filter(user=request.user).select_related('user')

    paginator = Paginator(logs, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'activity/activity_log.html', {
        'page_obj': page_obj,
        'logs': page_obj.object_list,
    })


# ============================================================
# CALENDAR INTEGRATIONS
# ============================================================

def _ical_escape(value):
    """Escape RFC 5545 text values before placing them in an iCalendar line."""
    return (
        str(value or '')
        .replace('\\', '\\\\')
        .replace(';', '\\;')
        .replace(',', '\\,')
        .replace('\r\n', '\\n')
        .replace('\n', '\\n')
        .replace('\r', '\\n')
    )


@login_required
def export_calendar_ical(request):
    now_stamp = timezone.now().astimezone(dt_timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//Smart Study System//Calendar Export//EN',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        'X-WR-CALNAME:Smart Study System',
        'X-WR-TIMEZONE:UTC',
    ]

    tasks = Task.objects.filter(user=request.user).exclude(status='Completed')
    for task in tasks:
        if not task.due_date:
            continue
        priority = {'High': 1, 'Medium': 5, 'Low': 9}.get(task.priority, 5)
        lines.extend([
            'BEGIN:VEVENT',
            f'UID:task-{task.id}@smartstudy.system',
            f'DTSTAMP:{now_stamp}',
            f'DTSTART;VALUE=DATE:{task.due_date:%Y%m%d}',
            f'SUMMARY:{_ical_escape(task.title)}',
            f'DESCRIPTION:{_ical_escape(task.description or "No description")}',
            f'PRIORITY:{priority}',
            'END:VEVENT',
        ])

    for plan in StudyPlan.objects.filter(user=request.user, is_deleted=False):
        description = f'Study {plan.hours} hours for {plan.subject}. {plan.notes or ""}'
        lines.extend([
            'BEGIN:VEVENT',
            f'UID:studyplan-{plan.id}@smartstudy.system',
            f'DTSTAMP:{now_stamp}',
            f'DTSTART;VALUE=DATE:{plan.date:%Y%m%d}',
            f'SUMMARY:{_ical_escape("Study: " + plan.subject)}',
            f'DESCRIPTION:{_ical_escape(description)}',
            'END:VEVENT',
        ])

    for event in PlannerEvent.objects.filter(user=request.user, is_deleted=False):
        start = event.starts_at.astimezone(dt_timezone.utc)
        end = event.ends_at.astimezone(dt_timezone.utc)
        lines.extend([
            'BEGIN:VEVENT',
            f'UID:planner-{event.id}@smartstudy.system',
            f'DTSTAMP:{now_stamp}',
            f'DTSTART:{start:%Y%m%dT%H%M%SZ}',
            f'DTEND:{end:%Y%m%dT%H%M%SZ}',
            f'SUMMARY:{_ical_escape(event.title)}',
            f'DESCRIPTION:{_ical_escape(event.description)}',
            'END:VEVENT',
        ])

    response = HttpResponse(
        '\r\n'.join(lines + ['END:VCALENDAR', '']),
        content_type='text/calendar',
    )
    response['Content-Disposition'] = 'attachment; filename="smartstudy_calendar.ics"'
    return response


@login_required
def calendar_instructions(request):
    return render(request, 'calendar_instructions.html')


@login_required
def study_recommendations(request):
    from .algorithms.study_recommendations import get_study_recommendations
    recommendations = get_study_recommendations(request.user, limit=6)
    return render(request, 'recommendations/study_recommendations.html', {
        'recommendations': recommendations,
    })


@login_required
def adaptive_planner(request):
    if request.method not in {'GET', 'POST'}:
        return HttpResponse(status=405)
    source = request.POST if request.method == 'POST' else request.GET
    try:
        days = int(source.get('days', 7))
        available_minutes = int(source.get('available_minutes', 120))
        suggestions = build_adaptive_plan(
            request.user,
            days=days,
            available_minutes_per_day=available_minutes,
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        suggestions = []
    else:
        if request.method == 'POST' and suggestions:
            with transaction.atomic():
                StudyPlan.objects.bulk_create([
                    StudyPlan(
                        user=request.user,
                        subject=item['subject'].name,
                        hours=item['minutes'] / 60,
                        date=item['date'],
                        notes='Created from the adaptive planner: '
                              + ', '.join(item['reasons']),
                    )
                    for item in suggestions
                ])
            messages.success(request, f'Added {len(suggestions)} adaptive study blocks.')
            return redirect('planner')
    return render(request, 'planner/adaptive_planner.html', {
        'suggestions': suggestions,
        'days': days if 'days' in locals() else 7,
        'available_minutes': available_minutes if 'available_minutes' in locals() else 120,
    })


# ============================================================
# NORMALIZED ACADEMIC DOMAIN
# ============================================================

def _available_subjects(user):
    """Return the subject scope for the current role without widening access."""
    if has_permission(user, 'admin.dashboard.view'):
        return Subject.objects.filter(is_active=True)
    if has_permission(user, 'student_progress.read'):
        return Subject.objects.filter(
            is_active=True,
            teacher_assignments__teacher=user,
            teacher_assignments__is_active=True,
        ).distinct()
    return Subject.objects.filter(
        is_active=True,
        student_enrollments__student=user,
        student_enrollments__is_active=True,
    ).distinct()


def _set_subject_scope(form, user):
    if 'subject' in form.fields:
        form.fields['subject'].queryset = _available_subjects(user)


def _teacher_subjects(user):
    """Return subjects the user may manage as a teacher or administrator."""
    if has_permission(user, 'admin.dashboard.view'):
        return Subject.objects.filter(is_active=True)
    if has_permission(user, 'student_progress.read'):
        return Subject.objects.filter(
            is_active=True,
            teacher_assignments__teacher=user,
            teacher_assignments__is_active=True,
        ).distinct()
    return Subject.objects.none()


def _can_manage_exam(user, exam):
    return _teacher_subjects(user).filter(pk=exam.subject_id).exists()


def _set_teacher_attendance_scope(form, user, subject_id=None):
    subjects = _teacher_subjects(user)
    form.fields['subject'].queryset = subjects
    if subject_id:
        students = User.objects.filter(
            subject_enrollments__subject_id=subject_id,
            subject_enrollments__is_active=True,
        ).order_by('username').distinct()
    else:
        students = User.objects.none()
    form.fields['student'].queryset = students


@login_required
def teacher_student_list(request):
    if not has_permission(request.user, 'teacher.students.read'):
        return redirect('dashboard')
    enrollments = StudentSubject.objects.filter(
        subject__in=_teacher_subjects(request.user),
        is_active=True,
    ).select_related('student', 'subject').order_by('subject__name', 'student__username')
    page_obj = Paginator(enrollments, 50).get_page(request.GET.get('page'))
    return render(request, 'academic/teacher_student_list.html', {
        'page_obj': page_obj,
        'enrollments': page_obj.object_list,
    })


@login_required
def teacher_progress_report(request):
    if not has_permission(request.user, 'teacher.reports.view'):
        return redirect('dashboard')
    subjects = list(_teacher_subjects(request.user)[:100])
    reports = []
    for subject in subjects:
        student_ids = list(StudentSubject.objects.filter(
            subject=subject,
            is_active=True,
        ).values_list('student_id', flat=True)[:500])
        results = list(ExamResult.objects.filter(
            exam__subject=subject,
            student_id__in=student_ids,
        ).select_related('exam', 'student').order_by('-graded_at')[:500])
        tasks = Task.objects.filter(subject=subject, user_id__in=student_ids)
        task_total = tasks.count()
        task_completed = tasks.filter(status='Completed').count()
        attendance = Attendance.objects.filter(
            subject=subject,
            user_id__in=student_ids,
        ).order_by('-date')[:1000]
        attendance_summary = calculate_attendance(attendance)
        reports.append({
            'subject': subject,
            'student_count': len(student_ids),
            'exam_result_count': len(results),
            'exam_average': round(
                sum(result.percentage for result in results) / len(results), 2
            ) if results else None,
            'task_total': task_total,
            'task_completed': task_completed,
            'task_completion_percent': (
                round(task_completed / task_total * 100, 2) if task_total else 0.0
            ),
            'attendance': attendance_summary,
            'recent_results': results[:10],
        })
    return render(request, 'academic/teacher_progress_report.html', {
        'reports': reports,
    })


@login_required
def teacher_attendance(request):
    if not has_permission(request.user, 'attendance.manage_any'):
        return redirect('dashboard')
    subject_id = request.POST.get('subject') or request.GET.get('subject')
    form = TeacherAttendanceForm(request.POST or None, initial={
        'subject': subject_id,
        'date': timezone.localdate(),
        'status': 'PRESENT',
    })
    _set_teacher_attendance_scope(form, request.user, subject_id)
    if request.method == 'POST' and form.is_valid():
        subject = form.cleaned_data['subject']
        student = form.cleaned_data['student']
        record = Attendance.objects.filter(
            user=student,
            date=form.cleaned_data['date'],
        ).first()
        if record and record.subject_id not in (None, subject.pk):
            form.add_error(
                None,
                'This student already has a different subject attendance record for that day.',
            )
        else:
            Attendance.objects.update_or_create(
                user=student,
                date=form.cleaned_data['date'],
                defaults={
                    'subject': subject,
                    'status': form.cleaned_data['status'],
                    'remarks': form.cleaned_data['remarks'],
                },
            )
            messages.success(request, 'Attendance saved for the student.')
            return redirect('teacher_attendance')
    return render(request, 'attendance/teacher_take.html', {
        'form': form,
        'selected_subject': subject_id,
    })


@login_required
def subject_list(request):
    subjects = _available_subjects(request.user).prefetch_related('topics')
    enrolled_ids = set(
        StudentSubject.objects.filter(
            student=request.user,
            is_active=True,
        ).values_list('subject_id', flat=True)
    )
    return render(request, 'academic/subject_list.html', {
        'subjects': subjects,
        'enrolled_ids': enrolled_ids,
        'can_manage': has_permission(request.user, 'admin.dashboard.view'),
    })


@permission_required('admin.dashboard.view')
def subject_create(request):
    if request.method == 'POST':
        form = SubjectForm(request.POST)
        if form.is_valid():
            subject = form.save(commit=False)
            subject.created_by = request.user
            subject.save()
            messages.success(request, 'Subject created.')
            return redirect('subject_list')
    else:
        form = SubjectForm()
    return render(request, 'academic/subject_form.html', {'form': form, 'heading': 'Create Subject'})


@permission_required('admin.dashboard.view')
def subject_edit(request, subject_id):
    subject = get_object_or_404(Subject, pk=subject_id)
    if request.method == 'POST':
        form = SubjectForm(request.POST, instance=subject)
        if form.is_valid():
            form.save()
            messages.success(request, 'Subject updated.')
            return redirect('subject_list')
    else:
        form = SubjectForm(instance=subject)
    return render(request, 'academic/subject_form.html', {'form': form, 'heading': 'Edit Subject'})


@permission_required('admin.dashboard.view')
def subject_delete(request, subject_id):
    subject = get_object_or_404(Subject, pk=subject_id)
    if request.method == 'POST':
        subject.is_active = False
        subject.save(update_fields=['is_active', 'updated_at'])
        messages.success(request, 'Subject archived.')
        return redirect('subject_list')
    return render(request, 'academic/confirm_delete.html', {
        'object': subject,
        'cancel_url': 'subject_list',
    })


@login_required
def enrollment_list(request):
    if request.method == 'POST':
        form = EnrollmentForm(request.POST)
        form.fields['subject'].queryset = Subject.objects.filter(is_active=True)
        if form.is_valid():
            try:
                with transaction.atomic():
                    enrollment, created = StudentSubject.objects.get_or_create(
                        student=request.user,
                        subject=form.cleaned_data['subject'],
                        defaults={'is_active': True},
                    )
                    if not created and not enrollment.is_active:
                        enrollment.is_active = True
                        enrollment.save(update_fields=['is_active'])
            except IntegrityError:
                form.add_error('subject', 'You are already enrolled in that subject.')
            else:
                messages.success(request, 'Subject enrollment saved.')
                return redirect('enrollment_list')
    else:
        form = EnrollmentForm()
        form.fields['subject'].queryset = Subject.objects.filter(is_active=True)

    enrollments = StudentSubject.objects.filter(
        student=request.user,
        is_active=True,
    ).select_related('subject')
    return render(request, 'academic/enrollment_list.html', {
        'form': form,
        'enrollments': enrollments,
    })


@login_required
@require_POST
def enrollment_delete(request, enrollment_id):
    enrollment = get_object_or_404(
        StudentSubject,
        pk=enrollment_id,
        student=request.user,
    )
    enrollment.is_active = False
    enrollment.save(update_fields=['is_active'])
    messages.success(request, 'Enrollment removed.')
    return redirect('enrollment_list')


@login_required
def study_session_list(request):
    if request.method == 'POST':
        form = StudySessionForm(request.POST)
        _set_subject_scope(form, request.user)
        if form.is_valid():
            session = form.save(commit=False)
            session.user = request.user
            session.save()
            messages.success(request, 'Study session recorded.')
            return redirect('study_session_list')
    else:
        form = StudySessionForm()
        _set_subject_scope(form, request.user)
    sessions = StudySession.objects.filter(user=request.user).select_related('subject')[:100]
    return render(request, 'academic/study_session_list.html', {
        'form': form,
        'sessions': sessions,
    })


@login_required
@require_POST
def study_session_delete(request, session_id):
    session = get_object_or_404(StudySession, pk=session_id, user=request.user)
    session.delete()
    messages.success(request, 'Study session deleted.')
    return redirect('study_session_list')


@login_required
def goal_list(request):
    if request.method == 'POST':
        form = GoalForm(request.POST)
        _set_subject_scope(form, request.user)
        if form.is_valid():
            goal = form.save(commit=False)
            goal.user = request.user
            goal.save()
            messages.success(request, 'Goal created.')
            return redirect('goal_list')
    else:
        form = GoalForm()
        _set_subject_scope(form, request.user)
    goals = Goal.objects.filter(
        user=request.user,
        status__in=['ACTIVE', 'COMPLETED'],
    ).select_related('subject')
    archived_goals = Goal.objects.filter(
        user=request.user,
        status='ARCHIVED',
    ).select_related('subject')
    return render(request, 'academic/goal_list.html', {
        'form': form,
        'goals': goals,
        'archived_goals': archived_goals,
    })


@login_required
def goal_edit(request, goal_id):
    goal = get_object_or_404(Goal, pk=goal_id, user=request.user)
    if request.method == 'POST':
        form = GoalForm(request.POST, instance=goal)
        _set_subject_scope(form, request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Goal updated.')
            return redirect('goal_list')
    else:
        form = GoalForm(instance=goal)
        _set_subject_scope(form, request.user)
    return render(request, 'academic/goal_form.html', {'form': form, 'goal': goal})


@login_required
@require_POST
def goal_delete(request, goal_id):
    goal = get_object_or_404(Goal, pk=goal_id, user=request.user)
    goal.status = 'ARCHIVED'
    goal.save(update_fields=['status', 'updated_at'])
    messages.success(request, 'Goal archived.')
    return redirect('goal_list')


@login_required
@require_POST
def goal_restore(request, goal_id):
    goal = get_object_or_404(
        Goal, pk=goal_id, user=request.user, status='ARCHIVED'
    )
    goal.status = 'ACTIVE'
    goal.save(update_fields=['status', 'updated_at'])
    messages.success(request, 'Goal restored.')
    return redirect('goal_list')


@login_required
def exam_list(request):
    subjects = _available_subjects(request.user)
    exams = Exam.objects.filter(
        subject__in=subjects,
        is_archived=False,
    ).select_related('subject', 'created_by')
    results = ExamResult.objects.filter(
        student=request.user,
        exam__in=exams,
    ).select_related('exam')
    can_manage = has_permission(request.user, 'student_progress.read') or has_permission(
        request.user, 'admin.dashboard.view'
    )
    archived_exams = Exam.objects.none()
    if can_manage:
        archived_exams = Exam.objects.filter(
            subject__in=_teacher_subjects(request.user),
            is_archived=True,
        ).select_related('subject')
    return render(request, 'academic/exam_list.html', {
        'exams': exams,
        'results': results,
        'archived_exams': archived_exams,
        'can_manage': can_manage,
    })


@login_required
def exam_create(request):
    allowed = (
        has_permission(request.user, 'student_progress.read')
        or has_permission(request.user, 'admin.dashboard.view')
    )
    if not allowed:
        messages.error(request, 'Only teachers and administrators can create exams.')
        return redirect('exam_list')
    if request.method == 'POST':
        form = ExamForm(request.POST)
        _set_subject_scope(form, request.user)
        if form.is_valid():
            exam = form.save(commit=False)
            exam.created_by = request.user
            exam.save()
            messages.success(request, 'Exam created.')
            return redirect('exam_list')
    else:
        form = ExamForm()
        _set_subject_scope(form, request.user)
    return render(request, 'academic/exam_form.html', {'form': form, 'heading': 'Create Exam'})


@login_required
def exam_edit(request, exam_id):
    exam = get_object_or_404(Exam, pk=exam_id, is_archived=False)
    if not _can_manage_exam(request.user, exam):
        return redirect('exam_list')
    if request.method == 'POST':
        form = ExamForm(request.POST, instance=exam)
        _set_subject_scope(form, request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Exam updated.')
            return redirect('exam_list')
    else:
        form = ExamForm(instance=exam)
        _set_subject_scope(form, request.user)
    return render(request, 'academic/exam_form.html', {
        'form': form,
        'heading': 'Edit Exam',
    })


@login_required
def exam_delete(request, exam_id):
    exam = get_object_or_404(Exam, pk=exam_id, is_archived=False)
    if not _can_manage_exam(request.user, exam):
        return redirect('exam_list')
    if request.method == 'POST':
        exam.is_archived = True
        exam.archived_at = timezone.now()
        exam.save(update_fields=['is_archived', 'archived_at'])
        messages.success(request, 'Exam archived.')
        return redirect('exam_list')
    return render(request, 'academic/confirm_delete.html', {
        'object': exam,
        'action_label': 'Archive',
        'confirmation_text': 'This hides the exam while preserving submitted results.',
        'cancel_url': 'exam_list',
    })


@login_required
def exam_restore(request, exam_id):
    exam = get_object_or_404(Exam, pk=exam_id, is_archived=True)
    if not _can_manage_exam(request.user, exam):
        return redirect('exam_list')
    if request.method == 'POST':
        exam.is_archived = False
        exam.archived_at = None
        exam.save(update_fields=['is_archived', 'archived_at'])
        messages.success(request, 'Exam restored.')
        return redirect('exam_list')
    return render(request, 'academic/confirm_delete.html', {
        'object': exam,
        'action_label': 'Restore',
        'confirmation_text': 'Restore this exam and its results?',
        'cancel_url': 'exam_list',
    })


@login_required
def teacher_exam_results(request, exam_id):
    if not has_permission(request.user, 'student_progress.read'):
        return redirect('dashboard')
    exam = get_object_or_404(
        Exam.objects.select_related('subject').filter(is_archived=False),
        pk=exam_id,
    )
    if not _teacher_subjects(request.user).filter(pk=exam.subject_id).exists():
        raise Http404
    students = User.objects.filter(
        subject_enrollments__subject=exam.subject,
        subject_enrollments__is_active=True,
    ).order_by('username').distinct()
    results = {
        result.student_id: result
        for result in ExamResult.objects.filter(
            exam=exam,
            student__in=students,
        ).select_related('student')
    }
    student_rows = [
        {'student': student, 'result': results.get(student.pk)}
        for student in students
    ]
    return render(request, 'academic/teacher_exam_results.html', {
        'exam': exam,
        'student_rows': student_rows,
        'can_edit': has_permission(request.user, 'exam_results.manage'),
    })


@login_required
def teacher_exam_result_edit(request, exam_id, student_id):
    if not has_permission(request.user, 'exam_results.manage'):
        return redirect('dashboard')
    exam = get_object_or_404(
        Exam.objects.select_related('subject').filter(is_archived=False),
        pk=exam_id,
    )
    if not _teacher_subjects(request.user).filter(pk=exam.subject_id).exists():
        raise Http404
    student_queryset = User.objects.filter(
        subject_enrollments__subject=exam.subject,
        subject_enrollments__is_active=True,
    ).order_by('username').distinct()
    student = get_object_or_404(student_queryset, pk=student_id)
    result = ExamResult.objects.filter(exam=exam, student=student).first()
    if request.method == 'POST':
        form = TeacherExamResultForm(
            request.POST,
            instance=result,
            exam=exam,
            student_queryset=student_queryset,
            initial={'student': student.pk},
        )
        if form.is_valid():
            result = form.save(commit=False)
            result.exam = exam
            result.student = student
            result.full_clean()
            result.save()
            messages.success(request, 'Exam result saved for the student.')
            return redirect('teacher_student_list')
    else:
        form = TeacherExamResultForm(
            instance=result,
            exam=exam,
            student_queryset=student_queryset,
            initial={'student': student.pk},
        )
    form.fields['student'].disabled = True
    return render(request, 'academic/teacher_exam_result_form.html', {
        'form': form,
        'exam': exam,
        'student': student,
    })


@login_required
def exam_result_create(request, exam_id):
    exam = get_object_or_404(
        Exam.objects.select_related('subject').filter(is_archived=False),
        pk=exam_id,
    )
    if not _available_subjects(request.user).filter(pk=exam.subject_id).exists():
        raise Http404

    existing = ExamResult.objects.filter(exam=exam, student=request.user).first()
    if request.method == 'POST':
        form = ExamResultForm(request.POST, instance=existing)
        form.fields['exam'].queryset = Exam.objects.filter(pk=exam.pk)
        if form.is_valid():
            result = form.save(commit=False)
            result.exam = exam
            result.student = request.user
            result.full_clean()
            result.save()
            messages.success(request, 'Exam result saved.')
            return redirect('exam_list')
    else:
        form = ExamResultForm(instance=existing, initial={'exam': exam.pk})
        form.fields['exam'].queryset = Exam.objects.filter(pk=exam.pk)
    return render(request, 'academic/exam_result_form.html', {'form': form, 'exam': exam})


@login_required
def notification_list(request):
    notifications = Notification.objects.filter(user=request.user)
    paginator = Paginator(notifications, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'academic/notification_list.html', {
        'notifications': page_obj.object_list,
        'page_obj': page_obj,
    })


@login_required
@require_POST
def notification_mark_read(request, notification_id):
    notification = get_object_or_404(Notification, pk=notification_id, user=request.user)
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=['read_at'])
    next_url = request.POST.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect('notification_list')


@login_required
def achievement_list(request):
    awards = UserAchievement.objects.filter(
        user=request.user,
    ).select_related('achievement').order_by('-awarded_at')
    return render(request, 'academic/achievement_list.html', {'awards': awards})


@login_required
def planner_event_list(request):
    if request.method == 'POST':
        form = PlannerEventForm(request.POST)
        _set_subject_scope(form, request.user)
        if form.is_valid():
            event = form.save(commit=False)
            event.user = request.user
            event.save()
            messages.success(request, 'Planner event created.')
            return redirect('planner_event_list')
    else:
        form = PlannerEventForm()
        _set_subject_scope(form, request.user)
    events = PlannerEvent.objects.filter(
        user=request.user,
        is_deleted=False,
    ).select_related('subject').prefetch_related('reminders')
    archived_events = PlannerEvent.objects.filter(
        user=request.user,
        is_deleted=True,
    ).select_related('subject')
    return render(request, 'academic/planner_event_list.html', {
        'form': form,
        'events': events,
        'archived_events': archived_events,
        'reminder_form': EventReminderForm(),
    })


@login_required
def planner_event_edit(request, event_id):
    event = get_object_or_404(
        PlannerEvent, pk=event_id, user=request.user, is_deleted=False
    )
    if request.method == 'POST':
        form = PlannerEventForm(request.POST, instance=event)
        _set_subject_scope(form, request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Planner event updated.')
            return redirect('planner_event_list')
    else:
        form = PlannerEventForm(instance=event)
        _set_subject_scope(form, request.user)
    return render(request, 'academic/planner_event_form.html', {'form': form, 'event': event})


@login_required
@require_POST
def planner_event_reminder_add(request, event_id):
    event = get_object_or_404(
        PlannerEvent,
        pk=event_id,
        user=request.user,
        is_deleted=False,
    )
    form = EventReminderForm(request.POST)
    if form.is_valid():
        remind_at = form.cleaned_data['remind_at']
        if remind_at <= timezone.now():
            form.add_error('remind_at', 'Reminder time must be in the future.')
        elif remind_at >= event.starts_at:
            form.add_error('remind_at', 'Reminder time must be before the event starts.')
        else:
            reminder, created = EventReminder.objects.get_or_create(
                event=event,
                remind_at=remind_at,
            )
            if created:
                messages.success(request, 'Event reminder added.')
            else:
                messages.info(request, 'That reminder already exists.')
            return redirect('planner_event_list')
    if form.errors:
        messages.error(
            request,
            '; '.join(
                str(error)
                for errors in form.errors.values()
                for error in errors
            ),
        )
    return redirect('planner_event_list')


@login_required
@require_POST
def planner_event_reminder_delete(request, reminder_id):
    reminder = get_object_or_404(
        EventReminder.objects.select_related('event'),
        pk=reminder_id,
        event__user=request.user,
    )
    reminder.delete()
    messages.success(request, 'Event reminder removed.')
    return redirect('planner_event_list')


@login_required
@require_POST
def planner_event_delete(request, event_id):
    event = get_object_or_404(
        PlannerEvent, pk=event_id, user=request.user, is_deleted=False
    )
    event.is_deleted = True
    event.deleted_at = timezone.now()
    event.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])
    messages.success(request, 'Planner event archived.')
    return redirect('planner_event_list')


@login_required
@require_POST
def planner_event_restore(request, event_id):
    event = get_object_or_404(
        PlannerEvent, pk=event_id, user=request.user, is_deleted=True
    )
    event.is_deleted = False
    event.deleted_at = None
    event.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])
    messages.success(request, 'Planner event restored.')
    return redirect('planner_event_list')


@permission_required('admin.dashboard.view')
def topic_create(request, subject_id):
    subject = get_object_or_404(Subject, pk=subject_id, is_active=True)
    if request.method == 'POST':
        form = TopicForm(request.POST)
        form.fields['subject'].queryset = Subject.objects.filter(pk=subject.pk)
        if form.is_valid():
            topic = form.save(commit=False)
            topic.subject = subject
            topic.save()
            messages.success(request, 'Topic created.')
            return redirect('subject_list')
    else:
        form = TopicForm(initial={'subject': subject.pk})
        form.fields['subject'].queryset = Subject.objects.filter(pk=subject.pk)
    return render(request, 'academic/topic_form.html', {
        'form': form,
        'heading': f'Add Topic to {subject.name}',
        'subject': subject,
    })


@permission_required('admin.dashboard.view')
def topic_edit(request, topic_id):
    topic = get_object_or_404(Topic.objects.select_related('subject'), pk=topic_id)
    if request.method == 'POST':
        form = TopicForm(request.POST, instance=topic)
        form.fields['subject'].queryset = Subject.objects.filter(pk=topic.subject_id)
        if form.is_valid():
            form.save()
            messages.success(request, 'Topic updated.')
            return redirect('subject_list')
    else:
        form = TopicForm(instance=topic)
        form.fields['subject'].queryset = Subject.objects.filter(pk=topic.subject_id)
    return render(request, 'academic/topic_form.html', {
        'form': form,
        'heading': 'Edit Topic',
        'subject': topic.subject,
    })


@permission_required('admin.dashboard.view')
def topic_delete(request, topic_id):
    topic = get_object_or_404(Topic.objects.select_related('subject'), pk=topic_id)
    if request.method == 'POST':
        topic.delete()
        messages.success(request, 'Topic deleted.')
        return redirect('subject_list')
    return render(request, 'academic/confirm_delete.html', {
        'object': topic,
        'action_label': 'Delete topic',
        'confirmation_text': 'This removes the topic from its subject.',
        'cancel_url': 'subject_list',
    })


@permission_required('admin.dashboard.view')
def teacher_assignment_list(request, subject_id):
    subject = get_object_or_404(Subject, pk=subject_id)
    if request.method == 'POST':
        form = TeacherAssignmentForm(request.POST)
        if form.is_valid():
            assignment, created = TeacherSubject.objects.get_or_create(
                teacher=form.cleaned_data['teacher'],
                subject=subject,
                defaults={'is_active': True},
            )
            if not created and not assignment.is_active:
                assignment.is_active = True
                assignment.save(update_fields=['is_active'])
            messages.success(request, 'Teacher assignment saved.')
            return redirect('teacher_assignment_list', subject_id=subject.pk)
    else:
        form = TeacherAssignmentForm()
    assignments = TeacherSubject.objects.filter(
        subject=subject,
        is_active=True,
    ).select_related('teacher')
    return render(request, 'academic/teacher_assignment_list.html', {
        'subject': subject,
        'form': form,
        'assignments': assignments,
    })


@permission_required('admin.dashboard.view')
@require_POST
def teacher_assignment_delete(request, assignment_id):
    assignment = get_object_or_404(TeacherSubject, pk=assignment_id)
    assignment.is_active = False
    assignment.save(update_fields=['is_active'])
    messages.success(request, 'Teacher assignment removed.')
    return redirect('teacher_assignment_list', subject_id=assignment.subject_id)
