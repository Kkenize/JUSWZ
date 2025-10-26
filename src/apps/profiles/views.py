from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Profile, UserProfile
from .forms import ProfileEditForm, CustomPasswordChangeForm, AdminRoleForm, AdminUserSearchForm

# Create your views here.
def is_admin(user):
    """Check if user is an admin"""
    try:
        user_profile = user.userprofile
        return user_profile.is_admin
    except UserProfile.DoesNotExist:
        return False

@login_required
def profile_view(request, username):
    """
    Display a user's profile page.
    """
    
    # TEMPORARY FOR TESTING WITHOUT LOGIN
    # request.user = User.objects.get(username="KK")
    
    user = get_object_or_404(User, username=username)

    # No one may view someone else's profile
    if request.user != user:
        messages.error(request, 'You do not have permission to view this profile.')
        return redirect('profiles:profile', username=request.user.username)

    try:
        profile = user.profile
    except Profile.DoesNotExist:
        profile = Profile.objects.create(user=user)

    context = {
        'profile_user': user,
        'profile': profile,
        'is_own_profile': request.user == user,
        'is_admin': is_admin(request.user),  
    }
    return render(request, 'profiles/profile.html', context)

@login_required
def edit_profile(request):
    """
    Edit the current user's profile.
    """
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, request.FILES, user=request.user, instance=request.user.profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('profiles:profile', username=request.user.username)
    else:
        form = ProfileEditForm(user=request.user, instance=request.user.profile)
    
    context = {
        'form': form,
        'user': request.user,
    }
    return render(request, 'profiles/edit_profile.html', context)

@login_required
def change_password(request):
    """
    Change the current user's password.
    """
    if request.method == 'POST':
        form = CustomPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Important!
            messages.success(request, 'Your password was successfully updated!')
            return redirect('profiles:profile', username=request.user.username)
    else:
        form = CustomPasswordChangeForm(request.user)
    
    context = {
        'form': form,
        'user': request.user,
    }
    return render(request, 'profiles/change_password.html', context)

@login_required
def admin_user_search(request):
    """
    Admin interface for searching and managing users.
    """
    if not is_admin(request.user):
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('profiles:profile', username=request.user.username)
    
    form = AdminUserSearchForm(request.GET)
    users = User.objects.all().select_related('profile', 'userprofile')
    
    if form.is_valid():
        search_query = form.cleaned_data.get('search_query')
        role_filter = form.cleaned_data.get('role_filter')
        
        if search_query:
            users = users.filter(
                Q(username__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query)
            )
        
        if role_filter:
            users = users.filter(userprofile__role=role_filter)
    
    # Paginate results
    paginator = Paginator(users, 20)  # Show 20 users per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'form': form,
        'page_obj': page_obj,
        'users': page_obj,
    }
    return render(request, 'profiles/admin_user_search.html', context)

@login_required
def admin_profile_management(request, username):
    """
    Admin interface for managing a specific user's profile and role.
    """
    if not is_admin(request.user):
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('profiles:profile', username=request.user.username)
    
    target_user = get_object_or_404(User, username=username)
    
    # Get or create user profile and profile
    user_profile, created = UserProfile.objects.get_or_create(user=target_user)
    profile, created = Profile.objects.get_or_create(user=target_user)
    
    if request.method == 'POST':
        if 'edit_profile' in request.POST:
            # Handle profile editing
            form = ProfileEditForm(request.POST, request.FILES, user=target_user, instance=profile)
            if form.is_valid():
                form.save()
                messages.success(request, f'{target_user.username}\'s profile has been updated successfully!')
                return redirect('profiles:admin_profile_management', username=username)
        
        elif 'change_password' in request.POST:
            # Handle password change
            password_form = CustomPasswordChangeForm(target_user, request.POST)
            if password_form.is_valid():
                password_form.save()
                messages.success(request, f'{target_user.username}\'s password has been updated successfully!')
                return redirect('profiles:admin_profile_management', username=username)
        
        elif 'change_role' in request.POST:
            # Admin role protection
            if user_profile.is_admin:
                messages.error(request, 'You cannot modify the role of an admin user.')
                return redirect('profiles:admin_profile_management', username=username)

            role_form = AdminRoleForm(request.POST, instance=user_profile)
            if role_form.is_valid():
                role_form.save()
                messages.success(request, f'{target_user.username}\'s role has been updated successfully!')
                return redirect('profiles:admin_profile_management', username=username)

    else:
        form = ProfileEditForm(user=target_user, instance=profile)
        password_form = CustomPasswordChangeForm(target_user)
        role_form = AdminRoleForm(instance=user_profile)
    
    context = {
        'target_user': target_user,
        'profile': profile,
        'user_profile': user_profile,
        'form': form,
        'password_form': password_form,
        'role_form': role_form,
        'is_admin_view': True,
    }
    return render(request, 'profiles/admin_profile_management.html', context)
