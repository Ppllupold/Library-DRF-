from django.urls import include, path
from rest_framework import routers

from books.views import (
    BookViewSet,
    PaymentViewSet,
    PaymentSuccessView,
    PaymentCancelView,
)

router = routers.DefaultRouter()
router.register("books", BookViewSet)
router.register("payments", PaymentViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("payment-success/", PaymentSuccessView.as_view(), name="payment-success"),
    path("payment-cancel/", PaymentCancelView.as_view(), name="payment-cancel"),
]

app_name = "books"
