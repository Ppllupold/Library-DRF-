import stripe
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_extensions.mixins import DetailSerializerMixin
from rest_framework_simplejwt.authentication import JWTAuthentication

from rest_framework import serializers
from books.models import Book, Payment
from books.permissions import IsAdminOrOwnerReadOnlyRenewOnly
from books.serializers import (
    BookSerializer,
    PaymentDetailSerializer,
    PaymentSerializer,
)
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiResponse,
    OpenApiExample,
    inline_serializer,
)
from books.stripe import renew_stripe_session, get_success_url, get_cancel_url

WRITE_ACTIONS = ["create", "update", "partial_update", "destroy"]


@extend_schema_view(
    list=extend_schema(
        summary="List books",
        description=(
            "Public endpoint. Returns the list of books. " "No authentication required."
        ),
        responses={200: BookSerializer(many=True)},
        tags=["Books"],
    ),
    retrieve=extend_schema(
        summary="Retrieve a book",
        description="Authenticated users can retrieve a single book by ID.",
        responses={
            200: BookSerializer,
            401: OpenApiResponse(description="Unauthorized"),
            404: OpenApiResponse(),
        },
        tags=["Books"],
    ),
    create=extend_schema(
        summary="Create a book",
        description="Admin-only endpoint to create a book.",
        request=BookSerializer,
        responses={201: BookSerializer, 401: OpenApiResponse(), 403: OpenApiResponse()},
        tags=["Books"],
    ),
    update=extend_schema(
        summary="Update a book",
        description="Admin-only full update.",
        request=BookSerializer,
        responses={
            200: BookSerializer,
            401: OpenApiResponse(),
            403: OpenApiResponse(),
            404: OpenApiResponse(),
        },
        tags=["Books"],
    ),
    partial_update=extend_schema(
        summary="Partially update a book",
        description="Admin-only partial update.",
        request=BookSerializer,
        responses={
            200: BookSerializer,
            401: OpenApiResponse(),
            403: OpenApiResponse(),
            404: OpenApiResponse(),
        },
        tags=["Books"],
    ),
    destroy=extend_schema(
        summary="Delete a book",
        description="Admin-only deletion.",
        responses={
            204: OpenApiResponse(description="No Content"),
            401: OpenApiResponse(),
            403: OpenApiResponse(),
            404: OpenApiResponse(),
        },
        tags=["Books"],
    ),
)
class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.all()
    serializer_class = BookSerializer
    authentication_classes = (JWTAuthentication,)

    def get_permissions(self):
        if self.action in WRITE_ACTIONS:
            permission_classes = [permissions.IsAdminUser]
        elif self.action == "retrieve":
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.AllowAny]
        return [permission() for permission in permission_classes]


