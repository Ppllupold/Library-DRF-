from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Book(models.Model):
    class CoverType(models.TextChoices):
        SOFT = "SOFT", "Soft"
        HARD = "HARD", "Hard"

    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255)
    cover = models.CharField(max_length=4, choices=CoverType.choices)
    inventory = models.PositiveIntegerField()
    daily_fee = models.DecimalField(
        max_digits=5, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )

    def __str__(self):
        return self.title


class Borrowing(models.Model):
    borrow_date = models.DateField(auto_now_add=True)
    expected_return_date = models.DateField()
    actual_return_date = models.DateField(null=True, blank=True)
    book = models.ForeignKey(Book, on_delete=models.PROTECT, related_name="borrowings")
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="borrowings")

    def __str__(self):
        return f"{self.user} borrowed {self.book.title} on {self.borrow_date}"


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PAID = "PAID", "Paid"

    class Type(models.TextChoices):
        PAYMENT = "PAYMENT", "Payment"
        FINE = "FINE", "Fine"

    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )

    type = models.CharField(max_length=10, choices=Type.choices)

    borrowing = models.ForeignKey(
        "Borrowing", on_delete=models.PROTECT, related_name="payments"
    )

    session_url = models.URLField()
    session_id = models.CharField(max_length=255)

    money_to_pay = models.DecimalField(
        max_digits=5, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )

    def __str__(self):
        return f"{self.get_type_display()} - {self.get_status_display()} - ${self.money_to_pay}"
