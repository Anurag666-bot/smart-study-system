# Entity Relationship Diagram for Smart Study System

This document describes the ER diagram for the Smart Study System Django project.

## Entities and Relationships

```mermaid
erDiagram
    %% Core Entities
    USER ||..||{ NOTE : "owns"
    USER ||..||{ TASK : "owns"
    USER ||..||{ TASK_COMMENT : "authors"
    USER ||..||{ TASK_ATTACHMENT : "uploads"
    USER ||..||{ ATTENDANCE : "records"
    USER ||..||{ ACTIVITY_LOG : "performs"
    USER ||..||{ STUDY_PLAN : "creates"
    USER ||..||{ PROFILE : "has"
    USER ||..||{ GOAL : "sets"
    USER ||..||{ EXAM_RESULT : "achieves"
    USER ||..||{ PLANNER_EVENT : "creates"
    USER ||..||{ EVENT_REMINDER : "receives"
    USER ||..||{ NOTIFICATION : "receives"
    USER ||..||{ ADMIN_LOG : "performs"
    USER ||..||{ SYSTEM_SETTING : "updates"
    USER ||..||{ ANNOUNCEMENT : "creates"
    
    SUBJECT ||..||{ TASK : "relates_to"
    SUBJECT ||..||{ ATTENDANCE : "tracks"
    SUBJECT ||..||{ TOPIC : "contains"
    SUBJECT ||..||{ STUDENT_SUBJECT : "enrolled_in"
    SUBJECT ||..||{ TEACHER_SUBJECT : "taught_by"
    SUBJECT ||..||{ STUDY_SESSION : "relates_to"
    SUBJECT ||..||{ GOAL : "targets"
    SUBJECT ||..||{ EXAM : "assesses"
    SUBJECT ||..||{ PLANNER_EVENT : "relates_to"
    
    NOTE ||..||{ NOTE_ATTACHMENT : "has"
    TASK ||..||{ TASK_COMMENT : "has"
    TASK ||..||{ TASK_ATTACHMENT : "has"
    EXAM ||..||{ EXAM_RESULT : "has"
    PLANNER_EVENT ||..||{ EVENT_REMINDER : "has"
    
    ROLE ||..||{ USER_ROLE : "assigned_to"
    PROFILE ||..||{ USER_ROLE : "receives"
    
    ACHIEVEMENT ||..||{ USER_ACHIEVEMENT : "earned_by"
    USER ||..||{ USER_ACHIEVEMENT : "earns"
    
    %% Entity Definitions
    USER {
        int id PK
        varchar username
        varchar email
        varchar first_name
        varchar last_name
        date date_joined
        bool is_active
    }
    
    NOTE {
        int id PK
        int user_id FK
        varchar title
        text content
        text summary
        varchar file
        datetime created_at
        datetime updated_at
        bool is_deleted
    }
    
    NOTE_ATTACHMENT {
        int id PK
        int note_id FK
        varchar file
        varchar original_name
        int size
        varchar content_type
        datetime uploaded_at
    }
    
    TASK {
        int id PK
        int user_id FK
        int subject_id FK
        varchar title
        text description
        varchar priority
        varchar status
        date due_date
        varchar difficulty
        int estimated_minutes
        int progress
        datetime completed_at
        datetime created_at
        datetime updated_at
        bool is_deleted
    }
    
    TASK_COMMENT {
        int id PK
        int task_id FK
        int author_id FK
        text body
        datetime created_at
        datetime updated_at
    }
    
    TASK_ATTACHMENT {
        int id PK
        int task_id FK
        int uploaded_by_id FK
        varchar file
        varchar original_name
        int size
        varchar content_type
        datetime uploaded_at
    }
    
    ATTENDANCE {
        int id PK
        int user_id FK
        int subject_id FK
        date date
        bool is_present
        varchar status
        varchar remarks
    }
    
    ACTIVITY_LOG {
        int id PK
        int user_id FK
        varchar action
        varchar model_name
        int object_id
        varchar object_repr
        datetime timestamp
        varchar ip_address
        text user_agent
    }
    
    STUDY_PLAN {
        int id PK
        int user_id FK
        varchar subject
        float hours
        date date
        text notes
        bool is_deleted
        datetime deleted_at
    }
    
    PROFILE {
        int id PK
        int user_id FK
        datetime created_at
        datetime updated_at
    }
    
    ROLE {
        int id PK
        varchar code
        varchar name
        text description
    }
    
    USER_ROLE {
        int id PK
        int profile_id FK
        int role_id FK
        datetime assigned_at
    }
    
    SUBJECT {
        int id PK
        varchar code
        varchar name
        text description
        int created_by_id FK
        bool is_active
        datetime created_at
        datetime updated_at
    }
    
    TOPIC {
        int id PK
        int subject_id FK
        varchar name
        text description
        datetime created_at
    }
    
    STUDENT_SUBJECT {
        int id PK
        int student_id FK
        int subject_id FK
        datetime enrolled_at
        bool is_active
    }
    
    TEACHER_SUBJECT {
        int id PK
        int teacher_id FK
        int subject_id FK
        datetime assigned_at
        bool is_active
    }
    
    STUDY_SESSION {
        int id PK
        int user_id FK
        int subject_id FK
        datetime started_at
        datetime ended_at
        int duration_minutes
        text notes
        datetime created_at
    }
    
    GOAL {
        int id PK
        int user_id FK
        int subject_id FK
        varchar title
        text description
        date target_date
        decimal target_value
        decimal current_value
        varchar unit
        varchar status
        datetime created_at
        datetime updated_at
    }
    
    ACHIEVEMENT {
        int id PK
        varchar code
        varchar name
        text description
        int points
    }
    
    USER_ACHIEVEMENT {
        int id PK
        int user_id FK
        int achievement_id FK
        datetime awarded_at
    }
    
    EXAM {
        int id PK
        int subject_id FK
        varchar title
        date exam_date
        decimal max_score
        int created_by_id FK
        bool is_archived
        datetime archived_at
        datetime created_at
    }
    
    EXAM_RESULT {
        int id PK
        int exam_id FK
        int student_id FK
        decimal score
        text feedback
        datetime graded_at
    }
    
    PLANNER_EVENT {
        int id PK
        int user_id FK
        int subject_id FK
        varchar title
        text description
        datetime starts_at
        datetime ends_at
        bool is_completed
        bool is_deleted
        datetime deleted_at
        datetime created_at
        datetime updated_at
    }
    
    EVENT_REMINDER {
        int id PK
        int event_id FK
        datetime remind_at
        datetime sent_at
    }
    
    NOTIFICATION {
        int id PK
        int user_id FK
        varchar notification_type
        varchar dedup_key
        varchar title
        text message
        datetime read_at
        datetime created_at
    }
    
    ADMIN_LOG {
        int id PK
        int actor_id FK
        varchar action
        varchar target_type
        varchar target_id
        json details
        varchar ip_address
        text user_agent
        datetime timestamp
    }
    
    SYSTEM_SETTING {
        int id PK
        varchar key
        json value
        int updated_by_id FK
        datetime updated_at
    }
    
    ANNOUNCEMENT {
        int id PK
        varchar title
        text body
        int created_by_id FK
        bool is_published
        datetime published_at
        datetime created_at
        datetime updated_at
    }
    
    %% Relationships (explicitly defined for clarity)
    USER }|..||{ NOTE : "owns"
    USER }|..||{ TASK : "owns"
    USER }|..||{ TASK_COMMENT : "authors"
    USER }|..||{ TASK_ATTACHMENT : "uploads"
    USER }|..||{ ATTENDANCE : "records"
    USER }|..||{ ACTIVITY_LOG : "performs"
    USER }|..||{ STUDY_PLAN : "creates"
    USER }|..||{ PROFILE : "has"
    USER }|..||{ GOAL : "sets"
    USER }|..||{ EXAM_RESULT : "achieves"
    USER }|..||{ PLANNER_EVENT : "creates"
    USER }|..||{ EVENT_REMINDER : "receives"
    USER }|..||{ NOTIFICATION : "receives"
    USER }|..||{ ADMIN_LOG : "performs"
    USER }|..||{ SYSTEM_SETTING : "updates"
    USER }|..||{ ANNOUNCEMENT : "creates"
    
    SUBJECT }|..||{ TASK : "relates_to"
    SUBJECT }|..||{ ATTENDANCE : "tracks"
    SUBJECT }|..||{ TOPIC : "contains"
    SUBJECT }|..||{ STUDENT_SUBJECT : "enrolled_in"
    SUBJECT }|..||{ TEACHER_SUBJECT : "taught_by"
    SUBJECT }|..||{ STUDY_SESSION : "relates_to"
    SUBJECT }|..||{ GOAL : "targets"
    SUBJECT }|..||{ EXAM : "assesses"
    SUBJECT }|..||{ PLANNER_EVENT : "relates_to"
    
    NOTE }|..||{ NOTE_ATTACHMENT : "has"
    TASK }|..||{ TASK_COMMENT : "has"
    TASK }|..||{ TASK_ATTACHMENT : "has"
    EXAM }|..||{ EXAM_RESULT : "has"
    PLANNER_EVENT }|..||{ EVENT_REMINDER : "has"
    
    ROLE }|..||{ USER_ROLE : "assigned_to"
    PROFILE }|..||{ USER_ROLE : "receives"
    
    ACHIEVEMENT }|..||{ USER_ACHIEVEMENT : "earned_by"
    USER }|..||{ USER_ACHIEVEMENT : "earns"
</em>