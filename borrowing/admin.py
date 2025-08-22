from django.contrib import admin

from books.models import Payment
from borrowing.models import Borrowing

# Register your models here.
admin.site.register(Borrowing)
admin.site.register(Payment)
