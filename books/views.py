from rest_framework import viewsets, mixins
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_extensions.mixins import DetailSerializerMixin

from books.models import Book, Payment
from books.serializers import (
    BookSerializer,
    PaymentDetailSerializer,
    PavementSerializer,
)
from books.stripe import create_checkout_session

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
    serializer_class = PavementSerializer

    # def get_queryset(self):
    #     if self.request.user.is_staff:
    #         return Payment.objects.all()
    #     return Payment.objects.filter(borrowing__user=self.request.user)

class CreateCheckoutSessionView(APIView):
    def post(self, request):
        session = create_checkout_session(
            amount=1000,
            success_url="https://yourdomain.com/success",
            cancel_url="https://yourdomain.com/cancel"
        )
        return Response({"sessionId": session.id, "sessionUrl": session.url})
