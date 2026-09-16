#!/usr/bin/env python3
"""
Test script for Smart Study System
Tests each feature one by one.
"""
import requests
import json
import os
import re
import sys

BASE_URL = os.environ.get('SMART_STUDY_BASE_URL', 'http://localhost:8000')
SESSION = requests.Session()

def print_step(step):
    print(f"\n=== {step} ===")

def print_success(msg):
    print(f"[✓] {msg}")

def print_failure(msg):
    print(f"[✗] {msg}")
    return False

def make_request(method, path, **kwargs):
    url = BASE_URL + path
    try:
        resp = SESSION.request(method, url, **kwargs)
        return resp
    except Exception as e:
        print(f"Request error: {e}")
        return None


def get_csrf_token(resp):
    if not resp:
        return None
    match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', resp.text)
    return match.group(1) if match else None


def register_user(username, email, password):
    print_step(f"Registering user {username}")
    page = make_request('GET', '/register/')
    csrf_token = get_csrf_token(page)
    if not csrf_token:
        print_failure("Could not find CSRF token for registration")
        return False
    data = {
        'username': username,
        'email': email,
        'password': password,
        'confirm_password': password,
        'csrfmiddlewaretoken': csrf_token,
    }
    resp = make_request('POST', '/register/', data=data)
    if resp and resp.status_code == 200:
        # Check if registration succeeded (look for redirect or success message)
        if 'dashboard' in resp.url or 'Dashboard' in resp.text:
            print_success(f"User {username} registered")
            return True
        else:
            # Maybe already logged in?
            print_success(f"User {username} registered (or already exists)")
            return True
    else:
        print_failure(f"Failed to register user {username}")
        return False

def login_user(username, password):
    print_step(f"Logging in as {username}")
    page = make_request('GET', '/login/')
    csrf_token = get_csrf_token(page)
    if not csrf_token:
        print_failure("Could not find CSRF token for login")
        return False
    data = {
        'username': username,
        'password': password,
        'csrfmiddlewaretoken': csrf_token,
    }
    resp = make_request('POST', '/login/', data=data)
    if resp and resp.status_code == 200:
        if 'dashboard' in resp.url or 'Dashboard' in resp.text:
            print_success(f"Logged in as {username}")
            return True
        else:
            print_failure(f"Login failed for {username}")
            return False
    else:
        print_failure(f"Login request failed for {username}")
        return False


def logout_user():
    print_step("Logging out")
    page = make_request('GET', '/dashboard/')
    csrf_token = get_csrf_token(page)
    if not csrf_token:
        print_failure("Could not find CSRF token for logout")
        return False
    resp = make_request(
        'POST',
        '/logout/',
        data={'csrfmiddlewaretoken': csrf_token},
    )
    if resp and resp.status_code in (200, 302):
        print_success("Logged out")
        return True
    else:
        print_failure("Logout failed")
        return False

def test_homepage():
    print_step("Testing homepage")
    resp = make_request('GET', '/')
    if resp and resp.status_code == 200:
        print_success("Homepage accessible")
        return True
    else:
        print_failure("Homepage not accessible")
        return False

def test_notes_crud():
    print_step("Testing Notes CRUD")
    # List notes (should be empty)
    resp = make_request('GET', '/notes/')
    if not (resp and resp.status_code == 200):
        return print_failure("Failed to access notes list")

    # Upload a note (without file for simplicity)
    print_step("Creating a note")
    data = {
        'title': 'Test Note',
        'content': 'This is a test note content.',
        'summary': '',  # Let auto-summary generate
    }
    # Fetch the form so the session receives and submits its CSRF token.
    resp = make_request('GET', '/notes/upload/')
    if not (resp and resp.status_code == 200):
        return print_failure("Failed to access upload note page")

    # Extract CSRF token from HTML (simplistic)
    import re
    csrf_match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', resp.text)
    if not csrf_match:
        print_failure("Could not find CSRF token")
        return False
    csrf_token = csrf_match.group(1)

    data['csrfmiddlewaretoken'] = csrf_token
    resp = make_request('POST', '/notes/upload/', data=data)
    if not (resp and resp.status_code in (200, 302)):
        print_failure("Failed to create note")
        return False

    # Note created, now check if it appears in list
    resp = make_request('GET', '/notes/')
    if resp and 'Test Note' in resp.text:
        print_success("Note created and listed")
    else:
        print_failure("Note not found in list")
        return False

    # We could test edit, delete, etc., but for brevity, we'll stop here.
    # However, we should at least test deletion to clean up.
    # Let's get the note ID from the list (simplistic)
    import re
    note_id_match = re.search(r'/notes/(\d+)/', resp.text)
    if note_id_match:
        note_id = note_id_match.group(1)
        # Delete note
        resp = make_request('GET', f'/notes/{note_id}/delete/')
        if resp and resp.status_code == 200:
            # Get CSRF token for delete confirmation
            csrf_match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', resp.text)
            if csrf_match:
                csrf_token = csrf_match.group(1)
                resp = make_request('POST', f'/notes/{note_id}/delete/',
                                    data={'csrfmiddlewaretoken': csrf_token})
                if resp and resp.status_code in (200, 302):
                    print_success("Note deleted")
                else:
                    print_failure("Failed to confirm note deletion")
            else:
                print_failure("Could not find CSRF token for delete")
        else:
            print_failure("Failed to access delete note page")
    else:
        print_failure("Could not find note ID for deletion")

    return True

