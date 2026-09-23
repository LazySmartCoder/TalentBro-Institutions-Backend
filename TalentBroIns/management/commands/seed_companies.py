import datetime

from django.core.management.base import BaseCommand

from TalentBroIns.models import ClientProfile, Company, Institution


COMPANIES = [
    {
        "company_name": "Tata Consultancy Services (TCS)",
        "industry": "IT Services",
        "company_description": (
            "India's largest IT services and consulting company, offering "
            "enterprise technology solutions to clients across 50+ countries."
        ),
        "job_roles": ["Systems Engineer", "Associate Software Engineer", "Trainee"],
        "eligible_courses": ["B.Tech", "B.E.", "M.Tech", "MCA", "BCA"],
        "eligible_branches": ["CSE", "IT", "ECE", "EEE", "Mechanical", "Civil"],
        "minimum_cgpa": 6.0,
        "maximum_backlogs": 2,
        "graduation_year": 2026,
        "required_skills": ["Java", "Python", "SQL", "Data Structures"],
        "preferred_skills": ["Cloud", "Machine Learning", "React"],
        "salary_min": 3.5,
        "salary_max": 7.0,
        "work_location": "Bengaluru, Hyderabad, Pune",
        "work_mode": "hybrid",
        "number_of_openings": 120,
        "selection_rounds": ["Aptitude Test", "Technical Interview", "HR Interview"],
        "application_deadline": datetime.date(2026, 10, 15),
        "campus_visit_date": datetime.date(2026, 10, 28),
        "recruitment_status": "upcoming",
        "placement_mode": "full_time",
        "offer_status": "pending",
    },
    {
        "company_name": "Infosys",
        "industry": "IT Services",
        "company_description": (
            "Global leader in next-generation digital services and consulting, "
            "known for its large graduate-hiring programme 'Infosys Springboard'."
        ),
        "job_roles": ["Infosys Systems Engineer", "Digital Specialist Engineer"],
        "eligible_courses": ["B.Tech", "B.E.", "MCA"],
        "eligible_branches": ["CSE", "IT", "ECE"],
        "minimum_cgpa": 6.5,
        "maximum_backlogs": 1,
        "graduation_year": 2026,
        "required_skills": ["C/C++", "Java", "Python", "DBMS"],
        "preferred_skills": ["AWS", "Angular", "Spring Boot"],
        "salary_min": 3.6,
        "salary_max": 8.0,
        "work_location": "Bengaluru, Mysuru, Hyderabad",
        "work_mode": "hybrid",
        "number_of_openings": 100,
        "selection_rounds": ["Online Assessment", "Technical Interview", "HR Round"],
        "application_deadline": datetime.date(2026, 10, 20),
        "campus_visit_date": datetime.date(2026, 11, 3),
        "recruitment_status": "upcoming",
        "placement_mode": "full_time",
        "offer_status": "pending",
    },
    {
        "company_name": "Wipro",
        "industry": "IT Services",
        "company_description": (
            "Leading technology services and consulting company delivering "
            "business transformation and IT solutions globally."
        ),
        "job_roles": ["Project Engineer", "Project Trainee"],
        "eligible_courses": ["B.Tech", "B.E.", "BCA", "MCA"],
        "eligible_branches": ["CSE", "IT", "ECE", "EEE"],
        "minimum_cgpa": 6.0,
        "maximum_backlogs": 2,
        "graduation_year": 2026,
        "required_skills": ["Java", "SQL", "OOP", "Web Technologies"],
        "preferred_skills": ["DevOps", "Python", "React"],
        "salary_min": 3.5,
        "salary_max": 6.5,
        "work_location": "Bengaluru, Chennai, Kolkata",
        "work_mode": "onsite",
        "number_of_openings": 90,
        "selection_rounds": ["Aptitude Test", "Coding Test", "Technical Interview"],
        "application_deadline": datetime.date(2026, 10, 25),
        "campus_visit_date": datetime.date(2026, 11, 10),
        "recruitment_status": "upcoming",
        "placement_mode": "full_time",
        "offer_status": "pending",
    },
    {
        "company_name": "HCL Technologies",
        "industry": "IT Services",
        "company_description": (
            "Multinational IT services company offering software services, "
            "infrastructure management and engineering services."
        ),
        "job_roles": ["Graduate Engineer Trainee", "Software Engineer"],
        "eligible_courses": ["B.Tech", "B.E.", "MCA"],
        "eligible_branches": ["CSE", "IT", "ECE", "EEE"],
        "minimum_cgpa": 6.0,
        "maximum_backlogs": 2,
        "graduation_year": 2026,
        "required_skills": ["Core Java", "SQL", "Networking", "Linux"],
        "preferred_skills": ["Cloud Computing", "Python", "Kubernetes"],
        "salary_min": 3.5,
        "salary_max": 6.0,
        "work_location": "Noida, Chennai, Bengaluru",
        "work_mode": "onsite",
        "number_of_openings": 80,
        "selection_rounds": ["Aptitude", "Technical Interview", "HR Round"],
        "application_deadline": datetime.date(2026, 11, 5),
        "campus_visit_date": datetime.date(2026, 11, 18),
        "recruitment_status": "upcoming",
        "placement_mode": "full_time",
        "offer_status": "pending",
    },
    {
        "company_name": "Tech Mahindra",
        "industry": "IT Services",
        "company_description": (
            "Part of the Mahindra Group, providing IT services, "
            "business and engineering consulting to telecom and hi-tech clients."
        ),
        "job_roles": ["Service Desk Engineer", "Associate Engineer"],
        "eligible_courses": ["B.Tech", "B.E.", "BCA", "MCA"],
        "eligible_branches": ["CSE", "IT", "ECE"],
        "minimum_cgpa": 6.0,
        "maximum_backlogs": 3,
        "graduation_year": 2026,
        "required_skills": ["Java", "Python", "SQL", "Networking"],
        "preferred_skills": ["Artificial Intelligence", "Cloud", "Testing"],
        "salary_min": 3.2,
        "salary_max": 5.5,
        "work_location": "Pune, Bengaluru, Hyderabad",
        "work_mode": "hybrid",
        "number_of_openings": 70,
        "selection_rounds": ["Online Test", "Technical Round", "HR Interview"],
        "application_deadline": datetime.date(2026, 11, 10),
        "campus_visit_date": datetime.date(2026, 11, 24),
        "recruitment_status": "upcoming",
        "placement_mode": "full_time",
        "offer_status": "pending",
    },
    {
        "company_name": "Larsen & Toubro (L&T)",
        "industry": "Engineering & Construction",
        "company_description": (
            "Indian multinational conglomerate in the engineering, construction, "
            "manufacturing and technology sectors."
        ),
        "job_roles": ["Graduate Engineer Trainee", "Project Engineer"],
        "eligible_courses": ["B.Tech", "B.E."],
        "eligible_branches": ["Civil", "Mechanical", "Electrical", "CSE"],
        "minimum_cgpa": 7.0,
        "maximum_backlogs": 0,
        "graduation_year": 2026,
        "required_skills": ["AutoCAD", "AutoCAD Civil 3D", "STAAD Pro"],
        "preferred_skills": ["Revit", "Project Management", "Lean Six Sigma"],
        "salary_min": 5.0,
        "salary_max": 9.0,
        "work_location": "Chennai, Mumbai, Delhi NCR",
        "work_mode": "onsite",
        "number_of_openings": 60,
        "selection_rounds": ["Campus Test", "Group Discussion", "Technical Interview"],
        "application_deadline": datetime.date(2026, 11, 15),
        "campus_visit_date": datetime.date(2026, 12, 1),
        "recruitment_status": "upcoming",
        "placement_mode": "full_time",
        "offer_status": "pending",
    },
    {
        "company_name": "HDFC Bank",
        "industry": "Banking & Financial Services",
        "company_description": (
            "India's largest private sector bank offering a wide range of "
            "retail, wholesale and rural banking products and services."
        ),
        "job_roles": ["Management Trainee", "Branch Operations Officer"],
        "eligible_courses": ["B.Tech", "BBA", "B.Com", "MBA"],
        "eligible_branches": ["CSE", "IT", "Finance", "Marketing", "HR"],
        "minimum_cgpa": 6.5,
        "maximum_backlogs": 1,
        "graduation_year": 2026,
        "required_skills": ["Financial Analysis", "MS Excel", "Communication"],
        "preferred_skills": ["Python", "Credit Analytics", "Power BI"],
        "salary_min": 5.0,
        "salary_max": 10.0,
        "work_location": "Mumbai, Bengaluru, Pune",
        "work_mode": "onsite",
        "number_of_openings": 50,
        "selection_rounds": ["Aptitude Test", "Group Discussion", "Personal Interview"],
        "application_deadline": datetime.date(2026, 11, 20),
        "campus_visit_date": datetime.date(2026, 12, 5),
        "recruitment_status": "upcoming",
        "placement_mode": "full_time",
        "offer_status": "pending",
    },
    {
        "company_name": "Reliance Jio Platforms",
        "industry": "Telecommunications",
        "company_description": (
            "Part of Reliance Industries, Jio leads India's digital revolution "
            "with 4G/5G telecom, broadband and a suite of digital services."
        ),
        "job_roles": ["Software Engineer", "Network Engineer"],
        "eligible_courses": ["B.Tech", "B.E.", "MCA"],
        "eligible_branches": ["CSE", "IT", "ECE", "EEE"],
        "minimum_cgpa": 6.5,
        "maximum_backlogs": 1,
        "graduation_year": 2026,
        "required_skills": ["C++", "Python", "Networking", "Linux"],
        "preferred_skills": ["5G", "Cloud", "Machine Learning"],
        "salary_min": 6.0,
        "salary_max": 12.0,
        "work_location": "Mumbai, Navi Mumbai",
        "work_mode": "onsite",
        "number_of_openings": 45,
        "selection_rounds": ["Coding Test", "Technical Interview", "HR Round"],
        "application_deadline": datetime.date(2026, 12, 1),
        "campus_visit_date": datetime.date(2026, 12, 12),
        "recruitment_status": "upcoming",
        "placement_mode": "full_time",
        "offer_status": "pending",
    },
    {
        "company_name": "Zomato",
        "industry": "Consumer Technology",
        "company_description": (
            "India's leading food delivery and dining-out platform, whose "
            "engineering teams build order, logistics and discovery products at scale."
        ),
        "job_roles": ["Software Development Engineer", "Data Analyst"],
        "eligible_courses": ["B.Tech", "B.E.", "MCA"],
        "eligible_branches": ["CSE", "IT", "ECE"],
        "minimum_cgpa": 7.0,
        "maximum_backlogs": 0,
        "graduation_year": 2026,
        "required_skills": ["Data Structures", "Algorithms", "Java", "SQL"],
        "preferred_skills": ["Go", "React", "Kafka", "System Design"],
        "salary_min": 14.0,
        "salary_max": 22.0,
        "work_location": "Gurugram, Bengaluru",
        "work_mode": "onsite",
        "number_of_openings": 25,
        "selection_rounds": ["Online Assessment", "DSA Interview", "System Design", "HR"],
        "application_deadline": datetime.date(2026, 12, 5),
        "campus_visit_date": datetime.date(2026, 12, 18),
        "recruitment_status": "upcoming",
        "placement_mode": "internship_ppo",
        "offer_status": "pending",
    },
    {
        "company_name": "Mahindra & Mahindra",
        "industry": "Automotive",
        "company_description": (
            "Indian multinational automotive manufacturer with a strong focus "
            "on SUVs, electric vehicles and farm equipment."
        ),
        "job_roles": ["Graduate Engineer Trainee", "Production Engineer"],
        "eligible_courses": ["B.Tech", "B.E."],
        "eligible_branches": ["Mechanical", "Electrical", "Automobile", "CSE"],
        "minimum_cgpa": 6.5,
        "maximum_backlogs": 1,
        "graduation_year": 2026,
        "required_skills": ["CATIA", "Thermodynamics", "Electronics", "Python"],
        "preferred_skills": ["Electric Vehicles", "IOT", "Embedded Systems"],
        "salary_min": 5.5,
        "salary_max": 9.5,
        "work_location": "Mumbai, Nashik, Chennai",
        "work_mode": "onsite",
        "number_of_openings": 40,
        "selection_rounds": ["Aptitude Test", "Technical Interview", "HR Round"],
        "application_deadline": datetime.date(2026, 12, 10),
        "campus_visit_date": datetime.date(2026, 12, 22),
        "recruitment_status": "upcoming",
        "placement_mode": "full_time",
        "offer_status": "pending",
    },
]


