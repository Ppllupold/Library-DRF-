from datetime import date

from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from books.models import Payment
from books.stripe import (
    create_stripe_session_for_borrowing,
    get_success_url,
    get_cancel_url,
)
from borrowing.bot import send_telegram_message
from borrowing.models import Borrowing
from borrowing.serializers import BorrowingCreateSerializer, BorrowingReadSerializer


class BorrowingViewSet(
    viewsets.GenericViewSet,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
):
    permission_classes = (IsAuthenticated,)
    authentication_classes = (JWTAuthentication,)
    queryset = Borrowing.objects.select_related("book", "user")

    def get_queryset(self):
        user = self.request.user
        user_id = self.request.query_params.get("user_id")
        is_active = self.request.query_params.get("is_active")

        if not user.is_staff and user_id is not None:
            raise PermissionDenied("Filtering by user_id is allowed for staff only.")

        if user.is_staff:
            queryset = Borrowing.objects.select_related("book", "user")
            if user_id is not None:
                queryset = queryset.filter(user_id=user_id)
        else:
            queryset = Borrowing.objects.filter(user=user)

        if is_active is not None:
            if is_active.lower() == "true":
                queryset = queryset.filter(actual_return_date__isnull=True)
            elif is_active.lower() == "false":
                queryset = queryset.filter(actual_return_date__isnull=False)

        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return BorrowingCreateSerializer
        return BorrowingReadSerializer

    def perform_create(self, serializer):
        if Payment.objects.filter(
            borrowing__user=self.request.user, status=Payment.Status.PENDING
        ).exists():
            raise ValidationError(
                "You have pending payments. Please complete them before borrowing new books."
            )

        borrowing = serializer.save(user=self.request.user)

        session = create_stripe_session_for_borrowing(
            borrowing,
            success_url=get_success_url(self.request),
            cancel_url=get_cancel_url(self.request),
        )
        Payment.objects.create(
            type=Payment.Type.PAYMENT,
            borrowing=borrowing,
            session_id=session.id,
            session_url=session.url,
            money_to_pay=session.amount_total / 100,
        )
        message = (
            f"📚 New borrowing created!\n\n"
            f"👤 User: {borrowing.user.email}\n"
            f"📖 Book: {borrowing.book.title}\n"
            f"📅 Expected return: {borrowing.expected_return_date}"
        )
        send_telegram_message(message)

    @action(detail=True, methods=["post"], url_path="return", url_name="return")
    def return_borrowing(self, request, pk=None):
        borrowing = self.get_object()

        if not request.user.is_staff and borrowing.user != request.user:
            return Response(
                {"detail": "You cannot return someone else's borrowing."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if borrowing.actual_return_date is not None:
            return Response(
                {"detail": "This borrowing has already been returned."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment = None
        borrowing.actual_return_date = date.today()

        if borrowing.expected_return_date < borrowing.actual_return_date:
            session = create_stripe_session_for_borrowing(
                borrowing=borrowing,
                success_url=get_success_url(request),
                cancel_url=get_cancel_url(request),
                fine=True,
            )
            payment = Payment.objects.create(
                borrowing=borrowing,
                type=Payment.Type.FINE,
                session_id=session.id,
                session_url=session.url,
                money_to_pay=session.amount_total / 100,
            )

        borrowing.book.inventory += 1
        borrowing.book.save()
        borrowing.save(update_fields=["actual_return_date"])

        if payment:
            return redirect("books:payment-detail", pk=payment.id)

        return Response(
            {"detail": f"Book '{borrowing.book.title}' returned successfully."},
            status=status.HTTP_200_OK,
        )
