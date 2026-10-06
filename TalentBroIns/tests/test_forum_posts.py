"""Tests for the Discussion Forum endpoints.

Three things here are easy to get wrong and invisible in `manage.py check`:

* the scoping. The forum is intra-institution, and the college always comes from
  the session — never from the body or the URL. A post written by one college must
  not appear on, or be deletable from, another college's board.
* ownership of the delete. There is no edit path at all, so delete is the only
  way a post goes away, and it must reject everybody but the author.
* the notice. Every post raises one institution-scoped Notification, which the
  inbox resolves per reader. That has to reach the rest of the college and stop
  there, and deleting the post has to take its notice with it.
"""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from TalentBroIns.models import (
    CandidateProfile,
    ClientProfile,
    ForumPost,
    Institution,
    Notification,
    NOTIFICATION_SENDER_FORUM,
)

USER_MODEL = get_user_model()

# TalentBroIns/urls.py sets app_name, so every pattern is namespaced.
NAMESPACE = 'TalentBroIns'


def url(name, **kwargs):
    return reverse(f'{NAMESPACE}:{name}', kwargs=kwargs)


def _institution(name, email_domain):
    """Institution rows require an owning user and a pile of non-blank fields."""
    owner = USER_MODEL.objects.create_user(
        email=f'owner@{email_domain}', username=f'owner-{email_domain}', password='pw',
    )
    return Institution.objects.create(
        user=owner,
        name=name,
        institution_type='College',
        email_domain=email_domain,
        address='1 College Road',
        city='Bengaluru',
        state='Karnataka',
        pin_code='560001',
        placement_department_name='Placement Cell',
        placement_office_email=f'placement@{email_domain}',
        approximate_student_strength=1000,
    )


def _student(email, institution, name='Test Student'):
    """A candidate account with a profile attached to *institution*."""
    user = USER_MODEL.objects.create_user(username=email, email=email, password='pw')
    user.first_name, user.last_name = name.split(' ', 1)
    user.save()
    CandidateProfile.objects.create(
        user=user,
        college=institution,
        first_name=name.split(' ', 1)[0],
        last_name=name.split(' ', 1)[1],
        department='Computer Science',
        program='B.Tech',
    )
    return user


def _staff(email, institution):
    user = USER_MODEL.objects.create_user(username=email, email=email, password='pw')
    ClientProfile.objects.create(user=user, institution=institution)
    return user


