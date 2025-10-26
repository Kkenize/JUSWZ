# Profiles App

Comprehensive user profile management system

## Overview

The profiles app provides a complete user profile management system with viewing, editing, and password change functionality.

## Features

### Profile Management
- Profile Viewing: Display detailed user profiles with all personal information
- Profile Editing: Complete form-based profile editing with validation
- Password Changes: Secure password change functionality
- Avatar Upload: Support for profile picture uploads
- Automatic Profile Creation: Profiles are automatically created when users are created

### Admin Management
- User Search: Search and filter users by name, email, or username
- Role Management: Promote users to admin or demote admins to user status
- Profile Administration: Edit any user's profile information
- Password Administration: Change passwords for any user
- User Overview: View complete user statistics and information

## Models

### Profile Model
Fields:
- user: One-to-one relationship with Django's User model
- bio: User's biography/description (max 500 characters)
- location: User's location (max 30 characters)
- birth_date: User's birth date (optional)
- avatar: Profile picture upload (stored in 'avatars/' directory)
- phone_number: Contact phone number (max 15 characters)
- website: Personal website URL (optional)

### UserProfile Model
Fields:
- user: One-to-one relationship with Django's User model
- role: User role (user or admin)

## Views

### Profile View (`profile_view`)
- URL: `/profiles/profile/<username>/`
- Purpose: Display a user's profile page
- Features: 
  - Shows all profile information in organized sections
  - Differentiates between viewing own profile vs others
  - Automatically creates profile if it doesn't exist
  - Login required

### Edit Profile (`edit_profile`)
- URL: `/profiles/edit/`
- Purpose: Edit the current user's profile
- Features:
  - Form-based editing of all profile fields
  - File upload support for avatar images
  - Success messages and redirects
  - Login required

### Change Password (`change_password`)
- URL: `/profiles/change-password/`
- Purpose: Change the current user's password
- Features:
  - Secure password change with current password verification
  - Session management (maintains login after password change)
  - Form validation and error handling
  - Login required

### Admin User Search (`admin_user_search`)
- URL: `/profiles/admin/users/`
- Purpose: Search and manage all users
- Features:
  - Search users by username, email, or name
  - Filter users by role
  - Paginated results display
  - Admin access only

### Admin Profile Management (`admin_profile_management`)
- URL: `/profiles/admin/profile/<username>/`
- Purpose: Manage any user's profile and role
- Features:
  - Edit any user's profile information
  - Change any user's password
  - Modify user roles
  - View complete user information
  - Admin access only

## Templates

### Profile Template (`profile.html`)
- Location: `/src/templates/profiles/profile.html`

### Edit Profile Template (`edit_profile.html`)
- Location: `/src/templates/profiles/edit_profile.html`

### Change Password Template (`change_password.html`)
- Location: `/src/templates/profiles/change_password.html`

### Admin User Search Template (`admin_user_search.html`)
- Location: `/src/templates/profiles/admin_user_search.html`

### Admin Profile Management Template (`admin_profile_management.html`)
- Location: `/src/templates/profiles/admin_profile_management.html`

## Forms

### ProfileEditForm
- Purpose: Handle profile editing with user field integration
- Features:
  - Includes user fields (first_name, last_name, email)
  - Profile-specific fields (bio, location, avatar, etc.)
  - File upload support
  - Form validation and error handling

### CustomPasswordChangeForm
- Purpose: Enhanced password change form
- Features:
  - Better styling integration
  - Form validation
  - Error handling

### AdminRoleForm
- Purpose: Handle user role changes
- Features:
  - Role selection dropdown
  - Form validation
  - Admin access only

### AdminUserSearchForm
- Purpose: Search and filter users
- Features:
  - Text search field
  - Role filter dropdown
  - Form validation

## Admin Interface

The Profile and UserProfile models are registered with Django admin for easy management:
- Profile list display: user, location, phone_number, website
- UserProfile list display: user, role
- Search functionality: username, email, location
- Filter options: location, role
- Raw ID fields for user selection

### Custom Admin Interface
- User search and management outside Django admin
- Role management interface
- Profile administration tools
- Password management for any user

## Signals

### Automatic Profile Creation
```python
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, kwargs):
    if created:
        Profile.objects.create(user=instance)
```

Profiles are automatically created when new users are created, ensuring every user has a profile.

## Design System

### Color Scheme
- Background: `#FFFFFF` (White)
- Text: `#1C1C1C` (Dark Grey)
- Accents: `#D4AF37` (Gold)

### Design Features
- Responsive Layout: Works on all screen sizes
- Card-Based Design: Clean containers with subtle shadows
- Visual Hierarchy: Clear section organization and typography
- Interactive Elements: Hover effects and smooth transitions
- Professional Styling: Modern, clean aesthetic

## Installation & Setup

### Prerequisites
- Django 5.2.7+
- Pillow (for image field support)

### Database Setup
```bash
# Create migrations
python manage.py makemigrations profiles

# Apply migrations
python manage.py migrate
```

### Dependencies
- Pillow: `pip install Pillow`

## Usage Examples

### Accessing a Profile
# In views
from apps.profiles.models import Profile

# Get user's profile
profile = user.profile

# Access profile fields
bio = profile.bio
location = profile.location
avatar = profile.avatar

### URL Patterns
- Profile URLs:
    - /profiles/profile/admin/          # View admin's profile
    - /profiles/edit/                   # Edit current user's profile
    - /profiles/change-password/        # Change current user's password
- Admin URLs:
    - /profiles/admin/users/            # Search and manage users
    - /profiles/admin/profile/<username>/ # Manage specific user

## Future Enhancements

Potential areas for future development:
- Profile privacy settings
- Social media integration
- Profile search functionality
- Advanced avatar editing
- Profile activity tracking
- Integration with other app features