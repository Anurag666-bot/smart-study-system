# SmartStudy System — Final ER Diagram

This diagram models the Django `auth.User` table as `USER` and all application-owned entities in `studyapp.models`. Foreign keys marked `nullable` are optional relationships. `USER` is the built-in Django authentication model; it is not replaced by a custom user table.

```mermaid
erDiagram
    USER {
        bigint id PK
        string username UK
        string email
        boolean is_active
        boolean is_staff
        boolean is_superuser
        datetime date_joined
    }

    NOTE {
        bigint id PK
        bigint user_id FK
        string title
        text content
        text summary nullable
        string file nullable
        datetime created_at
        datetime updated_at
        boolean is_deleted
    }

    NOTE_ATTACHMENT {
        bigint id PK
        bigint note_id FK
        string file
        string original_name
        int size
        string content_type
        datetime uploaded_at
    }

    TASK {
        bigint id PK
        bigint user_id FK
        bigint subject_id FK nullable
        string title
        text description
        string priority
        string status
        date due_date
        string difficulty
        int estimated_minutes nullable
        int progress
        datetime completed_at nullable
        datetime created_at
        datetime updated_at
        boolean is_deleted
    }

    TASK_COMMENT {
        bigint id PK
        bigint task_id FK
        bigint author_id FK nullable
        text body
        datetime created_at
        datetime updated_at
    }

    TASK_ATTACHMENT {
        bigint id PK
        bigint task_id FK
        bigint uploaded_by_id FK nullable
        string file
        string original_name
        int size
        string content_type
        datetime uploaded_at
    }

    ATTENDANCE {
        bigint id PK
        bigint user_id FK
        bigint subject_id FK nullable
        date date
        boolean is_present
        string status nullable
        string remarks
    }

    ACTIVITY_LOG {
        bigint id PK
        bigint user_id FK
        string action
        string model_name
        int object_id nullable
        string object_repr
        datetime timestamp
        string ip_address nullable
        text user_agent
    }

    STUDY_PLAN {
        bigint id PK
        bigint user_id FK
        string subject
        float hours
        date date
        text notes
        boolean is_deleted
        datetime deleted_at nullable
    }

    PROFILE {
        bigint id PK
        bigint user_id FK UK
        datetime created_at
        datetime updated_at
    }

    ROLE {
        bigint id PK
        string code UK
        string name
        text description
    }

    USER_ROLE {
        bigint id PK
        bigint profile_id FK
        bigint role_id FK
        datetime assigned_at
    }

    SUBJECT {
        bigint id PK
        string code UK
        string name UK
        text description
        bigint created_by_id FK nullable
        boolean is_active
        datetime created_at
        datetime updated_at
    }

    TOPIC {
        bigint id PK
        bigint subject_id FK
        string name
        text description
        datetime created_at
    }

    STUDENT_SUBJECT {
        bigint id PK
        bigint student_id FK
        bigint subject_id FK
        datetime enrolled_at
        boolean is_active
    }

    TEACHER_SUBJECT {
        bigint id PK
        bigint teacher_id FK
        bigint subject_id FK
        datetime assigned_at
        boolean is_active
    }

    STUDY_SESSION {
        bigint id PK
        bigint user_id FK
        bigint subject_id FK nullable
        datetime started_at
        datetime ended_at nullable
        int duration_minutes nullable
        text notes
        datetime created_at
    }

    GOAL {
        bigint id PK
        bigint user_id FK
        bigint subject_id FK nullable
        string title
        text description
        date target_date
        decimal target_value
        decimal current_value
        string unit
        string status
        datetime created_at
        datetime updated_at
    }

    ACHIEVEMENT {
        bigint id PK
        string code UK
        string name
        text description
        int points
    }

    USER_ACHIEVEMENT {
        bigint id PK
        bigint user_id FK
        bigint achievement_id FK
        datetime awarded_at
    }

    EXAM {
        bigint id PK
        bigint subject_id FK
        string title
        date exam_date
        decimal max_score
        bigint created_by_id FK nullable
        boolean is_archived
        datetime archived_at nullable
        datetime created_at
    }

    EXAM_RESULT {
        bigint id PK
        bigint exam_id FK
        bigint student_id FK
        decimal score
        text feedback
        datetime graded_at
    }

    PLANNER_EVENT {
        bigint id PK
        bigint user_id FK
        bigint subject_id FK nullable
        string title
        text description
        datetime starts_at
        datetime ends_at
        boolean is_completed
        boolean is_deleted
        datetime deleted_at nullable
        datetime created_at
        datetime updated_at
    }

    EVENT_REMINDER {
        bigint id PK
        bigint event_id FK
        datetime remind_at
        datetime sent_at nullable
    }

    NOTIFICATION {
        bigint id PK
        bigint user_id FK
        string notification_type
        string dedup_key nullable
        string title
        text message
        datetime read_at nullable
        datetime created_at
    }

    ADMIN_LOG {
        bigint id PK
        bigint actor_id FK nullable
        string action
        string target_type
        string target_id
        json details
        string ip_address nullable
        text user_agent
        datetime timestamp
    }

    SYSTEM_SETTING {
        bigint id PK
        string key UK
        json value
        bigint updated_by_id FK nullable
        datetime updated_at
    }

    ANNOUNCEMENT {
        bigint id PK
        string title
        text body
        bigint created_by_id FK nullable
        boolean is_published
        datetime published_at nullable
        datetime created_at
        datetime updated_at
    }

    USER ||--o{ NOTE : owns
    NOTE ||--o{ NOTE_ATTACHMENT : contains

    USER ||--o{ TASK : owns
    SUBJECT o|--o{ TASK : categorizes
    TASK ||--o{ TASK_COMMENT : has
    USER o|--o{ TASK_COMMENT : authors
    TASK ||--o{ TASK_ATTACHMENT : has
    USER o|--o{ TASK_ATTACHMENT : uploads

    USER ||--o{ ATTENDANCE : has
    SUBJECT o|--o{ ATTENDANCE : scopes
    USER ||--o{ ACTIVITY_LOG : generates
    USER ||--o{ STUDY_PLAN : creates

    USER ||--o| PROFILE : has
    PROFILE ||--o{ USER_ROLE : receives
    ROLE ||--o{ USER_ROLE : assigned_through

    USER o|--o{ SUBJECT : creates
    SUBJECT ||--o{ TOPIC : contains
    USER ||--o{ STUDENT_SUBJECT : enrolls
    SUBJECT ||--o{ STUDENT_SUBJECT : has_students
    USER ||--o{ TEACHER_SUBJECT : teaches
    SUBJECT ||--o{ TEACHER_SUBJECT : has_teachers

    USER ||--o{ STUDY_SESSION : records
    SUBJECT o|--o{ STUDY_SESSION : concerns
    USER ||--o{ GOAL : owns
    SUBJECT o|--o{ GOAL : concerns

    USER ||--o{ USER_ACHIEVEMENT : earns
    ACHIEVEMENT ||--o{ USER_ACHIEVEMENT : awarded_through

    SUBJECT ||--o{ EXAM : contains
    USER o|--o{ EXAM : creates
    EXAM ||--o{ EXAM_RESULT : receives
    USER ||--o{ EXAM_RESULT : earns

    USER ||--o{ PLANNER_EVENT : schedules
    SUBJECT o|--o{ PLANNER_EVENT : concerns
    PLANNER_EVENT ||--o{ EVENT_REMINDER : has
    USER ||--o{ NOTIFICATION : receives

    USER o|--o{ ADMIN_LOG : acts_through
    USER o|--o{ SYSTEM_SETTING : updates
    USER o|--o{ ANNOUNCEMENT : publishes
```

