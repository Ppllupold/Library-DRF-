from rest_framework import serializers

from books.models import Book
from borrowing.models import Borrowing
from user.serializers import UserSerializer


class BookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = ["id", "title", "author", "cover", "inventory", "daily_fee"]


class BorrowingSerializer(serializers.ModelSerializer):
    book = BookSerializer(many=False)
    user = UserSerializer(many=False, read_only=True)

    class Meta:
        model = Borrowing
        fields = ["id", "expected_return_date", "actual_return_date", "book", "user"]

    def create(self, validated_data):
        book = validated_data["book"]
        if book.inventory <= 0:
            raise serializers.ValidationError("Book is out of stock.")
        book.inventory -= 1
        book.save()
        return Borrowing.objects.create(**validated_data)
