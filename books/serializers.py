from rest_framework import serializers

from books.models import Book, Payment


class BookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = ["id", "title", "author", "cover", "inventory", "daily_fee"]


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["id", "status", "type", "money_to_pay"]


class PaymentDetailSerializer(serializers.ModelSerializer):
    borrowing = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "id",
            "status",
            "type",
            "money_to_pay",
            "session_url",
            "session_id",
            "borrowing",
        ]

    def get_borrowing(self, obj):
        from borrowing.serializers import BorrowingReadSerializer

        return BorrowingReadSerializer(obj.borrowing).data
