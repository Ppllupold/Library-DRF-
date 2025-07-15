from django.urls import include, path
from rest_framework import routers
from borrowing.views import BorrowingViewSet, ReturnBorrowingApiView

router = routers.DefaultRouter()
router.register("borrowings", BorrowingViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("borrowings/<int:pk>/return", ReturnBorrowingApiView.as_view())
]

app_name = "borrowings"
