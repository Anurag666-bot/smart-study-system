from django import forms
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db.models import Q

from .models import (
    Attendance,
    EventReminder,
    Exam,
    ExamResult,
    Goal,
    Note,
    PlannerEvent,
    Role,
    StudentSubject,
    StudyPlan,
    StudySession,
    Subject,
    SystemSetting,
    Task,
    TaskComment,
    Topic,
    Announcement,
)


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']


class NoteForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = ['title', 'content', 'file']


class AttachmentForm(forms.Form):
    file = forms.FileField()


class NoteEditForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = ['title', 'content']


class TaskForm(forms.ModelForm):
    estimated_minutes = forms.IntegerField(required=False, min_value=1)
    progress = forms.IntegerField(min_value=0, max_value=100)

    class Meta:
        model = Task
        fields = [
            'subject', 'title', 'description', 'priority', 'status', 'due_date',
            'difficulty', 'estimated_minutes', 'progress',
        ]
        widgets = {'due_date': forms.DateInput(attrs={'type': 'date'})}


class TaskFilterForm(forms.Form):
    STATUS_CHOICES = [('','All statuses')] + list(Task.STATUS_CHOICES)
    PRIORITY_CHOICES = [('','All priorities')] + list(Task.PRIORITY_CHOICES)
    DEADLINE_CHOICES = [
        ('', 'Any deadline'),
        ('overdue', 'Overdue'),
        ('due_soon', 'Due soon'),
        ('upcoming', 'Upcoming'),
        ('no_deadline', 'No deadline'),
    ]
    SORT_CHOICES = [
        ('', 'Default ordering'),
        ('priority', 'Priority'),
        ('deadline', 'Deadline'),
        ('created', 'Created date'),
        ('workload', 'Estimated workload'),
    ]

    status = forms.ChoiceField(required=False, choices=STATUS_CHOICES)
    priority = forms.ChoiceField(required=False, choices=PRIORITY_CHOICES)
    importance = forms.ChoiceField(required=False, choices=PRIORITY_CHOICES)
    subject = forms.ModelChoiceField(required=False, queryset=Subject.objects.none(), label='Subject')
    deadline = forms.ChoiceField(required=False, choices=DEADLINE_CHOICES)
    sort = forms.ChoiceField(required=False, choices=SORT_CHOICES)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['subject'].queryset = Subject.objects.filter(
                Q(tasks__user=user) | Q(student_enrollments__student=user) | Q(teacher_assignments__teacher=user)
            ).distinct().order_by('name')


class StudyPlanForm(forms.ModelForm):
    hours = forms.FloatField(validators=[MinValueValidator(0.01)])

    class Meta:
        model = StudyPlan
        fields = ['subject', 'hours', 'date', 'notes']
        widgets = {'date': forms.DateInput(attrs={'type': 'date'})}


class AttendanceForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = ['subject', 'status', 'is_present', 'remarks']

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        if status:
            cleaned_data['is_present'] = status in {'PRESENT', 'LATE'}
        else:
            cleaned_data['status'] = 'PRESENT' if cleaned_data.get('is_present') else 'ABSENT'
        return cleaned_data


class NoteImportRowForm(forms.Form):
    """Validate one normalized note row before an import transaction."""

    title = forms.CharField(max_length=200)
    content = forms.CharField()
    summary = forms.CharField(required=False, max_length=10000)


class TaskImportRowForm(forms.Form):
    """Validate one normalized task row before an import transaction."""

    title = forms.CharField(max_length=200)
    description = forms.CharField(required=False)
    priority = forms.ChoiceField(choices=Task.PRIORITY_CHOICES)
    status = forms.ChoiceField(choices=Task.STATUS_CHOICES)
    due_date = forms.DateField(input_formats=['%Y-%m-%d'])


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['code', 'name', 'description', 'is_active']


class TopicForm(forms.ModelForm):
    class Meta:
        model = Topic
        fields = ['subject', 'name', 'description']


class EnrollmentForm(forms.ModelForm):
    class Meta:
        model = StudentSubject
        fields = ['subject']


