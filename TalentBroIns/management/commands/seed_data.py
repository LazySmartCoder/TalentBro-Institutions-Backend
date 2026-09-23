import json

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from TalentBroIns.models import ClientProfile, Institution


INSTITUTIONS = [
    {
        "name": "Christ University",
        "user_username": "christ.admin@christuniversity.edu.in",
        "user_first_name": "Christ University Admin",
        "institution_type": "Deemed University",
        "website": "https://christuniversity.edu.in",
        "email_domain": "christuniversity.edu.in",
        "address": "Hosur Road, Lalbagh, Bengaluru, Karnataka",
        "city": "Bengaluru",
        "state": "Karnataka",
        "pin_code": "560029",
        "placement_department_name": "Centre for Placement & Training",
        "placement_office_email": "placement@christuniversity.edu.in",
        "approximate_student_strength": 14000,
        "courses_offered": ["B.Tech", "BCA", "BBA", "B.Com", "BA", "M.Tech", "MCA", "MBA", "M.Com", "MA"],
        "departments": '["computer department", "engineering department"]',
    },
    {
        "name": "Presidency University",
        "user_username": "presidency.admin@presidencyuniversity.in",
        "user_first_name": "Presidency University Admin",
        "institution_type": "University",
        "website": "https://presidencyuniversity.in",
        "email_domain": "presidencyuniversity.in",
        "address": "Sadashivanagar, Bengaluru, Karnataka",
        "city": "Bengaluru",
        "state": "Karnataka",
        "pin_code": "560080",
        "placement_department_name": "Training & Placement Cell",
        "placement_office_email": "placement@presidencyuniversity.in",
        "approximate_student_strength": 8000,
        "courses_offered": ["B.Tech", "BCA", "BBA", "B.Com", "M.Tech", "MCA", "MBA"],
        "departments": '["computer department", "engineering department"]',
    },
    {
        "name": "Jain University",
        "user_username": "jain.admin@jainuniversity.ac.in",
        "user_first_name": "Jain University Admin",
        "institution_type": "Deemed University",
        "website": "https://jainuniversity.ac.in",
        "email_domain": "jainuniversity.ac.in",
        "address": "Jnanashakti Campus, Tumakuru Road, Bengaluru, Karnataka",
        "city": "Bengaluru",
        "state": "Karnataka",
        "pin_code": "560062",
        "placement_department_name": "Centre for Industry-Academia Partnerships",
        "placement_office_email": "placement@jainuniversity.ac.in",
        "approximate_student_strength": 12000,
        "courses_offered": ["B.Tech", "BCA", "BBA", "B.Com", "B.Sc.", "M.Tech", "MCA", "MBA", "M.Sc."],
        "departments": '["computer department", "engineering department"]',
    },
]

