from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Borrowing(models.Model):
    borrow_date = models.DateField(auto_now_add=True)
    expected_return_date = models.DateField()
    actual_return_date = models.DateField(null=True, blank=True)

    book = models.ForeignKey(
        "books.Book", on_delete=models.PROTECT, related_name="borrowings"
    )
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="borrowings")

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(expected_return_date__gte=models.F("borrow_date")),
                name="expected_after_borrow",
            ),
            models.CheckConstraint(
                check=models.Q(actual_return_date__gte=models.F("borrow_date")),
                name="actual_after_borrow",
            ),
        ]

    def __str__(self):
        return f"{self.user} borrowed {self.book.title} on {self.borrow_date}"
