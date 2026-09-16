# Smart Study System

A comprehensive **Django-based academic management and intelligent study-support system** designed to help students organize their academic activities, manage study resources, track progress, and plan their study time efficiently.

The system provides separate role-based functionality for **Students, Teachers, and Administrators**, while integrating intelligent algorithms for task prioritization, content search, text summarization, study planning, and personalized recommendations.

---

## Key Features

### 🎓 Student Management

* Student dashboard with academic overview
* Personal profile management
* Subject and enrollment management
* Notes and study-resource management
* Task and assignment tracking
* Study planner and scheduling
* Study-session tracking
* Learning goals
* Attendance monitoring
* Academic progress and analytics
* Notifications and reminders
* Achievement/progress tracking

### 👨‍🏫 Teacher Management

* Teacher dashboard
* Assigned subject management
* Student enrollment visibility
* Attendance management
* Exam and assessment management
* Student result management
* Academic monitoring

### 🛡️ Administrator Management

* Administrative dashboard
* User management
* Role and permission management
* Subject management
* System configuration
* Announcements
* Notifications
* Activity and audit logging
* System-level monitoring

---

## Intelligent Features and Algorithms

The Smart Study System goes beyond basic CRUD operations by incorporating several intelligent and explainable algorithms.

### 1. Task Priority Scheduling

The system calculates task priority using factors such as:

* Deadline urgency
* Task importance
* Estimated workload
* Task status
* Available study time

A priority score is generated to help students determine which tasks should receive attention first.

---

### 2. TF-IDF Based Search

**Term Frequency–Inverse Document Frequency (TF-IDF)** is used to identify the importance of terms within study content.

It allows users to search notes and academic resources based on relevant keywords rather than relying only on exact database matches.

---

### 3. TextRank Summarization

The system uses the **TextRank algorithm** to extract important sentences from longer study materials.

This helps students quickly review large amounts of text and identify the most relevant information.

---

### 4. Adaptive Study Planning

The study planner considers factors such as:

* Learning goals
* Available study time
* Pending tasks
* Task deadlines
* Study history
* Subject requirements

Based on these factors, the system generates a structured study plan.

---

### 5. Personalized Recommendations

The recommendation component uses available academic activity and study information to provide relevant study suggestions.

Recommendations can be based on factors such as:

* Pending tasks
* Subjects
* Study activity
* Goals
* Previous study sessions
* Academic progress

---

## Role-Based Access Control

The system follows a **role-based architecture** with three major roles:

| Role              | Main Responsibilities                                               |
| ----------------- | ------------------------------------------------------------------- |
| **Student**       | Notes, tasks, planner, study sessions, goals, attendance, analytics |
| **Teacher**       | Subjects, attendance, exams, results, assigned students             |
| **Administrator** | Users, roles, subjects, announcements, settings, audit logs         |

The system separates user identity from role assignment using a dedicated role-based structure.

### RBAC Structure

```text
User
 ├── Profile
 └── UserRole
       └── Role
```

This design allows the system to support multiple roles while keeping authorization and user information logically separated.

---

## System Architecture

The project follows the Django **MVT (Model–View–Template)** architecture.

```text
                 Smart Study System
                        │
          ┌─────────────┴─────────────┐
          │                           │
      Presentation                 Application
          │                           │
      Templates                    Views
          │                           │
          └─────────────┬─────────────┘
                        │
                     Models
                        │
                 Database Layer
                        │
                    SQLite
```

The intelligent processing components operate alongside the application layer to provide search, summarization, prioritization, planning, and recommendation functionality.

---

## Project Structure

```text
smart_study_system/
│
├── core/
│   ├── settings.py          # Django configuration
│   ├── urls.py              # Main URL configuration
│   └── ...
│
├── studyapp/
│   ├── models.py            # Database models
│   ├── views.py             # Application logic
│   ├── urls.py              # Application URLs
│   ├── admin.py             # Admin configuration
│   ├── forms.py             # Forms
│   ├── templates/           # HTML templates
│   ├── static/              # CSS, JavaScript and assets
│   └── ...
│
├── docs/                    # Project documentation
├── media/                   # Uploaded files
├── backups/                 # Database backups
│
├── manage.py                # Django management utility
├── requirements.txt         # Python dependencies
├── db.sqlite3               # Development database
├── ER_DIAGRAM.md            # Database schema documentation
└── generate_schema.py       # Schema generation utility
```

