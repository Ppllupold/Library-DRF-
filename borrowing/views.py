from datetime import date

from django.shortcuts import get_object_or_404
from rest_framework import viewsets, mixins, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from borrowing.bot import send_telegram_message
from borrowing.serializers import BorrowingReadSerializer, BorrowingCreateSerializer
from borrowing.models import Borrowing


class BorrowingViewSet(
    viewsets.GenericViewSet,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
):
    permission_classes = (IsAuthenticated,)
    queryset = Borrowing.objects.select_related("book", "user")

    def get_queryset(self):
        user = self.request.user
        user_id = self.request.query_params.get("user_id")
        is_active = self.request.query_params.get("is_active")

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
        borrowing = serializer.save(user=self.request.user)
        message = (
            f"📚 New borrowing created!\n\n"
            f"👤 User: {borrowing.user.email}\n"
            f"📖 Book: {borrowing.book.title}\n"
            f"📅 Expected return: {borrowing.expected_return_date}"
        )
        send_telegram_message(message)


class ReturnBorrowingApiView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        borrowing = get_object_or_404(Borrowing, pk=pk)

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

        borrowing.actual_return_date = date.today()
        borrowing.book.inventory += 1
        borrowing.book.save()
        borrowing.save()

        return Response(
            {"detail": f"Book '{borrowing.book.title}' returned successfully."},
            status=status.HTTP_200_OK,
        )
