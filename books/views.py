from django.urls import reverse
from rest_framework import viewsets, mixins
from rest_framework.response import Response
from rest_framework.views import APIView
import stripe
from rest_framework_extensions.mixins import DetailSerializerMixin

from books.models import Book, Payment
from books.serializers import (
    BookSerializer,
    PaymentDetailSerializer,
    PaymentSerializer,
)

WRITE_ACTIONS = ["create", "update", "partial_update", "destroy"]


class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.all()
    serializer_class = BookSerializer
    # authentication_classes = (JWTAuthentication,)
    #
    # def get_permissions(self):
    #     if self.action in WRITE_ACTIONS:
    #         permission_classes = [permissions.IsAdminUser]
    #     elif self.action == "retrieve":
    #         permission_classes = [permissions.IsAuthenticated]
    #     else:
    #         permission_classes = [permissions.AllowAny]
    #     return [permission() for permission in permission_classes]


class PaymentViewSet(
    DetailSerializerMixin,
    viewsets.GenericViewSet,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
):
    queryset = Payment.objects.all()
    serializer_detail_class = PaymentDetailSerializer
    serializer_class = PaymentSerializer

    # def get_queryset(self):
    #     if self.request.user.is_staff:
    #         return Payment.objects.all()
    #     return Payment.objects.filter(borrowing__user=self.request.user)


class PaymentSuccessView(APIView):
    def get(self, request):
        session = stripe.checkout.Session.retrieve(
            request.query_params.get("session_id")
        )
        if session.payment_status == "paid":
            payment = Payment.objects.get(session_id=session.id)
            payment.status = "PAID"
            payment.save()
        return Response(
            {
                "result": f"session number {session.id} was successfully paid. Thank you for using our service"
            }
        )


class PaymentCancelView(APIView):
    def get(self, request):
        return Response({"result": "You can finish your payment later during 24 hours"})