---

## Core Database Entities

The major entities used by the system include:

```text
User
Profile
Role
UserRole
Subject
Enrollment
TeacherAssignment
Note
Task
PlannerEvent
Reminder
StudySession
Goal
Attendance
Exam
Result
Achievement
Notification
Announcement
SystemSetting
AdminLog
```

The database design supports academic management, role-based access control, study planning, progress tracking, and system administration.

For the detailed database relationship model, see:

`ER_DIAGRAM.md`

---

## Technology Stack

### Backend

* Python
* Django
* Django ORM

### Frontend

* HTML5
* CSS3
* JavaScript
* Responsive UI

### Database

* SQLite for development
* Compatible with relational databases such as MySQL/MariaDB and PostgreSQL for deployment

### Intelligent Processing

* TF-IDF
* TextRank
* Task-priority scheduling
* Adaptive study planning
* Recommendation logic

### Development and Testing

* Django Test Framework
* Python virtual environment
* Git/GitHub

---

## Installation

### Prerequisites

Make sure the following are installed:

* Python 3.12+
* pip
* Git
* Virtual environment support

### 1. Clone the Repository

```bash
git clone <repository-url>
cd smart_study_system
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
```

Activate it:

#### Linux/macOS

```bash
source venv/bin/activate
```

#### Windows

```powershell
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Apply Database Migrations

```bash
python manage.py migrate
```

### 5. Create an Administrator Account

```bash
python manage.py createsuperuser
```

Follow the prompts to create the administrator account.

---

## Running the Application

Start the Django development server:

```bash
python manage.py runserver
```

The application will normally be available at:

```text
http://127.0.0.1:8000/
```

The Django administration panel is available at:

```text
http://127.0.0.1:8000/admin/
```

---

## Testing

Run the complete test suite:

```bash
python manage.py test
```

Run tests specifically for the application:

```bash
python manage.py test studyapp
```

Before deployment, it is recommended to verify the project configuration with:

```bash
python manage.py check
```

---

## Configuration

Important configuration files include:

```text
core/settings.py
core/urls.py
studyapp/models.py
studyapp/views.py
```

For production deployment, sensitive configuration should be managed through environment variables.

Important settings include:

```text
SECRET_KEY
DEBUG
ALLOWED_HOSTS
DATABASE_URL
```

`DEBUG` should be disabled in a production environment.

---

## Database Backup

Database backups should be maintained before performing major database changes or migrations.

Example backup directory:

```text
backups/
```

If the project includes the backup utility, it can be executed with:

```bash
./backup_study_system.sh
```

---

## Security Considerations

The system incorporates several security-related practices, including:

* Role-based access control
* Authentication and authorization
* Password-protected user accounts
* Permission-based administrative operations
* User activity logging
* CSRF protection provided by Django
* Secure session management
* Input validation through Django forms
* Separation of administrative and student/teacher functionality

For production deployment, additional security configuration should include:

* HTTPS
* Secure cookies
* Environment-based secret management
* Proper `ALLOWED_HOSTS`
* Disabled `DEBUG`
* Database access restrictions
* Secure static and media-file configuration

---

## Deployment

For production deployment, the application can be configured with:

* Gunicorn or another production WSGI server
* PostgreSQL/MySQL/MariaDB
* Nginx or another reverse proxy
* HTTPS/TLS
* Environment variables
* Proper static and media file serving

The SQLite database included in the repository is intended primarily for development and demonstration.

---

## Project Documentation

Additional documentation is available in the project repository.

Important documentation includes:

```text
ER_DIAGRAM.md
docs/
```

The ER diagram documents the relationships between the major entities of the Smart Study System.

---

## Future Enhancements

Potential future improvements include:

* Mobile application
* Advanced learning analytics
* More sophisticated recommendation models
* Automated quiz generation
* Integration with external learning resources
* Email and push notifications
* Real-time collaboration
* Machine-learning-based performance prediction
* Cloud deployment and scalable database infrastructure

---

## Academic Project

**Project Title:** Smart Study System

**Technology:** Django, Python, HTML, CSS, JavaScript, SQLite

**Project Type:** Full-Stack Web Application with Intelligent Study-Support Features

**Academic Level:** Bachelor of Computer Application (BCA)

---

## Author

**Anurag Kumar Das**


---

## License

This project is developed as an academic project. If a specific open-source license is required for public distribution, the repository should include the corresponding `LICENSE` file.
