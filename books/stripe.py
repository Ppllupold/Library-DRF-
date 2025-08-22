from datetime import date
from decimal import Decimal

import stripe
from django.conf import settings
from django.urls import reverse

from books.models import Payment
from borrowing.models import Borrowing

stripe.api_key = settings.STRIPE_SECRET_KEY

FINE_MULTIPLIER = 2


def create_stripe_session_for_borrowing(
    borrowing: Borrowing, success_url: str, cancel_url: str, fine=False
):
    amount = calculate_amount(borrowing, fine)
    if fine:
        amount *= FINE_MULTIPLIER

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": f"Payment for borrowing #{borrowing.id} - {borrowing.book.title}",
                    },
                    "unit_amount": amount,
                },
                "quantity": 1,
            }
        ],
        mode="payment",
        success_url=success_url,
        cancel_url=cancel_url,
    )

    return session


def renew_stripe_session(
    payment: Payment,
    success_url: str,
    cancel_url: str,
):
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": f"Renew payment for borrowing #{payment.borrowing.id} - {payment.borrowing.book.title}",
                    },
                    "unit_amount": int(Decimal(payment.money_to_pay) * 100),
                },
                "quantity": 1,
            }
        ],
        mode="payment",
        success_url=success_url,
        cancel_url=cancel_url,
    )

    return session


def get_success_url(request):
    return f"{request.build_absolute_uri(reverse('books:payment-success'))}?session_id={{CHECKOUT_SESSION_ID}}"


def get_cancel_url(request):
    return request.build_absolute_uri(reverse("books:payment-cancel"))


def calculate_amount(borrowing: Borrowing, fine=False) -> int:
    if fine:
        return int(
            (borrowing.actual_return_date - borrowing.expected_return_date).days
            * borrowing.book.daily_fee
            * FINE_MULTIPLIER
            * 100
        )
    return int(
        borrowing.book.daily_fee
        * (borrowing.expected_return_date - date.today()).days
        * 100
    )
