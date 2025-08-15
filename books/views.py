import stripe
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_extensions.mixins import DetailSerializerMixin
from rest_framework_simplejwt.authentication import JWTAuthentication

from books.models import Book, Payment
from books.serializers import (
    BookSerializer,
    PaymentDetailSerializer,
    PaymentSerializer,
)
from books.stripe import renew_stripe_session, get_success_url, get_cancel_url

WRITE_ACTIONS = ["create", "update", "partial_update", "destroy"]


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


class PaymentViewSet(DetailSerializerMixin, viewsets.ModelViewSet):
    queryset = Payment.objects.select_related("borrowing", "borrowing__user")
    serializer_class = PaymentSerializer
    serializer_detail_class = PaymentDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return self.queryset
        return self.queryset.filter(borrowing__user=user)

    @action(detail=True, methods=["post"], url_path="renew")
    def renew(self, request, pk=None):
        payment = self.get_object()

        if payment.status != Payment.Status.EXPIRED:
            return Response(
                {
                    "result": "Your payment is not expired, no need to renew the payment session"
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

    @action(detail=False, methods=["get"], url_path="success")
    def success(self, request):
        session_id = request.query_params.get("session_id")
        if not session_id:
            return Response(
                {"error": "Missing session_id"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            session = stripe.checkout.Session.retrieve(session_id)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        if session.payment_status == "paid":
            payment = get_object_or_404(Payment, session_id=session.id)

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

    @action(detail=False, methods=["get"], url_path="cancel")
    def cancel(self, request):
        return Response(
            {
                "result": "You can finish your payment later (Stripe session is available ~24h)."
            },
            status=status.HTTP_200_OK,
        )
