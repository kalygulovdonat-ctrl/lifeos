from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.accounts import views

router = SimpleRouter()
router.register("categories", views.CategoryViewSet, basename="category")
router.register("tags", views.TagViewSet, basename="tag")

urlpatterns = [
    path("auth/register/", views.RegisterView.as_view(), name="auth-register"),
    path("auth/login/", views.LoginView.as_view(), name="auth-login"),
    path("auth/refresh/", views.RefreshView.as_view(), name="auth-refresh"),
    path("auth/logout/", views.LogoutView.as_view(), name="auth-logout"),
    path("auth/password/change/", views.PasswordChangeView.as_view(), name="auth-password-change"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("profile/onboarding/complete/", views.OnboardingCompleteView.as_view(), name="profile-onboarding"),
    *router.urls,
]
