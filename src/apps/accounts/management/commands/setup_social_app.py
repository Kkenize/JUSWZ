"""
Management command to set up Google Social Application from environment variables.
Run this after pulling code to ensure OAuth is configured.

Usage: python manage.py setup_social_app
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from allauth.socialaccount.models import SocialApp
from allauth.socialaccount.providers.google.provider import GoogleProvider
from django.contrib.sites.models import Site


class Command(BaseCommand):
    help = 'Creates or updates Google Social Application from environment variables'

    def handle(self, *args, **options):
        # Get credentials from settings
        client_id = settings.GOOGLE_OAUTH_CLIENT_ID
        client_secret = settings.GOOGLE_OAUTH_CLIENT_SECRET
        
        if not client_id or not client_secret:
            self.stdout.write(
                self.style.ERROR(
                    '❌ GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET must be set in .env file'
                )
            )
            return
        
        # Get or create the site
        site, _ = Site.objects.get_or_create(
            id=settings.SITE_ID,
            defaults={'domain': 'localhost:8000', 'name': 'JUSWZ'}
        )
        
        # Get or create the SocialApp
        social_app, created = SocialApp.objects.get_or_create(
            provider=GoogleProvider.id,
            defaults={
                'name': 'Google OAuth',
                'client_id': client_id,
                'secret': client_secret,
            }
        )
        
        # Update if it existed but credentials changed
        if not created:
            social_app.client_id = client_id
            social_app.secret = client_secret
            social_app.save()
            self.stdout.write(
                self.style.WARNING('⚠️  Updated existing Google Social App with new credentials')
            )
        
        # Ensure the site is linked
        if site not in social_app.sites.all():
            social_app.sites.add(site)
            self.stdout.write(
                self.style.SUCCESS('✓ Linked Google Social App to site')
            )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS('✓ Created Google Social App successfully')
            )
            self.stdout.write(
                self.style.SUCCESS('✓ Google OAuth is now configured!')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('✓ Google Social App already exists and is up to date')
            )