class ForumPostScopeTests(TestCase):
    def setUp(self):
        self.alpha = _institution('Alpha Institute', 'alpha.test')
        self.beta = _institution('Beta Institute', 'beta.test')

        self.student = _student('one@alpha.test', self.alpha, name='Asha Rao')
        self.classmate = _student('two@alpha.test', self.alpha, name='Bilal Khan')
        self.outsider = _student('three@beta.test', self.beta, name='Chet Iyer')

        self.client.force_login(self.student)

    def _create(self, body, **extra):
        response = self.client.post(
            url('forum-posts'),
            data=json.dumps({'body': body}),
            content_type='application/json',
            **extra,
        )
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()['post']

    def test_post_is_stored_with_college_author_and_timestamps(self):
        post = self._create('Anyone know who takes the DSA lab?')

        row = ForumPost.objects.get(pk=post['id'])
        self.assertEqual(row.institution_id, self.alpha.pk)
        self.assertEqual(row.author.user_id, self.student.pk)
        self.assertEqual(row.body, 'Anyone know who takes the DSA lab?')
        self.assertIsNotNone(row.created_at)
        self.assertIsNotNone(row.updated_at)
        self.assertTrue(post['is_mine'])

    def test_feed_returns_only_the_callers_college(self):
        mine = self._create('Alpha question about placements')

        # A post written straight into the other college's board, as if it had
        # been created there — it must not leak into this student's feed.
        outsider_post = ForumPost.objects.create(
            institution=self.beta,
            author=self.outsider.candidate_profile,
            body='Beta question, not for Alpha',
        )

        response = self.client.get(url('forum-posts'))
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        ids = [p['id'] for p in payload['posts']]
        self.assertIn(mine['id'], ids)
        self.assertNotIn(str(outsider_post.pk), ids)
        self.assertEqual(payload['total'], 1)
        self.assertEqual(payload['institution']['name'], 'Alpha Institute')

    def test_body_cannot_choose_the_college(self):
        # Naming another institution in the payload must not move the post there.
        self._create('Trying to address another college', institution=str(self.beta.pk))
        self.assertEqual(ForumPost.objects.get().institution_id, self.alpha.pk)

    def test_outsider_cannot_delete_someone_elses_post(self):
        post = self._create('Alpha only')

        self.client.force_login(self.outsider)
        response = self.client.delete(url('forum-post-detail', post_id=post['id']))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(ForumPost.objects.filter(pk=post['id']).exists())

    def test_classmate_cannot_delete_the_post_either(self):
        post = self._create('Asha wrote this')

        self.client.force_login(self.classmate)
        response = self.client.delete(url('forum-post-detail', post_id=post['id']))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(ForumPost.objects.filter(pk=post['id']).exists())

    def test_author_can_delete_their_post(self):
        post = self._create('Asha wrote this')

        response = self.client.delete(url('forum-post-detail', post_id=post['id']))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ForumPost.objects.filter(pk=post['id']).exists())

    def test_delete_unknown_post_is_404(self):
        response = self.client.delete(
            url('forum-post-detail', post_id='00000000-0000-0000-0000-000000000000')
        )
        self.assertEqual(response.status_code, 404)

    def test_mine_filter_returns_only_the_callers_posts(self):
        mine = self._create('Asha one')
        self._create('Asha two')

        other = ForumPost.objects.create(
            institution=self.alpha,
            author=self.classmate.candidate_profile,
            body='Bilal one',
        )

        response = self.client.get(url('forum-posts'), {'mine': '1'})
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        ids = [p['id'] for p in payload['posts']]
        self.assertEqual(len(ids), 2)
        self.assertNotIn(str(other.pk), ids)
        self.assertTrue(all(p['is_mine'] for p in payload['posts']))
        self.assertEqual(payload['total'], 2)

    def test_empty_and_overlong_posts_are_rejected(self):
        empty = self.client.post(
            url('forum-posts'),
            data=json.dumps({'body': '   '}),
            content_type='application/json',
        )
        self.assertEqual(empty.status_code, 400)

        long = self.client.post(
            url('forum-posts'),
            data=json.dumps({'body': 'x' * 2001}),
            content_type='application/json',
        )
        self.assertEqual(long.status_code, 400)
        self.assertEqual(ForumPost.objects.count(), 0)

    def test_anonymous_is_rejected(self):
        self.client.logout()
        self.assertEqual(self.client.get(url('forum-posts')).status_code, 401)
        self.assertEqual(
            self.client.post(
                url('forum-posts'),
                data=json.dumps({'body': 'hi'}),
                content_type='application/json',
            ).status_code,
            401,
        )

    def test_feed_is_empty_for_an_account_with_no_college(self):
        orphan = USER_MODEL.objects.create_user(
            username='orphan@nowhere.test', email='orphan@nowhere.test', password='pw',
        )
        CandidateProfile.objects.create(user=orphan)
        self.client.force_login(orphan)

        response = self.client.get(url('forum-posts'))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIsNone(payload['institution'])
        self.assertEqual(payload['posts'], [])

    def test_staff_cannot_post(self):
        cell = _staff('cell@alpha.test', self.alpha)
        self.client.force_login(cell)

        response = self.client.post(
            url('forum-posts'),
            data=json.dumps({'body': 'From the placement cell'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)


class ForumPostNoticeTests(TestCase):
    def setUp(self):
        self.alpha = _institution('Alpha Institute', 'alpha.test')
        self.beta = _institution('Beta Institute', 'beta.test')

        self.poster = _student('one@alpha.test', self.alpha, name='Asha Rao')
        self.classmate = _student('two@alpha.test', self.alpha, name='Bilal Khan')
        self.outsider = _student('three@beta.test', self.beta, name='Chet Iyer')
        self.cell = _staff('cell@alpha.test', self.alpha)
        self.other_cell = _staff('cell@beta.test', self.beta)

        self.client.force_login(self.poster)

    def _post(self, body='Placements for the 2027 batch?'):
        response = self.client.post(
            url('forum-posts'),
            data=json.dumps({'body': body}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201, response.content)
        return ForumPost.objects.get(pk=response.json()['post']['id'])

    def _inbox(self, user):
        self.client.force_login(user)
        response = self.client.get(url('notifications-list'))
        self.assertEqual(response.status_code, 200)
        return response.json()['notifications']

    def test_posting_raises_exactly_one_notice_for_the_college(self):
        post = self._post()

        notices = Notification.objects.filter(sender=NOTIFICATION_SENDER_FORUM)
        self.assertEqual(notices.count(), 1)
        notice = notices.get()
        self.assertEqual(notice.institution_id, self.alpha.pk)
        self.assertEqual(notice.dedupe_key, f'forum_post:{post.pk}')
        self.assertIn('Alpha Institute', notice.title)
        self.assertIn('2027', notice.body)

    def test_notice_reaches_the_whole_college_and_nobody_else(self):
        self._post()

        for member in (self.poster, self.classmate, self.cell):
            titles = [n['title'] for n in self._inbox(member)]
            self.assertTrue(
                any('Discussion Forum' in t for t in titles),
                f'{member} did not receive the forum notice',
            )

        for stranger in (self.outsider, self.other_cell):
            titles = [n['title'] for n in self._inbox(stranger)]
            self.assertFalse(
                any('Discussion Forum' in t for t in titles),
                f'{stranger} received a notice meant for another college',
            )

    def test_notice_can_be_filtered_by_sender(self):
        self._post()

        response = self.client.get(
            url('notifications-list'), {'sender': 'Discussion Forum'}
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(payload['total'], 1)
        self.assertTrue(
            all(n['sender'] == 'Discussion Forum' for n in payload['notifications'])
        )

    def test_deleting_the_post_removes_its_notice(self):
        post = self._post()
        self.assertEqual(
            Notification.objects.filter(dedupe_key=f'forum_post:{post.pk}').count(), 1
        )

        self.client.force_login(self.poster)
        response = self.client.delete(url('forum-post-detail', post_id=post.pk))
        self.assertEqual(response.status_code, 200)

        self.assertFalse(ForumPost.objects.filter(pk=post.pk).exists())
        self.assertFalse(
            Notification.objects.filter(dedupe_key=f'forum_post:{post.pk}').exists()
        )
        self.assertFalse(
            any(
                'Discussion Forum' in n['title']
                for n in self._inbox(self.classmate)
            )
        )