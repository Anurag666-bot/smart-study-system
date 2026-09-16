from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Task, TaskComment


class TaskCommentAccessTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='comment-owner', password='safe-pass-123'
        )
        self.other = User.objects.create_user(
            username='comment-other', password='safe-pass-123'
        )
        self.task = Task.objects.create(
            user=self.owner,
            title='Review joins',
            due_date=timezone.localdate(),
        )

    def test_owner_can_create_and_delete_comment(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse('task_detail', args=[self.task.pk]), {
            'body': 'Remember the foreign-key edge case.',
        })
        self.assertRedirects(response, reverse('task_detail', args=[self.task.pk]))
        comment = TaskComment.objects.get(task=self.task)
        self.assertEqual(comment.author_id, self.owner.id)
        response = self.client.post(
            reverse('task_comment_delete', args=[comment.pk])
        )
        self.assertRedirects(response, reverse('task_detail', args=[self.task.pk]))
        self.assertFalse(TaskComment.objects.filter(pk=comment.pk).exists())

    def test_other_user_cannot_read_or_delete_task_comments(self):
        comment = TaskComment.objects.create(
            task=self.task,
            author=self.owner,
            body='Private comment',
        )
        self.client.force_login(self.other)
        self.assertEqual(
            self.client.get(reverse('task_detail', args=[self.task.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(reverse('task_comment_delete', args=[comment.pk])).status_code,
            404,
        )
