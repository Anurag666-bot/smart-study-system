from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class NoteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class Note(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notes')
    title = models.CharField(max_length=200)
    content = models.TextField()
    summary = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to='notes/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    objects = NoteManager()  # Custom manager that excludes deleted items
    all_objects = models.Manager()  # Manager that includes all items

    class Meta:
        indexes = [
            models.Index(fields=['user'], name='idx_note_user'),
            models.Index(fields=['created_at'], name='idx_note_created_at'),
        ]

    def __str__(self):
        return self.title


class NoteAttachment(models.Model):
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='notes/attachments/')
    original_name = models.CharField(max_length=255)
    size = models.PositiveIntegerField(default=0)
    content_type = models.CharField(max_length=100, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.original_name


class TaskManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class Task(models.Model):
    PRIORITY_CHOICES = [('High', 'High'), ('Medium', 'Medium'), ('Low', 'Low')]
    STATUS_CHOICES = [('Pending', 'Pending'), ('In Progress', 'In Progress'), ('Completed', 'Completed')]
    DIFFICULTY_CHOICES = [('Easy', 'Easy'), ('Medium', 'Medium'), ('Hard', 'Hard')]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks')
    subject = models.ForeignKey(
        'Subject',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='tasks',
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='Medium')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='Pending')
    due_date = models.DateField()
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='Medium')
    estimated_minutes = models.PositiveIntegerField(null=True, blank=True)
    progress = models.PositiveSmallIntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    objects = TaskManager()  # Custom manager that excludes deleted items
    all_objects = models.Manager()  # Manager that includes all items

    class Meta:
        indexes = [
            models.Index(fields=['user'], name='idx_task_user'),
            models.Index(fields=['due_date'], name='idx_task_due_date'),
            models.Index(fields=['created_at'], name='idx_task_created_at'),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(progress__gte=0) & models.Q(progress__lte=100),
                name='task_progress_0_100',
            ),
            models.CheckConstraint(
                condition=models.Q(estimated_minutes__isnull=True) | models.Q(estimated_minutes__gt=0),
                name='task_estimate_positive',
            ),
        ]

    def save(self, *args, **kwargs):
        if self.status == 'Completed' and self.completed_at is None:
            self.completed_at = timezone.now()
        elif self.status != 'Completed' and self.completed_at is not None:
            self.completed_at = None
        super().save(*args, **kwargs)

    def is_overdue(self):
        """Return whether this incomplete task is due before the local date."""
        return (
            self.due_date is not None
            and self.due_date < timezone.localdate()
            and self.status != 'Completed'
        )

    def __str__(self):
        return self.title


class TaskComment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name='task_comments',
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        indexes = [models.Index(fields=['task', 'created_at'])]

    def __str__(self):
        return f'Comment on {self.task_id} by {self.author_id}'


class TaskAttachment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='attachments')
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name='task_attachments',
    )
    file = models.FileField(upload_to='tasks/attachments/')
    original_name = models.CharField(max_length=255)
    size = models.PositiveIntegerField(default=0)
    content_type = models.CharField(max_length=100, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.original_name


class Attendance(models.Model):
    STATUS_CHOICES = [
        ('PRESENT', 'Present'),
        ('ABSENT', 'Absent'),
        ('LATE', 'Late'),
        ('EXCUSED', 'Excused'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendance')
    subject = models.ForeignKey(
        'Subject',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='attendance_records',
    )
    date = models.DateField(default=timezone.now)
    is_present = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, null=True, blank=True)
    remarks = models.CharField(max_length=100, blank=True)

    def save(self, *args, **kwargs):
        if self.status:
            self.is_present = self.status in {'PRESENT', 'LATE'}
        else:
            self.status = 'PRESENT' if self.is_present else 'ABSENT'
        super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'date'],
                condition=models.Q(subject__isnull=True),
                name='uniq_attendance_general_day',
            ),
            models.UniqueConstraint(
                fields=['user', 'date', 'subject'],
                condition=models.Q(subject__isnull=False),
                name='uniq_attendance_subject_day',
            ),
        ]
        indexes = [
            models.Index(fields=['user'], name='idx_attendance_user'),
            models.Index(fields=['date'], name='idx_attendance_date'),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.date}"


