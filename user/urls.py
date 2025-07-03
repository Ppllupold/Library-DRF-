from django.urls import path

from user.views import UserRegisterView, ManageUserView

urlpatterns = [
    path("users/", UserRegisterView.as_view()),
    path("users/me/", ManageUserView.as_view()),
]