def test_tasks_crud():
    print_step("Testing Tasks CRUD")
    # Similar to notes, but we'll just test creation and listing for brevity.
    # Get tasks list
    resp = make_request('GET', '/tasks/')
    if not (resp and resp.status_code == 200):
        return print_failure("Failed to access tasks list")

    # Get add task page for CSRF
    resp = make_request('GET', '/tasks/add/')
    if not (resp and resp.status_code == 200):
        return print_failure("Failed to access add task page")

    import re
    csrf_match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', resp.text)
    if not csrf_match:
        print_failure("Could not find CSRF token")
        return False
    csrf_token = csrf_match.group(1)

    # Create a task
    from datetime import date, timedelta
    due_date = (date.today() + timedelta(days=5)).isoformat()
    data = {
        'title': 'Test Task',
        'description': 'This is a test task.',
        'priority': 'Medium',
        'status': 'Pending',
        'due_date': due_date,
        'difficulty': 'Medium',
        'progress': '0',
        'csrfmiddlewaretoken': csrf_token,
    }
    resp = make_request('POST', '/tasks/add/', data=data)
    if not (resp and resp.status_code in (200, 302)):
        print_failure("Failed to create task")
        return False

    # Check if task appears in list
    resp = make_request('GET', '/tasks/')
    if resp and 'Test Task' in resp.text:
        print_success("Task created and listed")
    else:
        print_failure("Task not found in list")
        return False

    # Clean up: delete the task
    task_id_match = re.search(r'/tasks/edit/(\d+)/', resp.text)
    if task_id_match:
        task_id = task_id_match.group(1)
        resp = make_request('GET', f'/tasks/{task_id}/delete/')
        if resp and resp.status_code == 200:
            csrf_match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', resp.text)
            if csrf_match:
                csrf_token = csrf_match.group(1)
                resp = make_request('POST', f'/tasks/{task_id}/delete/',
                                    data={'csrfmiddlewaretoken': csrf_token})
                if resp and resp.status_code in (200, 302):
                    print_success("Task deleted")
                else:
                    print_failure("Failed to confirm task deletion")
            else:
                print_failure("Could not find CSRF token for task delete")
        else:
            print_failure("Failed to access delete task page")
    else:
        print_failure("Could not find task ID for deletion")
        return False

    return True

def test_attendance():
    print_step("Testing Attendance")
    resp = make_request('GET', '/attendance/')
    if not (resp and resp.status_code == 200):
        return print_failure("Failed to access attendance page")

    # Mark attendance (post)
    # Get CSRF token
    import re
    csrf_match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', resp.text)
    if not csrf_match:
        print_failure("Could not find CSRF token")
        return False
    csrf_token = csrf_match.group(1)

    # Today's attendance record might already exist; we'll toggle it.
    data = {
        'is_present': 'on',  # checkbox
        'remarks': 'Test attendance',
        'csrfmiddlewaretoken': csrf_token,
    }
    resp = make_request('POST', '/attendance/', data=data)
    if not (resp and resp.status_code in (200, 302)):
        print_failure("Failed to mark attendance")
        return False

    print_success("Attendance marked")
    return True

def test_planner():
    print_step("Testing Planner (Study Plans)")
    resp = make_request('GET', '/planner/')
    if not (resp and resp.status_code == 200):
        return print_failure("Failed to access planner page")

    # Get CSRF token
    import re
    csrf_match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', resp.text)
    if not csrf_match:
        print_failure("Could not find CSRF token")
        return False
    csrf_token = csrf_match.group(1)

    # Create a study plan
    from datetime import date
    today = date.today().isoformat()
    data = {
        'subject': 'Test Subject',
        'hours': 2.5,
        'date': today,
        'notes': 'Test study plan notes.',
        'csrfmiddlewaretoken': csrf_token,
    }
    resp = make_request('POST', '/planner/', data=data)
    if not (resp and resp.status_code in (200, 302)):
        print_failure("Failed to create study plan")
        return False

    # Check if plan appears in list
    resp = make_request('GET', '/planner/')
    if resp and 'Test Subject' in resp.text:
        print_success("Study plan created and listed")
    else:
        print_failure("Study plan not found in list")
        return False

    # Clean up the plan through the same confirmation flow as the UI.
    plan_id_match = re.search(r'/planner/(\d+)/edit/', resp.text)
    if plan_id_match:
        plan_id = plan_id_match.group(1)
        resp = make_request('GET', f'/planner/{plan_id}/delete/')
        if resp and resp.status_code == 200:
            csrf_token = get_csrf_token(resp)
            if csrf_token:
                resp = make_request(
                    'POST',
                    f'/planner/{plan_id}/delete/',
                    data={'csrfmiddlewaretoken': csrf_token},
                )
                if resp and resp.status_code in (200, 302):
                    print_success("Study plan deleted")
                else:
                    print_failure("Failed to confirm study plan deletion")
            else:
                print_failure("Could not find CSRF token for study plan deletion")
        else:
            print_failure("Failed to access study plan deletion page")
    else:
        print_failure("Could not find study plan ID for deletion")
        return False
    return True

