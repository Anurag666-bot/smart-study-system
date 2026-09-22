# Smart Study System

A comprehensive Django-based web application designed to enhance learning and study efficiency through intelligent features and personalized learning paths.

## Features

- **Intelligent Study Planning**: AI-powered study schedule generation based on learning goals and available time
- **Progress Tracking**: Visual dashboards and analytics to monitor learning progress
- **Resource Management**: Organize and access study materials, notes, and references
- **Quiz & Assessment Tools**: Create and take practice quizzes with instant feedback
- **Collaboration Features**: Study groups and peer learning capabilities
- **Multi-platform Support**: Responsive design for desktop and mobile use

## Project Structure

```
smart_study_system/
├── core/                 # Django project settings and configuration
├── studyapp/            # Main application logic
├── docs/                # Documentation files
├── media/               # User-uploaded media files
├── backups/             # Database and system backups
├── requirements.txt     # Python dependencies
├── manage.py            # Django management script
├── db.sqlite3           # SQLite database (development)
├── ER_DIAGRAM.md        # Database schema documentation
└── generate_schema.py   # Database schema generation utility
```

## Installation

### Prerequisites

- Python 3.8+
- pip (Python package manager)
- Virtual environment (recommended)

### Setup Instructions

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd smart_study_system
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Apply database migrations**
   ```bash
   python manage.py migrate
   ```

5. **Create a superuser (admin)**
   ```bash
   python manage.py createsuperuser
   ```

6. **Load sample data (optional)**
   ```bash
   python manage.py loaddata sample_data.json
   ```

## Usage

### Development Server

Start the development server:
```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000/` in your web browser.

Access the admin panel at `http://127.0.0.1:8000/admin/` using your superuser credentials.

### Production Deployment

For production deployment, consider:
- Using a production WSGI server (Gunicorn, uWSGI)
- Configuring a proper database (PostgreSQL/MySQL)
- Setting up static file serving
- Configuring environment variables for security

## Configuration

Key configuration files:
- `core/settings.py` - Main Django settings
- `core/urls.py` - URL routing configuration
- `.env` - Environment variables (create based on `.env.example` if available)

Environment variables to consider:
- `SECRET_KEY` - Django secret key
- `DEBUG` - Set to `False` in production
- `DATABASE_URL` - Database connection string
- `ALLOWED_HOSTS` - List of allowed host/domain names

## Testing

Run the test suite:
```bash
python manage.py test
```

Run specific app tests:
```bash
python manage.py test studyapp
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

Please ensure your code follows the project's coding standards and includes appropriate tests.

## Database Schema

See [ER_DIAGRAM.md](ER_DIAGRAM.md) for detailed database schema documentation.

## Backup and Recovery

Use the provided backup script:
```bash
./backup_study_system.sh
```

Backups are stored in the `backups/` directory.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contact

For questions or support, please open an issue in the GitHub repository.

---

🤖 **Generated with [Claude Code](https://claude.com/claude-code)**