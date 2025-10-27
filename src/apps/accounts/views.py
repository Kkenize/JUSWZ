from django.shortcuts import render, redirect
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import SocialLoginView
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import login
from django.urls import reverse


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
            # Initialize GoogleLogin with proper attributes
            google_login = GoogleLogin()
            google_login.request = request
            google_login.format_kwarg = None
            
            # Prepare the access token request
            data = {
                'code': code,
                'callback_url': settings.GOOGLE_OAUTH_CALLBACK_URL
            }
            
            # Process the login directly
            serializer = google_login.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            
            # Get the user from the serializer
            user = serializer.validated_data['user']
            
            # Create token using Django REST framework's Token model
            from rest_framework.authtoken.models import Token
            token, _ = Token.objects.get_or_create(user=user)
            
            # Set session auth for the user
            login(request, user)
            
            # Redirect to dashboard
            return redirect('dashboard:home')
            
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

def home_view(request):
    """Landing page with login button"""
    return render(request, 'accounts/home.html')

def login_view(request):
    """Login page"""
    context = {
        "google_client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "google_callback_uri": settings.GOOGLE_OAUTH_CALLBACK_URL,
    }
    return render(request, 'accounts/login.html', context)
