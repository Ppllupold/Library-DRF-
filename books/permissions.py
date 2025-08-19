from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdminOrOwnerReadOnlyRenewOnly(BasePermission):
    def has_permission(self, request, view):
        if request.user and request.user.is_staff:
            return True
        if request.method in SAFE_METHODS:
            return True
        return request.method == "POST" and getattr(view, "action", None) == "renew"

    def has_object_permission(self, request, view, obj):
        if request.user and request.user.is_staff:
            return True
        is_owner = (
            getattr(obj, "borrowing", None) and obj.borrowing.user_id == request.user.id
        )
        if request.method in SAFE_METHODS:
            return is_owner
        return (
            request.method == "POST"
            and getattr(view, "action", None) == "renew"
            and is_owner
        )
