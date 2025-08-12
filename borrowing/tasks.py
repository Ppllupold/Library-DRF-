import logging
from datetime import date

import stripe.checkout
from celery import shared_task

from books.models import Payment
from borrowing.bot import send_telegram_message
from borrowing.models import Borrowing

logger = logging.getLogger(__name__)


@shared_task
def check_overdue_borrowings() -> None:
    logger.info("Running overdue borrowings check task")
    overdue_borrowings = Borrowing.objects.filter(
        expected_return_date__lt=date.today(), actual_return_date__isnull=True
    )

    results = [f"#borrowings_overdue\n" f"{date.today()} \n\n\n"]
    if overdue_borrowings:
        for borrowing in overdue_borrowings:
            overdue_days = (date.today() - borrowing.expected_return_date).days
            results.append(
                f"borrowing_id: {borrowing.id}\n"
                f"user_email: {borrowing.user.email}\n"
                f"book: {borrowing.book.title}\n"
                f"overdue: {overdue_days} days"
            )
    else:
        results.append("No borrowings overdue today!")
    logger.info(f"Prepared message: {results}")
    try:
        send_telegram_message("\n".join(results))
    except Exception as e:
        logger.error(f"Failed to send message: {e}")


@shared_task
def track_expired_sessions() -> None:
    pending_payments = Payment.objects.filter(
        status=Payment.Status.PENDING, session_id__isnull=False
    )
    for payment in pending_payments:
        session = stripe.checkout.Session.retrieve(payment.session_id)
        if session.status == "expired":
            payment.status = Payment.Status.EXPIRED
            payment.save()
