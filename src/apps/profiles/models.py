from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class UserProfile(models.Model):
    """Extended user profile with role management"""
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('collaborator', 'Collaborator'),
        ('staff', 'Staff'),
        ('admin', 'Admin'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    
    def __str__(self):
        return f'{self.user.username} - {self.role}'
    
    @property
    def is_admin(self):
        return self.role == 'admin'
    
    @property
    def is_staff(self):
        return self.role == 'staff'
    
    @property
    def is_student(self):
        return self.role == 'student'
    
    @property
    def is_collaborator(self): 
        return self.role == 'collaborator'

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    
    # Mandatory fields
    school = models.CharField(max_length=100, default='Boston College')
    department = models.CharField(max_length=100, blank=True)
    
    # Optional fields
    bio = models.TextField(max_length=500, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    phone_number = models.CharField(max_length=15, blank=True)
    website = models.URLField(blank=True)
    location = models.CharField(max_length=30, blank=True)
    
    # Academic information - up to 2 majors and 2 minors (for students)
    major_1 = models.CharField(max_length=100, blank=True, verbose_name="Primary Major")
    major_2 = models.CharField(max_length=100, blank=True, verbose_name="Secondary Major")
    minor_1 = models.CharField(max_length=100, blank=True, verbose_name="Primary Minor")
    minor_2 = models.CharField(max_length=100, blank=True, verbose_name="Secondary Minor")
    
    # Graduation year (for students)
    graduation_year = models.IntegerField(null=True, blank=True)
    
    def __str__(self):
        return f'{self.user.username} Profile'
    
    @property
    def majors(self):
        """Return a list of non-empty majors, or ['Undeclared'] if none"""
        majors_list = [major for major in [self.major_1, self.major_2] if major.strip()]
        return majors_list if majors_list else ['Undeclared']
    
    @property
    def minors(self):
        """Return a list of non-empty minors"""
        return [minor for minor in [self.minor_1, self.minor_2] if minor.strip()]
