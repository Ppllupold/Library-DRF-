from rest_framework import viewsets, permissions
from rest_framework_simplejwt.authentication import JWTAuthentication

from books.models import Book
from books.serializers import BookSerializer

WRITE_ACTIONS = ["create", "update", "partial_update", "destroy"]

class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.all()
    serializer_class = BookSerializer
    authentication_classes = (JWTAuthentication,)

    def get_permissions(self):
        if self.action in WRITE_ACTIONS:
            permission_classes = [permissions.IsAdminUser]
        elif self.action == "retrieve":
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.AllowAny]
        return [permission() for permission in permission_classes]
