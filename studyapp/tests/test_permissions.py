from django.contrib.auth import get_user_model
from django.test import TestCase

from studyapp.models import Role, UserRole
from studyapp.permissions import (
    is_admin,
    is_student,
    is_teacher,
    require_role,
    user_has_role,
)

User = get_user_model()


class RolePermissionHelpersTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            username='student-role-helper', password='safe-pass-123'
        )
        self.teacher = User.objects.create_user(
            username='teacher-role-helper', password='safe-pass-123'
        )
        self.admin = User.objects.create_user(
            username='admin-role-helper', password='safe-pass-123'
        )

        UserRole.objects.filter(profile=self.student.profile).delete()
        UserRole.objects.filter(profile=self.teacher.profile).delete()
        UserRole.objects.filter(profile=self.admin.profile).delete()

        UserRole.objects.create(
            profile=self.student.profile,
            role=Role.objects.get(code='student'),
        )
        UserRole.objects.create(
            profile=self.teacher.profile,
            role=Role.objects.get(code='teacher'),
        )
        UserRole.objects.create(
            profile=self.admin.profile,
            role=Role.objects.get(code='administrator'),
        )

    def test_user_has_role_uses_project_role_records(self):
        self.assertTrue(user_has_role(self.student, 'student'))
        self.assertTrue(user_has_role(self.teacher, 'teacher'))
        self.assertTrue(user_has_role(self.admin, 'administrator'))
        self.assertFalse(user_has_role(self.student, 'teacher'))
        self.assertFalse(user_has_role(self.teacher, 'administrator'))

    def test_role_helper_wrappers_match_boundaries(self):
        self.assertTrue(is_student(self.student))
        self.assertTrue(is_teacher(self.teacher))
        self.assertTrue(is_admin(self.admin))
        self.assertFalse(is_student(self.teacher))
        self.assertFalse(is_teacher(self.student))
        self.assertFalse(is_admin(self.student))

    def test_require_role_returns_boolean_for_role_boundaries(self):
        self.assertTrue(require_role(self.student, 'student'))
        self.assertFalse(require_role(self.teacher, 'student'))
        self.assertTrue(require_role(self.teacher, 'teacher'))
        self.assertFalse(require_role(self.student, 'administrator'))
        self.assertTrue(require_role(self.admin, 'administrator'))
