from django.urls import path, re_path, include
from . import views
from .views import GoogleLogin, GoogleLoginCallback, logout_view

urlpatterns = [
    path('', views.home_view, name='home'),
    path('home/', views.home_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('learn-more/', views.learn_more_view, name='learn_more'),
    
    path('logout/', logout_view, name='logout'),

    path("api/v1/auth/", include("dj_rest_auth.urls")),
    re_path(r"^api/v1/auth/accounts/", include("allauth.urls")),
    path("api/v1/auth/registration/", include("dj_rest_auth.registration.urls")),
    path("api/v1/auth/google/", GoogleLogin.as_view(), name="google_login"),
    path("api/v1/auth/google/callback/", GoogleLoginCallback.as_view(), name="google_callback"),
]
