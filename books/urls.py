from django.urls import include, path
from rest_framework import routers

from books.views import BookViewSet, PaymentViewSet, CreateCheckoutSessionView

router = routers.DefaultRouter()
router.register("books", BookViewSet)
router.register("payments", PaymentViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("create-checkout-session/", CreateCheckoutSessionView.as_view(), name="create-checkout-session"),
]

app_name = "books"