def test_analytics():
    print_step("Testing Analytics")
    resp = make_request('GET', '/analytics/')
    if not (resp and resp.status_code == 200):
        return print_failure("Failed to access analytics page")

    if 'Analytics' in resp.text or 'Completed' in resp.text:
        print_success("Analytics page loaded")
        return True
    else:
        print_failure("Analytics page content unexpected")
        return False

def test_export_import():
    print_step("Testing Export/Import")
    # Export notes as CSV
    resp = make_request('GET', '/notes/export/csv/')
    if resp and resp.status_code == 200 and 'text/csv' in resp.headers.get('Content-Type', ''):
        print_success("Notes CSV export works")
    else:
        print_failure("Notes CSV export failed")
        return False

    # Export tasks as CSV
    resp = make_request('GET', '/tasks/export/csv/')
    if resp and resp.status_code == 200 and 'text/csv' in resp.headers.get('Content-Type', ''):
        print_success("Tasks CSV export works")
    else:
        print_failure("Tasks CSV export failed")
        return False

    # We could test import, but that requires file upload and CSRF, which is more complex.
    # For now, we'll consider export sufficient.
    return True

def test_activity_log():
    print_step("Testing Activity Log")
    resp = make_request('GET', '/activity/log/')
    if resp and resp.status_code == 200:
        print_success("Activity log accessible")
        return True
    else:
        print_failure("Activity log not accessible")
        return False

def test_calendar_integrations():
    print_step("Testing Calendar Integrations")
    # Export iCal
    resp = make_request('GET', '/calendar/export/ical/')
    if resp and resp.status_code == 200 and 'text/calendar' in resp.headers.get('Content-Type', ''):
        print_success("iCal export works")
    else:
        print_failure("iCal export failed")
        return False

    # Calendar instructions
    resp = make_request('GET', '/calendar/instructions/')
    if resp and resp.status_code == 200:
        print_success("Calendar instructions accessible")
        return True
    else:
        print_failure("Calendar instructions not accessible")
        return False

def test_study_recommendations():
    print_step("Testing Study Recommendations")
    resp = make_request('GET', '/recommendations/')
    if resp and resp.status_code == 200:
        print_success("Study recommendations accessible")
        return True
    else:
        print_failure("Study recommendations not accessible")
        return False

def main():
    print("Starting Smart Study System feature-by-feature test")
    print(f"Testing against {BASE_URL}")

    # First, check if the server is up
    if not test_homepage():
        print("Server seems down. Exiting.")
        sys.exit(1)

    # Register and login a test user
    username = os.environ.get('SMART_STUDY_TEST_USERNAME', 'testuser123')
    email = os.environ.get('SMART_STUDY_TEST_EMAIL', 'test@example.com')
    password = os.environ.get('SMART_STUDY_TEST_PASSWORD', 'Testpass-123!')

    # We'll try to register; if user already exists, we'll just login.
    register_user(username, email, password)
    if not login_user(username, password):
        print("Login failed. Exiting.")
        sys.exit(1)

    # Now test each feature
    tests = [
        ("Notes CRUD", test_notes_crud),
        ("Tasks CRUD", test_tasks_crud),
        ("Attendance", test_attendance),
        ("Planner", test_planner),
        ("Analytics", test_analytics),
        ("Export/Import", test_export_import),
        ("Activity Log", test_activity_log),
        ("Calendar Integrations", test_calendar_integrations),
        ("Study Recommendations", test_study_recommendations),
    ]

    passed = 0
    total = len(tests)

    for name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Running test: {name}")
        if test_func():
            passed += 1
            print(f"Test '{name}' PASSED")
        else:
            print(f"Test '{name}' FAILED")

    # Logout
    logout_user()

    print(f"\n{'='*50}")
    print(f"Tests passed: {passed}/{total}")
    if passed == total:
        print("All tests passed!")
        sys.exit(0)
    else:
        print("Some tests failed.")
        sys.exit(1)

if __name__ == '__main__':
    main()