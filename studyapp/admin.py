from django.contrib import admin

from .models import (
    Achievement,
    AdminLog,
    Announcement,
    Attendance,
    EventReminder,
    Exam,
    ExamResult,
    Goal,
    Note,
    NoteAttachment,
    Notification,
    PlannerEvent,
    Profile,
    Role,
    StudentSubject,
    Subject,
    StudyPlan,
    StudySession,
    SystemSetting,
    Task,
    TaskAttachment,
    TaskComment,
    TeacherSubject,
    Topic,
    UserAchievement,
    UserRole,
)


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'created_at')
    search_fields = ('title', 'content')


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'priority', 'status', 'due_date', 'updated_at')
    list_filter = ('priority', 'status')
    search_fields = ('title', 'description', 'user__username')


@admin.register(NoteAttachment)
class NoteAttachmentAdmin(admin.ModelAdmin):
    list_display = ('note', 'original_name', 'size', 'content_type', 'uploaded_at')
    search_fields = ('note__title', 'original_name')
    readonly_fields = ('size', 'content_type', 'uploaded_at')
    autocomplete_fields = ('note',)


@admin.register(TaskAttachment)
class TaskAttachmentAdmin(admin.ModelAdmin):
    list_display = ('task', 'original_name', 'size', 'content_type', 'uploaded_at')
    search_fields = ('task__title', 'original_name')
    readonly_fields = ('size', 'content_type', 'uploaded_at')
    autocomplete_fields = ('task', 'uploaded_by')


@admin.register(TaskComment)
class TaskCommentAdmin(admin.ModelAdmin):
    list_display = ('task', 'author', 'created_at')
    search_fields = ('task__title', 'author__username', 'body')
    autocomplete_fields = ('task', 'author')


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'subject', 'date', 'status', 'is_present')
    list_filter = ('status', 'is_present', 'date', 'subject')
    autocomplete_fields = ('user', 'subject')


@admin.register(StudyPlan)
class StudyPlanAdmin(admin.ModelAdmin):
    list_display = ('subject', 'user', 'date', 'hours')


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at', 'updated_at')
    search_fields = ('user__username', 'user__email')


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('code', 'name')
    search_fields = ('code', 'name')


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('profile', 'role', 'assigned_at')
    list_filter = ('role',)
    search_fields = ('profile__user__username', 'role__code')
    autocomplete_fields = ('profile', 'role')


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'is_active', 'created_by', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('code', 'name')
    autocomplete_fields = ('created_by',)


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('name', 'subject', 'created_at')
    search_fields = ('name', 'subject__name')
    autocomplete_fields = ('subject',)


@admin.register(StudentSubject)
class StudentSubjectAdmin(admin.ModelAdmin):
    list_display = ('student', 'subject', 'is_active', 'enrolled_at')
    list_filter = ('is_active', 'subject')
    search_fields = ('student__username', 'subject__name')
    autocomplete_fields = ('student', 'subject')


@admin.register(TeacherSubject)
class TeacherSubjectAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'subject', 'is_active', 'assigned_at')
    list_filter = ('is_active', 'subject')
    search_fields = ('teacher__username', 'subject__name')
    autocomplete_fields = ('teacher', 'subject')


@admin.register(StudySession)
class StudySessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'subject', 'started_at', 'ended_at', 'duration_minutes')
    list_filter = ('subject',)
    search_fields = ('user__username', 'notes')
    autocomplete_fields = ('user', 'subject')


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'subject', 'target_date', 'status', 'current_value', 'target_value')
    list_filter = ('status', 'subject')
    search_fields = ('title', 'user__username')
    autocomplete_fields = ('user', 'subject')


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'points')
    search_fields = ('code', 'name')


@admin.register(UserAchievement)
class UserAchievementAdmin(admin.ModelAdmin):
    list_display = ('user', 'achievement', 'awarded_at')
    search_fields = ('user__username', 'achievement__code')
    autocomplete_fields = ('user', 'achievement')
    readonly_fields = ('awarded_at',)


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'exam_date', 'max_score', 'created_by', 'is_archived')
    list_filter = ('subject', 'exam_date', 'is_archived')
    search_fields = ('title', 'subject__name')
    autocomplete_fields = ('subject', 'created_by')


@admin.register(ExamResult)
class ExamResultAdmin(admin.ModelAdmin):
    list_display = ('exam', 'student', 'score', 'graded_at')
    search_fields = ('exam__title', 'student__username')
    autocomplete_fields = ('exam', 'student')
    readonly_fields = ('graded_at',)


@admin.register(PlannerEvent)
class PlannerEventAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'starts_at', 'ends_at', 'is_completed')
    list_filter = ('is_completed', 'subject')
    search_fields = ('title', 'user__username')
    autocomplete_fields = ('user', 'subject')


@admin.register(EventReminder)
class EventReminderAdmin(admin.ModelAdmin):
    list_display = ('event', 'remind_at', 'sent_at')
    list_filter = ('sent_at',)
    autocomplete_fields = ('event',)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'notification_type', 'title', 'read_at', 'created_at')
    list_filter = ('notification_type', 'read_at')
    search_fields = ('user__username', 'title', 'message')
    autocomplete_fields = ('user',)


@admin.register(AdminLog)
class AdminLogAdmin(admin.ModelAdmin):
    list_display = ('actor', 'action', 'target_type', 'target_id', 'timestamp')
    list_filter = ('action', 'target_type')
    search_fields = ('actor__username', 'target_type', 'target_id')
    readonly_fields = (
        'actor', 'action', 'target_type', 'target_id', 'details',
        'ip_address', 'user_agent', 'timestamp',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ('key', 'updated_by', 'updated_at')
    search_fields = ('key',)
    autocomplete_fields = ('updated_by',)


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_published', 'published_at', 'created_by', 'updated_at')
    list_filter = ('is_published',)
    search_fields = ('title', 'body')
    autocomplete_fields = ('created_by',)
