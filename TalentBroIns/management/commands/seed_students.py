import datetime

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from TalentBroIns.models import CandidateProfile, ClientProfile


FIRST = ["Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Rohan", "Kiran", "Ananya",
         "Riya", "Ishita", "Sneha", "Pranav", "Nikhil", "Dev", "Amit", "Suraj", "Neha",
         "Priya", "Kavya", "Manish", "Varun", "Tejas", "Harsh", "Sakshi", "Tanvi", "Gaurav",
         "Rahul", "Meera", "Divya", "Siddharth", "Om", "Shreya", "Akash", "Nandini", "Yash",
         "Pooja", "Vikram", "Aditi", "Ritika", "Kunal", "Sahil", "Ira", "Mihir", "Anjali",
         "Swara", "Aryan", "Disha"]
LAST = ["Patil", "Sharma", "Kulkarni", "Deshmukh", "Joshi", "Nair", "Reddy", "Iyer",
         "Menon", "Gowda", "Bhattacharya", "Mehta", "Rane", "Pillai", "Verma", "Shetty",
         "Chavan", "Agarwal", "Sinha", "Jadhav", "Kadam", "Bhosale", "Thakur", "Mane",
         "Pawar", "Gavde", "Sathe", "Borkar", "Pandit", "Khot"]
GENDERS = ["male", "female", "other", "prefer_not_to_say"]
STATUSES = ["placed", "shortlisted", "applying", "not_started"]

# (department, program, roles) — department uses the same long names the
# frontend student page filters by.
BRANCHES = [
    ("Computer Engineering", "B.Tech", ["Software Engineer", "Data Analyst"]),
    ("Information Technology", "B.Tech", ["Systems Engineer", "Cloud Engineer"]),
    ("Electronics & Telecom", "B.Tech", ["Network Engineer", "Embedded Engineer"]),
    ("Mechanical Engineering", "B.Tech", ["Design Engineer", "Graduate Trainee"]),
    ("Civil Engineering", "B.Tech", ["Site Engineer", "Project Engineer"]),
    ("AI & Data Science", "B.Tech", ["ML Engineer", "Data Analyst"]),
]
SKILL_POOL = [
    ["Python", "SQL", "Pandas"],
    ["Java", "Spring Boot", "MySQL"],
    ["C++", "Data Structures", "Algorithms"],
    ["React", "Node.js", "PostgreSQL"],
    ["AWS", "Docker", "Kubernetes"],
    ["AutoCAD", "SolidWorks", "ANSYS"],
    ["Verilog", "VLSI", "Embedded C"],
    ["STAAD Pro", "Revit", "Surveying"],
    ["Machine Learning", "TensorFlow", "Python"],
    ["Networking", "Linux", "AWS"],
]


def cgpa_to_status(cgpa):
    if cgpa >= 8.5:
        return "placed"
    if cgpa >= 7.2:
        return "shortlisted"
    if cgpa >= 6.4:
        return "applying"
    return "not_started"


class Command(BaseCommand):
    help = "Seed ~48 final-year students for Raj Patel's institution (pk=6)"

    def handle(self, *args, **options):
        try:
            client = ClientProfile.objects.select_related("institution").get(pk=13)
        except ClientProfile.DoesNotExist:
            self.stdout.write(self.style.ERROR("ClientProfile pk=13 (Raj Patel) not found."))
            return
        inst = client.institution
        if inst is None:
            self.stdout.write(self.style.ERROR("Raj Patel has no institution."))
            return
        self.stdout.write(f"Seeding students for {inst.name}")

        created_total = existing_total = 0
        for i in range(48):
            branch, program, role_hint = BRANCHES[i % len(BRANCHES)]
            first = FIRST[i % len(FIRST)]
            last = LAST[(i * 7) % len(LAST)]
            email = f"{first.lower()}.{last.lower()}{i}@svit.in"
            department = branch

            if i % 13 == 0:
                program = "BCA"
            elif i % 17 == 0:
                program = "BBA"

            cgpa = round(5.6 + ((i * 7919) % 410) / 100.0, 2)
            status = cgpa_to_status(cgpa)
            eligible = cgpa >= 6.0 or status in ("placed", "shortlisted")
            skills = SKILL_POOL[i % len(SKILL_POOL)]
            preferred_roles = role_hint if status != "not_started" else []
            expected_ctc = round(4.0 + ((i * 13) % 14), 1) if status in ("placed", "shortlisted") else None

            user, u_created = User.objects.get_or_create(
                username=email,
                defaults={
                    "email": email,
                    "first_name": first,
                    "last_name": last,
                },
            )
            if u_created:
                user.set_unusable_password()
                user.save()

            created_at = timezone.make_aware(
                datetime.datetime(2026, 1 + (i % 8), 4 + (i % 22), 9, (i * 7) % 60)
            )
            profile, p_created = CandidateProfile.objects.update_or_create(
                user=user,
                college=inst,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "department": department,
                    "program": program,
                    "start_year": 2022,
                    "end_year": 2026,
                    "mobile_number": f"+91 9{str(800000000 + i * 2719).zfill(9)}",
                    "gender": GENDERS[i % len(GENDERS)],
                    "cgpa": cgpa,
                    "placement_status": status,
                    "placement_eligible": eligible,
                    "skills": skills,
                    "preferred_roles": preferred_roles,
                    "preferred_locations": ["Pune", "Bengaluru", "Hyderabad"],
                    "expected_ctc": expected_ctc,
                    "id_verified": (i % 7 != 0),  # ~85% verified like a real batch
                    "created_at": created_at,
                    "updated_at": created_at,
                },
            )
            if p_created:
                created_total += 1
            else:
                existing_total += 1

        total = CandidateProfile.objects.filter(college=inst).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeding complete! {created_total} created, {existing_total} synced. "
                f"Total students for {inst.name}: {total}."
            )
        )