class StudySessionForm(forms.ModelForm):
    class Meta:
        model = StudySession
        fields = ['subject', 'started_at', 'ended_at', 'duration_minutes', 'notes']
        widgets = {
            'started_at': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M',
                attrs={'type': 'datetime-local'},
            ),
            'ended_at': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M',
                attrs={'type': 'datetime-local'},
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        started_at = cleaned_data.get('started_at')
        ended_at = cleaned_data.get('ended_at')
        if started_at and ended_at and ended_at <= started_at:
            self.add_error('ended_at', 'End time must be after start time.')
        return cleaned_data


class GoalForm(forms.ModelForm):
    class Meta:
        model = Goal
        fields = [
            'subject', 'title', 'description', 'target_date',
            'target_value', 'current_value', 'unit', 'status',
        ]
        widgets = {'target_date': forms.DateInput(attrs={'type': 'date'})}


class ExamForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = ['subject', 'title', 'exam_date', 'max_score']
        widgets = {'exam_date': forms.DateInput(attrs={'type': 'date'})}


class ExamResultForm(forms.ModelForm):
    class Meta:
        model = ExamResult
        fields = ['exam', 'score', 'feedback']

    def clean(self):
        cleaned_data = super().clean()
        exam = cleaned_data.get('exam')
        score = cleaned_data.get('score')
        if exam and score is not None and score > exam.max_score:
            self.add_error('score', 'Score cannot exceed the exam maximum.')
        return cleaned_data


class TeacherExamResultForm(forms.ModelForm):
    class Meta:
        model = ExamResult
        fields = ['student', 'score', 'feedback']

    def __init__(self, *args, exam=None, student_queryset=None, **kwargs):
        self.exam = exam
        super().__init__(*args, **kwargs)
        if student_queryset is not None:
            self.fields['student'].queryset = student_queryset

    def clean_score(self):
        score = self.cleaned_data.get('score')
        if self.exam and score is not None and score > self.exam.max_score:
            raise forms.ValidationError('Score cannot exceed the exam maximum.')
        return score


class TeacherAttendanceForm(forms.Form):
    subject = forms.ModelChoiceField(queryset=Subject.objects.none())
    student = forms.ModelChoiceField(queryset=User.objects.none())
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    status = forms.ChoiceField(choices=Attendance.STATUS_CHOICES)
    remarks = forms.CharField(required=False, max_length=100)


class PlannerEventForm(forms.ModelForm):
    class Meta:
        model = PlannerEvent
        fields = ['subject', 'title', 'description', 'starts_at', 'ends_at', 'is_completed']
        widgets = {
            'starts_at': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M',
                attrs={'type': 'datetime-local'},
            ),
            'ends_at': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M',
                attrs={'type': 'datetime-local'},
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        starts_at = cleaned_data.get('starts_at')
        ends_at = cleaned_data.get('ends_at')
        if starts_at and ends_at and ends_at <= starts_at:
            self.add_error('ends_at', 'End time must be after start time.')
        return cleaned_data


class EventReminderForm(forms.ModelForm):
    class Meta:
        model = EventReminder
        fields = ['remind_at']
        widgets = {
            'remind_at': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M',
                attrs={'type': 'datetime-local'},
            ),
        }


class TaskCommentForm(forms.ModelForm):
    class Meta:
        model = TaskComment
        fields = ['body']
        widgets = {'body': forms.Textarea(attrs={'rows': 3})}


class TeacherAssignmentForm(forms.Form):
    teacher = forms.ModelChoiceField(
        queryset=User.objects.filter(
            is_active=True,
            profile__user_roles__role__code='teacher',
        ).distinct(),
    )


class RoleAssignmentForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).order_by('username'),
    )
    role = forms.ModelChoiceField(queryset=Role.objects.order_by('code'))


class SystemSettingForm(forms.ModelForm):
    class Meta:
        model = SystemSetting
        fields = ['key', 'value']
        widgets = {'value': forms.Textarea(attrs={'rows': 4})}


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ['title', 'body', 'is_published']
        widgets = {'body': forms.Textarea(attrs={'rows': 5})}