class ActivityLog(models.Model):
    ACTION_CHOICES = [
        ('CREATE', 'Created'),
        ('UPDATE', 'Updated'),
        ('DELETE', 'Deleted'),
        ('LOGIN', 'Logged In'),
        ('LOGOUT', 'Logged Out'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=50)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    object_repr = models.CharField(max_length=200)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['model_name', '-timestamp']),
        ]

    def __str__(self):
        return f"{self.user.username} {self.action} {self.model_name} {self.object_id} at {self.timestamp}"


class StudyPlan(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='study_plans')
    subject = models.CharField(max_length=100)
    hours = models.FloatField()
    date = models.DateField()
    notes = models.TextField(blank=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['user'], name='idx_studyplan_user'),
            models.Index(fields=['date'], name='idx_studyplan_date'),
        ]

    def __str__(self):
        return f"{self.subject} on {self.date}"


class Profile(models.Model):
    """Application profile kept separate from Django's identity fields."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile for {self.user.get_username()}"


class Role(models.Model):
    """Stable application role; permissions remain code-owned for now."""

    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return self.name


class UserRole(models.Model):
    """Explicit role assignment for a profile."""

    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='user_roles',
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name='user_roles',
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['profile', 'role'],
                name='uniq_profile_role',
            ),
        ]
        indexes = [
            models.Index(fields=['profile', 'role'], name='idx_userrole_profile_role'),
        ]

    def __str__(self):
        return f"{self.profile.user.get_username()} – {self.role.code}"


class Subject(models.Model):
    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='created_subjects',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [models.Index(fields=['is_active', 'name'])]

    def __str__(self):
        return f'{self.code} – {self.name}'


class Topic(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='topics')
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['subject__name', 'name']
        constraints = [
            models.UniqueConstraint(fields=['subject', 'name'], name='uniq_subject_topic'),
        ]

    def __str__(self):
        return f'{self.subject.name}: {self.name}'


class StudentSubject(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subject_enrollments',
    )
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='student_enrollments')
    enrolled_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['student', 'subject'], name='uniq_student_subject'),
        ]
        indexes = [models.Index(fields=['student', 'is_active'])]

    def __str__(self):
        return f'{self.student.get_username()} – {self.subject.name}'


class TeacherSubject(models.Model):
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subject_assignments',
    )
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='teacher_assignments')
    assigned_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['teacher', 'subject'], name='uniq_teacher_subject'),
        ]
        indexes = [models.Index(fields=['teacher', 'is_active'])]

    def __str__(self):
        return f'{self.teacher.get_username()} – {self.subject.name}'


class StudySession(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='study_sessions',
    )
    subject = models.ForeignKey(
        Subject,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='study_sessions',
    )
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-started_at']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ended_at__isnull=True) | models.Q(ended_at__gt=models.F('started_at')),
                name='session_end_after_start',
            ),
            models.CheckConstraint(
                condition=models.Q(duration_minutes__isnull=True) | models.Q(duration_minutes__gte=1),
                name='session_duration_positive',
            ),
        ]
        indexes = [models.Index(fields=['user', '-started_at'])]

    def clean(self):
        if self.ended_at and self.ended_at <= self.started_at:
            raise ValidationError({'ended_at': 'End time must be after start time.'})

    def __str__(self):
        return f'{self.user.get_username()} session at {self.started_at}'


class Goal(models.Model):
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('COMPLETED', 'Completed'),
        ('ARCHIVED', 'Archived'),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='goals',
    )
    subject = models.ForeignKey(
        Subject,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='goals',
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    target_date = models.DateField()
    target_value = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)])
    current_value = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    unit = models.CharField(max_length=40, default='units')
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='ACTIVE')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['status', 'target_date']
        constraints = [
            models.CheckConstraint(condition=models.Q(target_value__gt=0), name='goal_target_positive'),
            models.CheckConstraint(condition=models.Q(current_value__gte=0), name='goal_current_nonnegative'),
        ]
        indexes = [models.Index(fields=['user', 'status', 'target_date'])]

    def __str__(self):
        return self.title


class Achievement(models.Model):
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=150)
    description = models.TextField()
    points = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.name


class UserAchievement(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='achievements',
    )
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE, related_name='recipients')
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'achievement'], name='uniq_user_achievement'),
        ]

    def __str__(self):
        return f'{self.user.get_username()} – {self.achievement.code}'


class Exam(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='exams')
    title = models.CharField(max_length=200)
    exam_date = models.DateField()
    max_score = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0.01)])
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_exams',
    )
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['exam_date', 'title']
        indexes = [models.Index(fields=['subject', 'is_archived', 'exam_date'])]
        constraints = [
            models.CheckConstraint(condition=models.Q(max_score__gt=0), name='exam_max_score_positive'),
        ]

    def __str__(self):
        return f'{self.title} – {self.subject.name}'


class ExamResult(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='results')
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='exam_results',
    )
    score = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)])
    feedback = models.TextField(blank=True)
    graded_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['exam', 'student'], name='uniq_exam_student_result'),
            models.CheckConstraint(condition=models.Q(score__gte=0), name='exam_score_nonnegative'),
        ]

    def clean(self):
        if self.exam_id and self.score is not None and self.score > self.exam.max_score:
            raise ValidationError({'score': 'Score cannot exceed the exam maximum.'})

    @property
    def percentage(self):
        if not self.exam.max_score:
            return 0
        return round(float(self.score / self.exam.max_score * 100), 2)

    def __str__(self):
        return f'{self.student.get_username()} – {self.exam.title}'


class PlannerEvent(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='planner_events',
    )
    subject = models.ForeignKey(
        Subject,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='planner_events',
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    is_completed = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['starts_at']
        constraints = [
            models.CheckConstraint(condition=models.Q(ends_at__gt=models.F('starts_at')), name='event_end_after_start'),
        ]
        indexes = [models.Index(fields=['user', 'starts_at'])]

    def clean(self):
        if self.ends_at <= self.starts_at:
            raise ValidationError({'ends_at': 'End time must be after start time.'})

    def __str__(self):
        return self.title


class EventReminder(models.Model):
    event = models.ForeignKey(PlannerEvent, on_delete=models.CASCADE, related_name='reminders')
    remind_at = models.DateTimeField()
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['event', 'remind_at'], name='uniq_event_reminder_time'),
        ]

    def __str__(self):
        return f'Reminder for {self.event.title} at {self.remind_at}'


class Notification(models.Model):
    TYPE_CHOICES = [
        ('DEADLINE', 'Deadline'),
        ('REMINDER', 'Reminder'),
        ('ATTENDANCE', 'Attendance'),
        ('GOAL', 'Goal'),
        ('STREAK', 'Streak'),
        ('ACHIEVEMENT', 'Achievement'),
        ('SYSTEM', 'System'),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='SYSTEM')
    dedup_key = models.CharField(max_length=200, null=True, blank=True)
    title = models.CharField(max_length=200)
    message = models.TextField()
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'dedup_key'], name='uniq_user_notification_key'),
        ]
        indexes = [models.Index(fields=['user', 'read_at', '-created_at'])]

    @property
    def is_read(self):
        return self.read_at is not None

    def __str__(self):
        return f'{self.user.get_username()} – {self.title}'


class AdminLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name='admin_logs',
    )
    action = models.CharField(max_length=100)
    target_type = models.CharField(max_length=100)
    target_id = models.CharField(max_length=100, blank=True)
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [models.Index(fields=['actor', '-timestamp'])]

    def __str__(self):
        return f'{self.action} {self.target_type} {self.target_id}'


class SystemSetting(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.JSONField(default=dict)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name='updated_system_settings',
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.key


class Announcement(models.Model):
    title = models.CharField(max_length=200)
    body = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name='announcements_created',
    )
    is_published = models.BooleanField(default=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-published_at', '-created_at']
        indexes = [models.Index(fields=['is_published', '-published_at'])]

    def save(self, *args, **kwargs):
        if self.is_published and self.published_at is None:
            self.published_at = timezone.now()
        elif not self.is_published:
            self.published_at = None
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
