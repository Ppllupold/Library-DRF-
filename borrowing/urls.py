from django.urls import include, path
from rest_framework import routers
from borrowing.views import BorrowingViewSet

router = routers.DefaultRouter()
router.register("borrowings", BorrowingViewSet, basename="borrowing")

urlpatterns = [
    path("", include(router.urls)),
]

app_name = "borrowings"
