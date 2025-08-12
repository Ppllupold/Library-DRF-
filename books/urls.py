from django.urls import include, path
from rest_framework import routers

from books.views import (
    BookViewSet,
    PaymentViewSet,
)

router = routers.DefaultRouter()
router.register("books", BookViewSet)
router.register("payments", PaymentViewSet, basename="payment")

urlpatterns = [
    path("", include(router.urls)),
]

app_name = "books"