CLIENT_PROFILES = [
    # 6 from Christ University
    {"full_name": "Dr. Arun Sharma", "official_email": "arun.sharma@christuniversity.edu.in", "mobile_number": "9876543210", "designation": "Placement Officer", "employee_staff_id": "CHR-PL-001", "institution_name": "Christ University", "access": "master"},
    {"full_name": "Priya Menon", "official_email": "priya.menon@christuniversity.edu.in", "mobile_number": "9876543211", "designation": "Assistant Placement Coordinator", "employee_staff_id": "CHR-PL-002", "institution_name": "Christ University", "access": "beta"},
    {"full_name": "Rajesh Kumar", "official_email": "rajesh.kumar@christuniversity.edu.in", "mobile_number": "9876543212", "designation": "Training Head", "employee_staff_id": "CHR-TR-001", "institution_name": "Christ University", "access": "beta"},
    {"full_name": "Sneha Iyer", "official_email": "sneha.iyer@christuniversity.edu.in", "mobile_number": "9876543213", "designation": "Student Relations Manager", "employee_staff_id": "CHR-SR-001", "institution_name": "Christ University", "access": "beta"},
    {"full_name": "Vikram Patel", "official_email": "vikram.patel@christuniversity.edu.in", "mobile_number": "9876543214", "designation": "Corporate Liaison", "employee_staff_id": "CHR-CL-001", "institution_name": "Christ University", "access": "beta"},
    {"full_name": "Deepa Nair", "official_email": "deepa.nair@christuniversity.edu.in", "mobile_number": "9876543215", "designation": "Placement Analyst", "employee_staff_id": "CHR-PA-001", "institution_name": "Christ University", "access": "beta"},
    # 2 from Presidency University
    {"full_name": "Mohammed Ali", "official_email": "mohammed.ali@presidencyuniversity.in", "mobile_number": "9876543216", "designation": "Placement Director", "employee_staff_id": "PRES-PD-001", "institution_name": "Presidency University", "access": "master"},
    {"full_name": "Kavitha Reddy", "official_email": "kavitha.reddy@presidencyuniversity.in", "mobile_number": "9876543217", "designation": "Training Coordinator", "employee_staff_id": "PRES-TC-001", "institution_name": "Presidency University", "access": "beta"},
    # 2 from Jain University
    {"full_name": "Suresh Babu", "official_email": "suresh.babu@jainuniversity.ac.in", "mobile_number": "9876543218", "designation": "Head of Placements", "employee_staff_id": "JAIN-HOP-001", "institution_name": "Jain University", "access": "master"},
    {"full_name": "Lakshmi Devi", "official_email": "lakshmi.devi@jainuniversity.ac.in", "mobile_number": "9876543219", "designation": "Industry Relations Manager", "employee_staff_id": "JAIN-IRM-001", "institution_name": "Jain University", "access": "beta"},
]


class Command(BaseCommand):
    help = "Seed the database with 3 Bengaluru institutions and 10 client profiles"

    def handle(self, *args, **options):
        institutions = {}
        for inst_data in INSTITUTIONS:
            user, created = User.objects.get_or_create(
                username=inst_data["user_username"],
                defaults={
                    "email": inst_data["user_username"],
                    "first_name": inst_data["user_first_name"],
                    "last_name": "",
                },
            )
            if created:
                user.set_unusable_password()
                user.save()

            inst, inst_created = Institution.objects.get_or_create(
                user=user,
                defaults={
                    "name": inst_data["name"],
                    "institution_type": inst_data["institution_type"],
                    "website": inst_data["website"],
                    "email_domain": inst_data["email_domain"],
                    "address": inst_data["address"],
                    "city": inst_data["city"],
                    "state": inst_data["state"],
                    "pin_code": inst_data["pin_code"],
                    "placement_department_name": inst_data["placement_department_name"],
                    "placement_office_email": inst_data["placement_office_email"],
                    "approximate_student_strength": inst_data["approximate_student_strength"],
                    "courses_offered": inst_data["courses_offered"],
                    "departments": inst_data["departments"],
                },
            )
            institutions[inst_data["name"]] = inst
            status = "created" if inst_created else "already exists"
            self.stdout.write(self.style.SUCCESS(f"Institution: {inst.name} ({status})"))

        for profile_data in CLIENT_PROFILES:
            inst = institutions[profile_data["institution_name"]]
            user, created = User.objects.get_or_create(
                username=profile_data["official_email"],
                defaults={
                    "email": profile_data["official_email"],
                    "first_name": profile_data["full_name"],
                    "last_name": "",
                },
            )
            if created:
                user.set_unusable_password()
                user.save()

            profile, profile_created = ClientProfile.objects.get_or_create(
                user=user,
                defaults={
                    "institution": inst,
                    "full_name": profile_data["full_name"],
                    "official_email": profile_data["official_email"],
                    "mobile_number": profile_data["mobile_number"],
                    "designation": profile_data["designation"],
                    "employee_staff_id": profile_data["employee_staff_id"],
                    "access": profile_data["access"],
                },
            )
            if not profile_created and profile.access != profile_data["access"]:
                profile.access = profile_data["access"]
                profile.save(update_fields=["access"])
            status = "created" if profile_created else "already exists"
            self.stdout.write(self.style.SUCCESS(f"Client Profile: {profile.full_name} @ {inst.name} ({status})"))

        self.stdout.write(self.style.SUCCESS("\nSeeding complete!"))
