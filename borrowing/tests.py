from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from model_bakery import baker

from books.models import Book
from borrowing.models import Borrowing
from books.models import Payment

from urllib.parse import urlencode

User = get_user_model()


def borrowing_list(is_active=None, user_id=None):
    base_url = reverse("borrowings:borrowing-list")
    query_params = {}
    if is_active is not None:
        query_params["is_active"] = is_active
    if user_id is not None:
        query_params["user_id"] = user_id
    if query_params:
        return f"{base_url}?{urlencode(query_params)}"
    return base_url


def borrowing_return_url(pk: int) -> str:
    return reverse("borrowings:borrowing-return", kwargs={"pk": pk})


class BorrowingViewsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        # users
        self.admin = User.objects.create_user(
            email="admin@example.com", password="pass", is_staff=True
        )
        self.user_no_borrowings = User.objects.create(
            email="new@example.com", password="pass"
        )
        self.user = User.objects.create_user(email="user@example.com", password="pass")
        self.other = User.objects.create_user(
            email="other@example.com", password="pass"
        )

        # book
        self.book = baker.make(
            Book,
            title="Clean Architecture",
            inventory=3,
            daily_fee=Decimal("1.50"),
        )

        # active borrowing for self.user (still not returned)
        self.borrowing_active_1 = baker.make(
            Borrowing,
            user=self.user,
            book=self.book,
            expected_return_date=date.today() + timedelta(days=3),
            actual_return_date=None,
        )

        self.borrowing_active_2 = baker.make(
            Borrowing,
            user=self.user,
            book=self.book,
            expected_return_date=date.today() + timedelta(days=1),
            actual_return_date=None,
        )
        # another user's borrowing
        self.borrowing_other = baker.make(
            Borrowing,
            user=self.other,
            book=self.book,
            expected_return_date=date.today() + timedelta(days=5),
            actual_return_date=None,
        )

        self.pending_payment = baker.make(
            Payment,
            borrowing=self.borrowing_active_1,
            status=Payment.Status.PENDING,
            type=Payment.Type.PAYMENT if hasattr(Payment, "Type") else "Payment",
            session_id="cs_test_pending",
            session_url="https://stripe.test/pending",
            money_to_pay=Decimal("10.00"),
        )

    def test_user_see_only_his_borrowings(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(borrowing_list())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for borrowing in response.data:
            self.assertEqual(borrowing["user"], self.user.id)
        returned_ids = [borrowing["id"] for borrowing in response.data]

        other_borrowing = Borrowing.objects.get(user=self.other)
        self.assertNotIn(other_borrowing.id, returned_ids)

    def test_admin_can_see_other_users_borrowings(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(borrowing_list(user_id=self.user.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for borrowing in response.data:
            self.assertEqual(borrowing["user"], self.user.id)

    def test_user_can_see_other_users_borrowings_forbidden(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(borrowing_list(user_id=self.other.id))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_filter_by_is_active_true(self):
        self.borrowing_active_1.actual_return_date = (
            self.borrowing_active_1.expected_return_date
        )
        self.borrowing_active_1.save(update_fields=["actual_return_date"])

        self.client.force_authenticate(self.user)

        response_with_active = self.client.get(borrowing_list(is_active=True))
        response_default = self.client.get(borrowing_list())

        self.assertEqual(response_with_active.status_code, status.HTTP_200_OK)

        for borrowing in response_with_active.data:
            self.assertIsNone(borrowing["actual_return_date"])
        self.assertNotEquals(len(response_with_active.data), len(response_default.data))

    def test_filter_by_is_active_false(self):
        self.borrowing_active_1.actual_return_date = (
            self.borrowing_active_1.expected_return_date
        )
        self.borrowing_active_1.save(update_fields=["actual_return_date"])

        self.client.force_authenticate(self.user)

        response_with_active = self.client.get(borrowing_list(is_active=False))
        response_default = self.client.get(borrowing_list())

        self.assertEqual(response_with_active.status_code, status.HTTP_200_OK)

        for borrowing in response_with_active.data:
            self.assertIsNotNone(borrowing["actual_return_date"])
        self.assertNotEquals(len(response_with_active.data), len(response_default.data))

    def test_list_uses_BorrowingReadSerializer_fields(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(borrowing_list())
        borrowing_dict = response.data[0]
        self.assertIn("id", borrowing_dict)
        self.assertIn("actual_return_date", borrowing_dict)
        self.assertIn("expected_return_date", borrowing_dict)
        self.assertIn("book", borrowing_dict)
        self.assertIn("user", borrowing_dict)
        self.assertIn("payments", borrowing_dict)

    @patch("borrowing.views.send_telegram_message")
    @patch("borrowing.views.get_cancel_url", return_value="https://site.test/cancel")
    @patch("borrowing.views.get_success_url", return_value="https://site.test/success")
    @patch("borrowing.views.create_stripe_session_for_borrowing")
    def test_post_uses_BorrowingCreate_serializer_field(
        self, mock_cs, _mock_success, _mock_cancel, _mock_tg
    ):
        self.client.force_authenticate(self.user_no_borrowings)

        mock_cs.return_value = type(
            "Sess",
            (),
            {"id": "cs_new", "url": "https://stripe.test/new", "amount_total": 500},
        )()

        payload = {
            "expected_return_date": (date.today() + timedelta(days=5)).isoformat(),
            "book": self.book.id,
        }
        response = self.client.post(borrowing_list(), data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertIn("expected_return_date", response.data)
        self.assertIn("book", response.data)
        self.assertIn("payments", response.data)

    def test_user_can_not_make_a_borrowing_if_a_pending_payment_exists(self):
        self.client.force_authenticate(self.user)
        payload = {
            "expected_return_date": (date.today() + timedelta(days=5)).isoformat(),
            "book": self.book.id,
        }
        response = self.client.post(borrowing_list(), data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("borrowing.views.send_telegram_message")
    @patch("borrowing.views.get_cancel_url", return_value="https://site.test/cancel")
    @patch("borrowing.views.get_success_url", return_value="https://site.test/success")
    @patch("borrowing.views.create_stripe_session_for_borrowing")
    def test_borrowing_perform_create_payment_for_borrowing(
        self, mock_cs: MagicMock, _mock_success, _mock_cancel, _mock_tg
    ):
        self.client.force_authenticate(self.user_no_borrowings)

        mock_cs.return_value.id = "cs_new_123"
        mock_cs.return_value.url = "https://stripe.test/new"
        mock_cs.return_value.amount_total = 500

        payload = {
            "expected_return_date": (date.today() + timedelta(days=5)).isoformat(),
            "book": self.book.id,
        }
        response = self.client.post(borrowing_list(), data=payload, format="json")
        payment_for_borrowing = Payment.objects.get(borrowing_id=response.data["id"])

        mock_cs.assert_called_once()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.book.refresh_from_db()
        self.assertEqual(self.book.inventory, 2)
        self.assertIsNotNone(payment_for_borrowing)
        self.assertEqual(
            payment_for_borrowing.money_to_pay, mock_cs.return_value.amount_total / 100
        )

        _mock_tg.assert_called_once()

        send_text = _mock_tg.call_args.args[0]
        self.assertIn(self.user_no_borrowings.email, send_text)
        self.assertIn(self.book.title, send_text)
        self.assertIn(
            Borrowing.objects.get(
                id=response.data["id"]
            ).expected_return_date.isoformat(),
            send_text,
        )

    def test_return_forbidden_for_non_owner(self):
        self.client.force_authenticate(self.user)
        url = borrowing_return_url(self.borrowing_other.id)
        res = self.client.post(url)
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_return_already_returned_400(self):
        self.client.force_authenticate(self.user)
        self.borrowing_active_1.actual_return_date = date.today()
        self.borrowing_active_1.save()
        url = borrowing_return_url(self.borrowing_active_1.id)
        res = self.client.post(url)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_can_return_others_borrowing(self):
        self.client.force_authenticate(self.admin)
        start_inventory = self.book.inventory
        url = borrowing_return_url(self.borrowing_other.id)
        res = self.client.post(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.book.refresh_from_db()
        self.assertEqual(self.book.inventory, start_inventory + 1)

    def test_return_ok_no_fine_increments_inventory(self):
        self.client.force_authenticate(self.user)
        start_inventory = self.book.inventory
        url = borrowing_return_url(self.borrowing_active_1.id)
        res = self.client.post(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.borrowing_active_1.refresh_from_db()
        self.assertIsNotNone(self.borrowing_active_1.actual_return_date)

        self.book.refresh_from_db()
        self.assertEqual(self.book.inventory, start_inventory + 1)

        self.assertFalse(
            Payment.objects.filter(
                borrowing=self.borrowing_active_1, type=Payment.Type.FINE
            ).exists()
        )

    @patch("borrowing.views.get_cancel_url", return_value="https://site.test/cancel")
    @patch("borrowing.views.get_success_url", return_value="https://site.test/success")
    @patch("borrowing.views.create_stripe_session_for_borrowing")
    def test_return_overdue_creates_fine_and_redirects(self, mock_cs, _ms, _mc):
        self.client.force_authenticate(self.user)

        self.borrowing_active_1.borrow_date = date.today() - timedelta(days=7)
        self.borrowing_active_1.expected_return_date = date.today() - timedelta(days=1)
        self.borrowing_active_1.save(
            update_fields=["borrow_date", "expected_return_date"]
        )

        mock_cs.return_value = SimpleNamespace(
            id="cs_fine_123",
            url="https://stripe.test/fine",
            amount_total=750,
        )

        start_inventory = self.book.inventory
        url = borrowing_return_url(self.borrowing_active_1.id)
        res = self.client.post(url)
        self.assertIn(res.status_code, (301, 302))
        self.borrowing_active_1.refresh_from_db()

        payment = (
            Payment.objects.filter(
                borrowing=self.borrowing_active_1, type=Payment.Type.FINE
            )
            .order_by("-id")
            .first()
        )
        self.assertIsNotNone(payment)
        self.assertEqual(payment.session_id, "cs_fine_123")
        self.assertEqual(payment.session_url, "https://stripe.test/fine")
        self.assertEqual(payment.money_to_pay, Decimal("7.50"))

        self.assertTrue(mock_cs.called)
        _, kwargs = mock_cs.call_args
        self.assertTrue(kwargs.get("fine"))

        self.book.refresh_from_db()
        self.assertEqual(self.book.inventory, start_inventory + 1)