## Important constraints and modeling notes

- `PROFILE.user` is one-to-one and `USER_ROLE(profile, role)` is unique.
- `STUDENT_SUBJECT(student, subject)` and `TEACHER_SUBJECT(teacher, subject)` are unique association rows.
- `TOPIC(subject, name)` is unique.
- `USER_ACHIEVEMENT(user, achievement)` is unique.
- `EXAM_RESULT(exam, student)` is unique.
- `EVENT_REMINDER(event, remind_at)` is unique.
- `NOTIFICATION(user, dedup_key)` is unique when a deduplication key is supplied.
- Attendance supports both general daily records and subject-scoped records:
  - one general record per `(user, date)` when `subject_id IS NULL`;
  - one record per `(user, date, subject)` when `subject_id IS NOT NULL`.
- `STUDY_PLAN.subject` is intentionally legacy free text, not a foreign key to `SUBJECT`; ambiguous legacy values are not remapped.
- `TASK.subject`, `ATTENDANCE.subject`, `STUDY_SESSION.subject`, `GOAL.subject`, and `PLANNER_EVENT.subject` are nullable and use `SET_NULL` on subject deletion.
- `SUBJECT.created_by`, `EXAM.created_by`, `TASK_COMMENT.author`, `TASK_ATTACHMENT.uploaded_by`, `ADMIN_LOG.actor`, `SYSTEM_SETTING.updated_by`, and `ANNOUNCEMENT.created_by` are nullable audit/ownership references.
- Soft deletion/archive state is represented by `is_deleted`/`deleted_at` on notes, tasks, study plans, and planner events, and by `is_archived`/`archived_at` on exams.
- `USER` represents Django's built-in `auth.User`; `is_staff` is a technical Django flag, while application authorization is represented by explicit `ROLE` assignments.

## Viva explanation

The design separates identity (`USER`), authorization (`PROFILE`–`ROLE`–`USER_ROLE`), academic reference data (`SUBJECT`–`TOPIC`), student/teacher associations, personal study activity, assessment, planning, notifications, and administration. Ownership foreign keys enforce private data boundaries, while association tables provide many-to-many enrollment and teaching relationships without duplicating user or subject data.
