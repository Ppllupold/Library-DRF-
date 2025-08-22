from datetime import date

from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    extend_schema,
    OpenApiExample,
    OpenApiResponse,
    OpenApiParameter,
    extend_schema_view,
)
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


@extend_schema_view(
    list=extend_schema(
        summary="List borrowings",
        description=(
            "• For regular users, only their own borrowings are returned.\n"
            "• For staff users, borrowings can be filtered by `user_id`.\n"
            "• Use `is_active=true|false` to filter by active/returned borrowings."
        ),
        parameters=[
            OpenApiParameter(
                name="user_id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter borrowings by user (available to staff only).",
            ),
            OpenApiParameter(
                name="is_active",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                required=False,
                description="`true` — only active (not returned) borrowings, `false` — only returned.",
            ),
        ],
        responses={
            200: BorrowingReadSerializer(many=True),
            401: OpenApiResponse(description="Unauthorized"),
            403: OpenApiResponse(
                description="Forbidden (non-staff attempted to filter by user_id)"
            ),
        },
        examples=[
            OpenApiExample(
                "Active borrowings of current user",
                value={
                    "results": [
                        {
                            "id": 12,
                            "expected_return_date": "2025-09-10",
                            "actual_return_date": None,
                            "book": {
                                "id": 3,
                                "title": "Clean Architecture",
                                "inventory": 2,
                                "daily_fee": "1.50",
                            },
                            "user": 7,
                            "payments": [],
                        }
                    ]
                },
            )
        ],
        tags=["Borrowings"],
    ),
    retrieve=extend_schema(
        summary="Retrieve borrowing details",
        responses={
            200: BorrowingReadSerializer,
            401: OpenApiResponse(description="Unauthorized"),
            404: OpenApiResponse(description="Not found"),
        },
        tags=["Borrowings"],
    ),
    create=extend_schema(
        summary="Create a borrowing",
        description=(
            "Creates a new borrowing for the current user. "
            "A pending `Payment` is also created and a Telegram message is sent. "
            "If the user already has pending payments, a 400 error is returned."
        ),
        request=BorrowingCreateSerializer,
        responses={
            201: BorrowingCreateSerializer,
            400: OpenApiResponse(
                description="User has pending payments or invalid data"
            ),
            401: OpenApiResponse(description="Unauthorized"),
        },
        examples=[
            OpenApiExample(
                "Example request",
                request_only=True,
                value={"book": 3, "expected_return_date": "2025-09-10"},
            ),
            OpenApiExample(
                "Example response",
                response_only=True,
                value={
                    "id": 42,
                    "expected_return_date": "2025-09-10",
                    "book": 3,
                    "payments": [],
                },
            ),
        ],
        tags=["Borrowings"],
    ),
)
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

    @extend_schema(
        summary="Return a borrowing",
        description=(
            "Return a book for a specific borrowing.\n\n"
            "• Allowed for the borrowing owner or staff.\n"
            "• If already returned, responds with 400.\n"
            "• If overdue, a fine `Payment` is created and a redirect to the payment detail endpoint is returned.\n"
            "• If not overdue, responds with 200 and a success message.\n"
            "• In all cases, the book inventory is increased by 1."
        ),
        responses={
            200: OpenApiResponse(description="Successful return without fine"),
            302: OpenApiResponse(description="Redirect to fine payment detail"),
            400: OpenApiResponse(description="Borrowing already returned"),
            401: OpenApiResponse(description="Unauthorized"),
            403: OpenApiResponse(description="Forbidden (not owner and not staff)"),
            404: OpenApiResponse(
                description="Borrowing not found (filtered out by queryset)"
            ),
        },
        tags=["Borrowings"],
        examples=[
            OpenApiExample(
                "Successful return without fine",
                response_only=True,
                value={"detail": "Book 'Clean Architecture' returned successfully."},
            )
        ],
    )
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
