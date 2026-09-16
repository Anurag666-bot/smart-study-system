import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Note, NoteAttachment, Task, TaskAttachment


class ProtectedAttachmentTests(TestCase):
    def setUp(self):
        self.media_dir = tempfile.mkdtemp(prefix='smart-study-test-media-')
        self.media_override = override_settings(MEDIA_ROOT=self.media_dir)
        self.media_override.enable()
        self.owner = User.objects.create_user(
            username='attachment-owner', password='safe-pass-123'
        )
        self.other = User.objects.create_user(
            username='attachment-other', password='safe-pass-123'
        )
        self.note = Note.objects.create(
            user=self.owner, title='Private note', content='Content'
        )
        self.task = Task.objects.create(
            user=self.owner, title='Private task', due_date=timezone.localdate()
        )

    def tearDown(self):
        self.media_override.disable()
        shutil.rmtree(self.media_dir, ignore_errors=True)

    def _pdf(self, name='study.pdf'):
        return SimpleUploadedFile(
            name,
            b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF',
            content_type='application/pdf',
        )

    def test_note_attachment_is_owner_scoped_and_downloadable(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('note_attachment_add', args=[self.note.pk]),
            {'file': self._pdf()},
        )
        self.assertRedirects(response, reverse('note_detail', args=[self.note.pk]))
        attachment = NoteAttachment.objects.get(note=self.note)
        self.assertEqual(
            self.client.get(reverse('note_attachment_file', args=[attachment.pk])).status_code,
            200,
        )

        self.client.force_login(self.other)
        self.assertEqual(
            self.client.get(reverse('note_attachment_file', args=[attachment.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(reverse('note_attachment_delete', args=[attachment.pk])).status_code,
            404,
        )

    def test_task_attachment_can_be_removed_by_owner(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('task_attachment_add', args=[self.task.pk]),
            {'file': self._pdf('task.pdf')},
        )
        self.assertRedirects(response, reverse('task_detail', args=[self.task.pk]))
        attachment = TaskAttachment.objects.get(task=self.task)
        response = self.client.post(
            reverse('task_attachment_delete', args=[attachment.pk])
        )
        self.assertRedirects(response, reverse('task_detail', args=[self.task.pk]))
        self.assertFalse(TaskAttachment.objects.filter(pk=attachment.pk).exists())

    def test_disallowed_attachment_type_is_rejected(self):
        self.client.force_login(self.owner)
        upload = SimpleUploadedFile(
            'script.sh', b'#!/bin/sh\necho unsafe', content_type='text/x-shellscript'
        )
        response = self.client.post(
            reverse('note_attachment_add', args=[self.note.pk]),
            {'file': upload},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(NoteAttachment.objects.exists())
