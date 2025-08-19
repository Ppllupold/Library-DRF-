from decimal import Decimal
from unittest.mock import patch
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from model_bakery import baker
from rest_framework.test import APIClient

from books.models import Book, Payment

User = get_user_model()


def book_list_url():
    return reverse("books:book-list")


def book_detail_url(book_id):
    return reverse("books:book-detail", kwargs={"pk": book_id})


def payment_list_url():
    return reverse("books:payment-list")


def payment_detail_url(payment_id):
    return reverse("books:payment-detail", kwargs={"pk": payment_id})


def payment_renew_url(payment_id):
    return reverse("books:payment-renew", kwargs={"pk": payment_id})


def payment_success_url(
    payment_id,
):
    return reverse(
        "books:payment-success",
        kwargs={
            "pk": payment_id,
        },
    )


class TestBookViews(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.book = Book.objects.create(
            title="title",
            author="author",
            cover=Book.CoverType.SOFT,
            inventory=10,
            daily_fee=1.00,
        )
        self.admin_user = User.objects.create_superuser(
            email="<EMAIL>", password="<PASSWORD>"
        )
        self.auth_user = User.objects.create_user(
            email="<EMAIL_AUTH>", password="<PASSWORD_AUTH>"
        )
        self.anon_user = User.objects.create_user(
            email="<EMAIL_ANON>", password="<PASSWORD_ANON>"
        )

    def test_write_action_allowed_for_admin(self):
        self.client.force_authenticate(user=self.admin_user)

        payload = {
            "title": "title",
            "author": "author",
            "cover": Book.CoverType.SOFT,
            "inventory": 10,
            "daily_fee": "1.00",
        }

        response = self.client.post(book_list_url(), data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertEqual(Book.objects.count(), 2)

        self.assertEqual(response.data["title"], payload["title"])
        self.assertEqual(response.data["author"], payload["author"])
        self.assertEqual(response.data["cover"], payload["cover"])
        self.assertEqual(response.data["inventory"], payload["inventory"])
        self.assertEqual(str(response.data["daily_fee"]), payload["daily_fee"])

    def test_write_action_forbidden_for_not_staff(self):
        self.client.force_authenticate(user=self.auth_user)

        payload = {
            "title": "title",
            "author": "author",
            "cover": Book.CoverType.SOFT,
            "inventory": 10,
            "daily_fee": "1.00",
        }
        payload_update = {
            "title": "title",
            "author": "author",
        }

        response_post = self.client.post(book_list_url(), data=payload, format="json")
        response_update = self.client.put(
            book_detail_url(self.book.id), data=payload_update, format="json"
        )
        response_partial_update = self.client.patch(
            book_detail_url(self.book.id), data=payload_update, format="json"
        )
        response_delete = self.client.delete(
            book_detail_url(self.book.id), format="json"
        )
        self.assertEqual(response_post.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response_update.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response_partial_update.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response_delete.status_code, status.HTTP_403_FORBIDDEN)

    def test_book_list_allow_any(self):
        response = self.client.get(book_list_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class PaymentViewSetTests(TestCase):
    def _mock_session(self, sid="cs_new_test", url="https://stripe.test/new"):
        return SimpleNamespace(id=sid, url=url)

    def _session(self, session_id="cs_any", payment_status="paid"):
        return SimpleNamespace(id=session_id, payment_status=payment_status)

    def setUp(self):
        self.client = APIClient()

        self.admin = User.objects.create_user(
            email="admin@example.com", password="pass", is_staff=True
        )
        self.user1 = User.objects.create_user(email="u1@example.com", password="pass")
        self.user2 = User.objects.create_user(email="u2@example.com", password="pass")

        self.borrowing_u1 = baker.make("borrowing.Borrowing", user=self.user1)
        self.borrowing_u2 = baker.make("borrowing.Borrowing", user=self.user2)

        self.payment_u1 = baker.make(
            Payment,
            borrowing=self.borrowing_u1,
            status=Payment.Status.PENDING,
            type=Payment.Type.PAYMENT,
            money_to_pay=Decimal("10.00"),
            session_url="https://stripe.test/u1",
            session_id="cs_test_u1",
        )
        self.payment_u2 = baker.make(
            Payment,
            borrowing=self.borrowing_u2,
            status=Payment.Status.PENDING,
            type=Payment.Type.PAYMENT,
            money_to_pay=Decimal("20.00"),
            session_url="https://stripe.test/u2",
            session_id="cs_test_u2",
        )

    def test_list_requires_authentication(self):
        res = self.client.get(payment_list_url())
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_shows_only_own_payments_for_non_staff(self):
        self.client.force_authenticate(self.user1)

        res = self.client.get(payment_list_url())
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["id"], self.payment_u1.id)

        item_keys = set(res.data[0].keys())
        self.assertEqual(item_keys, {"id", "status", "type", "money_to_pay"})

    def test_retrieve_own_payment_uses_detail_serializer(self):
        self.client.force_authenticate(self.user1)

        res = self.client.get(payment_detail_url(self.payment_u1.id))
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        keys = set(res.data.keys())
        self.assertTrue(
            {
                "id",
                "status",
                "type",
                "money_to_pay",
                "session_url",
                "session_id",
                "borrowing",
            }.issubset(keys)
        )

        self.assertEqual(res.data["id"], self.payment_u1.id)
        self.assertEqual(str(res.data["money_to_pay"]), "10.00")

    def test_retrieve_other_users_payment_returns_404_for_non_staff(self):
        self.client.force_authenticate(self.user1)

        res = self.client.get(payment_detail_url(self.payment_u2.id))
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_list_sees_all_payments(self):
        self.client.force_authenticate(self.admin)

        res = self.client.get(payment_list_url())
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        returned_ids = {item["id"] for item in res.data}
        self.assertEqual(returned_ids, {self.payment_u1.id, self.payment_u2.id})

    def test_admin_can_retrieve_any_payment(self):
        self.client.force_authenticate(self.admin)

        res = self.client.get(payment_detail_url(self.payment_u2.id))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["id"], self.payment_u2.id)
        self.assertIn("session_url", res.data)
        self.assertIn("borrowing", res.data)

    @patch("books.stripe.get_cancel_url", return_value="https://site.test/cancel")
    @patch("books.stripe.get_success_url", return_value="https://site.test/success")
    @patch("books.stripe.renew_stripe_session")
    def test_renew_fails_if_not_expired(self, mock_renew, mock_success, mock_cancel):
        self.client.force_authenticate(self.user1)
        url = payment_renew_url(self.payment_u1)

        res = self.client.post(url, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        mock_renew.assert_not_called()

        self.payment_u1.refresh_from_db()
        self.assertEqual(self.payment_u1.status, Payment.Status.PENDING)

    @patch("books.views.get_cancel_url", return_value="https://site.test/cancel")
    @patch("books.views.get_success_url", return_value="https://site.test/success")
    @patch("books.views.renew_stripe_session")
    def test_owner_can_renew_expired_payment(
        self, mock_renew, mock_success, mock_cancel
    ):
        self.client.force_authenticate(self.user1)
        mock_renew.return_value = self._mock_session(
            sid="cs_new_owner", url="https://stripe.test/new_owner"
        )
        self.payment_u1.status = Payment.Status.EXPIRED
        self.payment_u1.save(update_fields=["status"])

        res = self.client.post(payment_renew_url(self.payment_u1.id), format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["detail"], "Session renewed")
        self.assertEqual(res.data["session_id"], "cs_new_owner")
        self.assertEqual(res.data["session_url"], "https://stripe.test/new_owner")

        self.payment_u1.refresh_from_db()
        self.assertEqual(self.payment_u1.status, Payment.Status.PENDING)
        self.assertEqual(self.payment_u1.session_id, "cs_new_owner")
        self.assertEqual(self.payment_u1.session_url, "https://stripe.test/new_owner")

        mock_renew.assert_called_once()
        called_payment = mock_renew.call_args.args[0]
        self.assertEqual(called_payment.id, self.payment_u1.id)

    @patch("books.views.get_cancel_url", return_value="https://site.test/cancel")
    @patch("books.views.get_success_url", return_value="https://site.test/success")
    @patch("books.views.renew_stripe_session")
    def test_admin_can_renew_any_expired_payment(
        self, mock_renew, mock_success, mock_cancel
    ):
        self.client.force_authenticate(self.admin)
        mock_renew.return_value = self._mock_session(
            sid="cs_new_admin", url="https://stripe.test/new_admin"
        )
        self.payment_u2.status = Payment.Status.EXPIRED
        self.payment_u2.save(update_fields=["status"])

        res = self.client.post(payment_renew_url(self.payment_u2.id), format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["session_id"], "cs_new_admin")

        self.payment_u2.refresh_from_db()
        self.assertEqual(self.payment_u2.status, Payment.Status.PENDING)
        self.assertEqual(self.payment_u2.session_id, "cs_new_admin")
        self.assertEqual(self.payment_u2.session_url, "https://stripe.test/new_admin")

    def test_payment_success_no_session_id_400(self):
        self.client.force_authenticate(self.user1)
        res = self.client.get(
            payment_success_url(self.payment_u1.id, None), format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("books.views.stripe.checkout.Session.retrieve")
    def test_success_mark_payment_paid_when_stripe_paid(self, mock_retrieve):
        self.client.force_authenticate(self.user1)
        mock_retrieve.return_value = self._session(
            session_id=self.payment_u1.session_id, payment_status="paid"
        )
        response = self.client.get(
            payment_success_url(self.payment_u1.id), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.payment_u1.refresh_from_db()
        self.assertEqual(self.payment_u1.status, Payment.Status.PAID)

    @patch("books.views.stripe.checkout.Session.retrieve")
    def test_success_is_idempotent_if_already_paid(self, mock_retrieve):
        self.client.force_authenticate(self.user1)

        self.payment_u1.status = Payment.Status.PAID
        self.payment_u1.save(update_fields=["status"])

        mock_retrieve.return_value = self._session(
            session_id=self.payment_u1.session_id,
            payment_status="paid",
        )
        response = self.client.get(
            payment_success_url(self.payment_u1.id), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.payment_u1.refresh_from_db()
        self.assertEqual(self.payment_u1.status, Payment.Status.PAID)

    @patch(
        "books.views.stripe.checkout.Session.retrieve",
        side_effect=Exception("bad_session"),
    )
    def test_success_session_error_404(self, mock_retrieve):
        self.client.force_authenticate(self.user1)
        response = self.client.get(
            payment_success_url(self.payment_u1.id), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
