from rest_framework import serializers

from books.serializers import BookSerializer
from borrowing.models import Borrowing


class BorrowingReadSerializer(serializers.ModelSerializer):
    book = BookSerializer(many=False, read_only=True)

    class Meta:
        model = Borrowing
        fields = ["id", "expected_return_date", "actual_return_date", "book", "user"]


class BorrowingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Borrowing
        fields = ["id", "expected_return_date", "book"]

    def create(self, validated_data):
        book = validated_data["book"]
        if book.inventory <= 0:
            raise serializers.ValidationError("Book is out of stock.")
        book.inventory -= 1
        book.save()
        return Borrowing.objects.create(**validated_data)
