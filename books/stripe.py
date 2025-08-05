from datetime import date

import stripe
from django.conf import settings
from django.urls import reverse

from borrowing.models import Borrowing

stripe.api_key = settings.STRIPE_SECRET_KEY


def create_stripe_session_for_borrowing(
    borrowing: Borrowing, success_url: str, cancel_url: str
):
    amount = int(
        borrowing.book.daily_fee
        * (borrowing.expected_return_date - date.today()).days
        * 100
    )

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


def get_success_url(request):
    return f"{request.build_absolute_uri(reverse('books:payment-success'))}?session_id={{CHECKOUT_SESSION_ID}}"


def get_cancel_url(request):
    return request.build_absolute_uri(reverse("books:payment-cancel"))
