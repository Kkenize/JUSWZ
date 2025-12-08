from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.dashboard.models import Certificate, Training
from apps.profiles.models import UserProfile


class Command(BaseCommand):
    help = "Seed sample issued certificates: team member issuing to students."

    def handle(self, *args, **options):
        self.stdout.write("Seeding issued certificates...")

        staff_user = self._ensure_user(
            username="team_member",
            first_name="Taylor",
            last_name="Member",
            role="staff",
            email="team_member@example.com",
        )
        student_one = self._ensure_user(
            username="student_alex",
            first_name="Alex",
            last_name="Rivera",
            role="student",
            email="alex.rivera@example.com",
        )
        student_two = self._ensure_user(
            username="student_brianna",
            first_name="Brianna",
            last_name="Tang",
            role="student",
            email="brianna.tang@example.com",
        )
        student_three = self._ensure_user(
            username="student_casey",
            first_name="Casey",
            last_name="Lee",
            role="student",
            email="casey.lee@example.com",
        )
        student_four = self._ensure_user(
            username="student_jordan",
            first_name="Jordan",
            last_name="Park",
            role="student",
            email="jordan.park@example.com",
        )
        student_five = self._ensure_user(
            username="student_morgan",
            first_name="Morgan",
            last_name="Smith",
            role="student",
            email="morgan.smith@example.com",
        )
        student_six = self._ensure_user(
            username="student_avery",
            first_name="Avery",
            last_name="Chen",
            role="student",
            email="avery.chen@example.com",
        )

        trainings = [
            {
                "title": "Lvl 1 – Sewing Machine Basics Training",
                "days_ago": 14,
                "start": time(10, 0),
                "end": time(11, 30),
                "learners": [student_one],
            },
            {
                "title": "Lvl 1 – Intro to 3D Printing Training",
                "days_ago": 10,
                "start": time(14, 0),
                "end": time(15, 30),
                "learners": [student_two],
            },
            {
                "title": "Lvl 2 – High-Detail Resin 3D Printing Training",
                "days_ago": 7,
                "start": time(9, 0),
                "end": time(11, 0),
                "learners": [student_one, student_two],
            },
            {
                "title": "Lvl 1 – Laser Cutter Training",
                "days_ago": 4,
                "start": time(13, 0),
                "end": time(14, 30),
                "learners": [student_one, student_three],
            },
            {
                "title": "Lvl 1 – Vinyl Cutter Training",
                "days_ago": 2,
                "start": time(16, 0),
                "end": time(17, 0),
                "learners": [student_two, student_four],
            },
            {
                "title": "Lvl 1 – Electronics Soldering Training",
                "days_ago": 9,
                "start": time(11, 0),
                "end": time(12, 30),
                "learners": [student_three, student_four],
            },
            {
                "title": "Lvl 1 – Woodworking Basics Training",
                "days_ago": 6,
                "start": time(15, 0),
                "end": time(16, 30),
                "learners": [student_one, student_three],
            },
            {
                "title": "Lvl 2 – Multi-Material 3D Printing Training",
                "days_ago": 3,
                "start": time(10, 30),
                "end": time(12, 0),
                "learners": [student_two, student_four],
            },
            {
                "title": "Lvl 1 – Metalworking CAM Training",
                "days_ago": 12,
                "start": time(9, 30),
                "end": time(11, 0),
                "learners": [student_five, student_six],
            },
            {
                "title": "Lvl 2 – Advanced Laser Training",
                "days_ago": 8,
                "start": time(13, 30),
                "end": time(15, 0),
                "learners": [student_three, student_five],
            },
            {
                "title": "Lvl 1 – Screen Printing Training",
                "days_ago": 1,
                "start": time(10, 0),
                "end": time(11, 30),
                "learners": [student_six, student_one],
            },
        ]

        created_count = 0
        for cfg in trainings:
            training_date = timezone.localdate() - timedelta(days=cfg["days_ago"])
            training, _ = Training.objects.get_or_create(
                title=cfg["title"],
                date=training_date,
                start_time=cfg["start"],
                end_time=cfg["end"],
                defaults={
                    "capacity": 8,
                    "instructor": staff_user,
                },
            )
            training.participants.add(*cfg["learners"])

            for learner in cfg["learners"]:
                cert, created = Certificate.objects.get_or_create(
                    user=learner,
                    training=training,
                    defaults={
                        "issued_on": training_date,
                        "expires_on": training_date + timedelta(days=365 * 3),
                        "status": "sent",
                        "issued_by": staff_user,
                        "notes": "Seeded for UI testing.",
                    },
                )
                if created:
                    created_count += 1

        self.stdout.write(self.style.SUCCESS(f"Seed complete. Certificates created: {created_count}"))

    def _ensure_user(self, username, first_name, last_name, role, email):
        user, _ = User.objects.get_or_create(
            username=username,
            defaults={"first_name": first_name, "last_name": last_name, "email": email},
        )
        if not user.password:
            user.set_password("password123")
            user.save(update_fields=["password"])

        profile, _ = UserProfile.objects.get_or_create(user=user, defaults={"role": role})
        if profile.role != role:
            profile.role = role
            profile.save(update_fields=["role"])
        return user
