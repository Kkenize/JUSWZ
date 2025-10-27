from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class UserProfile(models.Model):
    """Extended user profile with role management"""
    ROLE_CHOICES = [
        ('user', 'User'),
        ('admin', 'Admin'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='user')
    
    def __str__(self):
        return f'{self.user.username} - {self.role}'
    
    @property
    def is_admin(self):
        return self.role == 'admin'

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(max_length=500, blank=True)
    location = models.CharField(max_length=30, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    phone_number = models.CharField(max_length=15, blank=True)
    website = models.URLField(blank=True)
    
    # Academic information - up to 2 majors and 2 minors
    major_1 = models.CharField(max_length=100, blank=True, verbose_name="Primary Major")
    major_2 = models.CharField(max_length=100, blank=True, verbose_name="Secondary Major")
    minor_1 = models.CharField(max_length=100, blank=True, verbose_name="Primary Minor")
    minor_2 = models.CharField(max_length=100, blank=True, verbose_name="Secondary Minor")
    
    def __str__(self):
        return f'{self.user.username} Profile'
    
    @property
    def majors(self):
        """Return a list of non-empty majors"""
        return [major for major in [self.major_1, self.major_2] if major.strip()]
    
    @property
    def minors(self):
        """Return a list of non-empty minors"""
        return [minor for minor in [self.minor_1, self.minor_2] if minor.strip()]