@extend_schema_view(
    list=extend_schema(
        summary="List payments",
        description=(
            "Authenticated endpoint. Regular users see **only their own** payments. "
            "Staff sees all payments."
        ),
        responses={
            200: PaymentSerializer(many=True),
            401: OpenApiResponse(description="Unauthorized"),
        },
        tags=["Payments"],
    ),
    retrieve=extend_schema(
        summary="Retrieve a payment",
        description=(
            "Authenticated endpoint. Regular users can retrieve only their own payments. "
            "Staff can retrieve any payment."
        ),
        responses={
            200: PaymentDetailSerializer,
            401: OpenApiResponse(),
            404: OpenApiResponse(),
        },
        tags=["Payments"],
    ),
)
class PaymentViewSet(DetailSerializerMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Payment.objects.select_related("borrowing", "borrowing__user")
    serializer_class = PaymentSerializer
    serializer_detail_class = PaymentDetailSerializer
    permission_classes = [IsAuthenticated, IsAdminOrOwnerReadOnlyRenewOnly]
    http_method_names = ["get", "head", "options", "post"]

    def get_queryset(self):
        user = self.request.user
        return (
            self.queryset
            if user.is_staff
            else self.queryset.filter(borrowing__user=user)
        )

    @extend_schema(
        summary="Renew an expired payment session",
        description=(
            "Detail action. Only the owner (or staff) can renew. "
            "Works **only** if payment status is `EXPIRED`. "
            "Sets status to `PENDING` and returns a fresh Stripe session."
        ),
        responses={
            200: inline_serializer(
                name="PaymentRenewResponse",
                fields={
                    "detail": serializers.CharField(),
                    "session_id": serializers.CharField(),
                    "session_url": serializers.URLField(),
                },
            ),
            400: inline_serializer(
                name="PaymentRenewError",
                fields={"detail": serializers.CharField()},
            ),
            401: OpenApiResponse(description="Unauthorized"),
            404: OpenApiResponse(
                description="Not found (filtered by queryset/ownership)"
            ),
        },
        examples=[
            OpenApiExample(
                "Renewed",
                value={
                    "detail": "Session renewed",
                    "session_id": "cs_test_123",
                    "session_url": "https://checkout.stripe.com/s/cs_test_123",
                },
                response_only=True,
            ),
            OpenApiExample(
                "Not expired",
                value={
                    "detail": "Your payment is not expired, no need to renew the payment session"
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
        tags=["Payments"],
    )
    @action(detail=True, methods=["post"], url_path="renew")
    def renew(self, request, pk=None):
        payment = self.get_object()
        if payment.status != Payment.Status.EXPIRED:
            return Response(
                {
                    "detail": "Your payment is not expired, no need to renew the payment session"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        session = renew_stripe_session(
            payment,
            success_url=get_success_url(request),
            cancel_url=get_cancel_url(request),
        )
        payment.status = Payment.Status.PENDING
        payment.session_id = session.id
        payment.session_url = session.url
        payment.save(update_fields=["status", "session_id", "session_url"])

        return Response(
            {
                "detail": "Session renewed",
                "session_id": session.id,
                "session_url": session.url,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Check payment success",
        description=(
            "Detail action. Retrieves the Stripe Checkout Session for this payment and, "
            "if `payment_status == 'paid'`, marks the payment as `PAID`. "
            "Accessible by the owner or staff."
        ),
        responses={
            200: inline_serializer(
                name="PaymentSuccessResponse",
                fields={"result": serializers.CharField()},
            ),
            400: inline_serializer(
                name="PaymentSuccessStripeError",
                fields={"error": serializers.CharField()},
            ),
            401: OpenApiResponse(description="Unauthorized"),
            404: OpenApiResponse(
                description="Not found (filtered by queryset/ownership)"
            ),
        },
        examples=[
            OpenApiExample(
                "Paid",
                value={
                    "result": "Session cs_test_123 was successfully paid. Thank you!"
                },
                response_only=True,
            ),
            OpenApiExample(
                "Not paid yet",
                value={"result": "Payment not completed yet"},
                response_only=True,
            ),
        ],
        tags=["Payments"],
    )
    @action(detail=True, methods=["get"], url_path="success")
    def success(self, request, pk=None):
        payment = self.get_object()
        try:
            session = stripe.checkout.Session.retrieve(payment.session_id)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        if session.payment_status == "paid":
            if payment.status != Payment.Status.PAID:
                payment.status = Payment.Status.PAID
                payment.save(update_fields=["status"])
            return Response(
                {"result": f"Session {session.id} was successfully paid. Thank you!"},
                status=status.HTTP_200_OK,
            )

        return Response(
            {"result": "Payment not completed yet"}, status=status.HTTP_200_OK
        )

    @extend_schema(
        summary="Payment canceled/info",
        description=(
            "Collection action. Informational endpoint called after user cancels from Stripe Checkout. "
            "Always returns a generic message; does not mutate state."
        ),
        responses={
            200: inline_serializer(
                name="PaymentCancelInfo",
                fields={"result": serializers.CharField()},
            ),
            401: OpenApiResponse(description="Unauthorized"),
        },
        tags=["Payments"],
    )
    @action(detail=False, methods=["get"], url_path="cancel")
    def cancel(self, request):
        return Response(
            {
                "result": "You can finish your payment later (Stripe session is available ~24h)."
            },
            status=status.HTTP_200_OK,
        )
