from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from user.views import UserRegisterView, ManageUserView

urlpatterns = [
    path("users/", UserRegisterView.as_view(), name="register"),
    path("users/me/", ManageUserView.as_view(), name="manage-me"),
    path("users/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("users/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]

app_name = "users"
