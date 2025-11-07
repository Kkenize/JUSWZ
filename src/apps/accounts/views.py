from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib.auth import login, get_user_model, logout
from django.urls import reverse
from django.views.decorators.cache import cache_control, never_cache

from rest_framework.views import APIView
from rest_framework.response import Response

import requests

from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import SocialLoginView


User = get_user_model()


class GoogleLogin(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter
    client_class = OAuth2Client
    callback_url = settings.GOOGLE_OAUTH_CALLBACK_URL


class GoogleLoginCallback(APIView):
    def get(self, request, *args, **kwargs):
        code = request.GET.get("code")
        if not code:
            return Response({"error": "Missing code"}, status=400)

        try:
            # Exchange code for access token
            token_url = "https://oauth2.googleapis.com/token"
            data = {
                "code": code,
                "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
                "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_OAUTH_CALLBACK_URL,
                "grant_type": "authorization_code"
            }
            token_response = requests.post(token_url, data=data).json()
            access_token = token_response.get("access_token")

            # Fetch user info from Google
            userinfo = requests.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            ).json()

            email = userinfo.get("email")
            name = userinfo.get("name")

            # Create or get local user
            user, created = User.objects.get_or_create(
                email=email,
                defaults={"username": email, "first_name": name}
            )

            # Log in user
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")

            # Redirect to dashboard home
            return redirect("dashboard:home")

        except Exception as e:
            import traceback
            return Response(
                {
                    "error": "Authentication failed",
                    "detail": str(e),
                    "trace": traceback.format_exc()
                },
                status=500
            )


# Prevents caching and allows a clean redirect to home after logout
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def logout_view(request):
    """Logs out user and clears browser cache for authenticated pages."""
    logout(request)
    return redirect('home')


# Landing page for non-logged-in users
def home_view(request):
    """Landing page with login button"""
    return render(request, "accounts/home.html")


# Login page (Google OAuth button)
def login_view(request):
    """Login page"""
    context = {
        "google_client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "google_callback_uri": settings.GOOGLE_OAUTH_CALLBACK_URL,
    }
    return render(request, "accounts/login.html", context)


# Learn More page
def learn_more_view(request):
    """Learn More page"""
    return render(request, "accounts/learn_more.html")
