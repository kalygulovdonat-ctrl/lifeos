"""HTTP layer for auth, profile and reference data. No business logic here (SDD §6.1)."""

from __future__ import annotations

from typing import Any

from django.contrib.auth import authenticate
from django.db.models import QuerySet
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts import selectors, services
from apps.accounts.auth import (
    clear_refresh_cookie,
    enforce_csrf,
    ensure_csrf_cookie,
    issue_tokens,
    read_refresh_cookie,
    set_refresh_cookie,
)
from apps.accounts.models import Category, Tag, User
from apps.accounts.serializers import (
    AccessResponseSerializer,
    AuthResponseSerializer,
    CategorySerializer,
    LoginSerializer,
    PasswordChangeSerializer,
    ProfileSerializer,
    RegisterSerializer,
    TagSerializer,
)
from common.audit import audit
from common.exceptions import LifeOSError
from common.idempotency import idempotent
from common.views import OwnedModelViewSet


class InvalidCredentials(LifeOSError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "INVALID_CREDENTIALS"
    message = "Email or password is incorrect."


class RefreshInvalid(LifeOSError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "REFRESH_INVALID"
    message = "Session has expired. Please sign in again."


def _auth_response(request: Request, user: User, status_code: int = 200) -> Response:
    access, refresh = issue_tokens(user)
    profile = selectors.profile_get(user)
    response = Response({"access": access, "profile": ProfileSerializer(profile).data}, status=status_code)
    set_refresh_cookie(response, refresh)
    ensure_csrf_cookie(request)
    return response


class AuthBaseView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_scope = "auth"


class RegisterView(AuthBaseView):
    @extend_schema(request=RegisterSerializer, responses={201: AuthResponseSerializer})
    def post(self, request: Request) -> Response:
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.user_register(**serializer.validated_data)
        return _auth_response(request, user, status.HTTP_201_CREATED)


class LoginView(AuthBaseView):
    @extend_schema(request=LoginSerializer, responses={200: AuthResponseSerializer})
    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request._request,
            username=serializer.validated_data["email"].lower(),
            password=serializer.validated_data["password"],
        )
        if user is None or not user.is_active:
            raise InvalidCredentials()
        audit(user=user, entity_type="user", entity_id=user.id, action="LOGIN")
        return _auth_response(request, user)


class RefreshView(AuthBaseView):
    """Reads the refresh token from the HttpOnly cookie, rotates it, returns a new access token."""

    @extend_schema(request=None, responses={200: AccessResponseSerializer})
    def post(self, request: Request) -> Response:
        raw = read_refresh_cookie(request)
        if not raw:  # no session at all: a plain 401, nothing to protect with CSRF
            raise RefreshInvalid()
        enforce_csrf(request)
        serializer = TokenRefreshSerializer(data={"refresh": raw})
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as exc:  # expired/blacklisted/malformed token, deleted or inactive user
            raise RefreshInvalid() from exc
        data = serializer.validated_data
        response = Response({"access": data["access"]})
        if "refresh" in data:
            set_refresh_cookie(response, data["refresh"])
        ensure_csrf_cookie(request)
        return response


class LogoutView(AuthBaseView):
    @extend_schema(request=None, responses={204: OpenApiResponse(description="Logged out")})
    def post(self, request: Request) -> Response:
        enforce_csrf(request)
        raw = read_refresh_cookie(request)
        if raw:
            try:
                RefreshToken(raw).blacklist()
            except TokenError:
                pass
        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_refresh_cookie(response)
        return response


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=PasswordChangeSerializer, responses={200: AccessResponseSerializer})
    def post(self, request: Request) -> Response:
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.password_change(user=request.user, **serializer.validated_data)
        # All sessions were revoked; issue a fresh pair for the current device.
        access, refresh = issue_tokens(request.user)
        response = Response({"access": access})
        set_refresh_cookie(response, refresh)
        return response


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: ProfileSerializer})
    def get(self, request: Request) -> Response:
        return Response(ProfileSerializer(selectors.profile_get(request.user)).data)

    @extend_schema(request=ProfileSerializer, responses={200: ProfileSerializer})
    def patch(self, request: Request) -> Response:
        profile = selectors.profile_get(request.user)
        serializer = ProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        profile = services.profile_update(user=request.user, data=dict(serializer.validated_data))
        return Response(ProfileSerializer(profile).data)


class OnboardingCompleteView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: ProfileSerializer})
    def post(self, request: Request) -> Response:
        return Response(ProfileSerializer(services.onboarding_complete(user=request.user)).data)


class CategoryViewSet(OwnedModelViewSet):
    serializer_class = CategorySerializer
    queryset = Category.objects.none()
    filterset_fields = ["scope", "is_archived"]
    ordering_fields = ["sort_order", "name", "created_at"]

    def selector(self, user: Any) -> QuerySet[Category]:
        include_archived = self.request.query_params.get("include_archived") == "true"
        if self.action != "list":
            include_archived = True
        return selectors.category_list(user, include_archived=include_archived)

    @idempotent
    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = services.category_create(user=request.user, **serializer.validated_data)
        return Response(self.get_serializer(category).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        category = self.get_object()
        serializer = self.get_serializer(category, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        category = services.category_update(
            user=request.user, category=category, data=dict(serializer.validated_data)
        )
        return Response(self.get_serializer(category).data)

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        services.category_archive(user=request.user, category=self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)


class TagViewSet(OwnedModelViewSet):
    serializer_class = TagSerializer
    queryset = Tag.objects.none()
    ordering_fields = ["name", "created_at"]

    def selector(self, user: Any) -> QuerySet[Tag]:
        return selectors.tag_list(user)

    @idempotent
    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tag = services.tag_create(user=request.user, **serializer.validated_data)
        return Response(self.get_serializer(tag).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        tag = self.get_object()
        serializer = self.get_serializer(tag, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        tag = services.tag_update(user=request.user, tag=tag, data=dict(serializer.validated_data))
        return Response(self.get_serializer(tag).data)

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        services.tag_delete(user=request.user, tag=self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)