TIER_BY_NAME = {
    "Tata Consultancy Services (TCS)": "dream",
    "Infosys": "dream",
    "Wipro": "core",
    "HCL Technologies": "core",
    "Tech Mahindra": "core",
    "Larsen & Toubro (L&T)": "dream",
    "HDFC Bank": "dream",
    "Reliance Jio Platforms": "super_dream",
    "Zomato": "super_dream",
    "Mahindra & Mahindra": "dream",
}


class Command(BaseCommand):
    help = "Seed 10 Indian placement-drive companies for Raj Patel's institution"

    def handle(self, *args, **options):
        try:
            client = ClientProfile.objects.select_related("institution").get(pk=13)
        except ClientProfile.DoesNotExist:
            self.stdout.write(self.style.ERROR("ClientProfile with pk=13 (Raj Patel) not found."))
            return

        institution = client.institution
        if institution is None:
            self.stdout.write(
                self.style.ERROR("Raj Patel has no linked institution. Link one first.")
            )
            return

        self.stdout.write(f"Linking companies to client: {client.full_name} @ {institution.name}")

        for data in COMPANIES:
            data = {**data, "tier": TIER_BY_NAME[data["company_name"]]}
            company, created = Company.objects.update_or_create(
                company_name=data["company_name"],
                institution=institution,
                defaults={**data, "client": client},
            )
            status = "created" if created else "synced"
            self.stdout.write(
                self.style.SUCCESS(f"Company: {company.company_name} [{company.company_id}] ({status})")
            )

        total = Company.objects.filter(institution=institution).count()
        self.stdout.write(self.style.SUCCESS(f"\nSeeding complete! {total} company record(s) for {institution.name}."))