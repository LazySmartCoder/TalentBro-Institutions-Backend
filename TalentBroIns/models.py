import random
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone


COURSES_OFFERED = [
    'B.Tech', 'B.E.', 'BCA', 'BBA', 'B.Com', 'B.Sc.', 'BA', 'BMS', 'BBM',
    'B.Des', 'B.Arch', 'B.Pharm', 'MBBS', 'BDS', 'BAMS', 'BHMS', 'BPT',
    'B.Sc. Nursing', 'B.Ed', 'LLB', 'BA LLB', 'BBA LLB', 'BJMC', 'BHM',
    'BFA', 'B.Voc', 'M.Tech', 'M.E.', 'MCA', 'MBA', 'PGDM', 'M.Com',
    'M.Sc.', 'MA', 'M.Des', 'M.Arch', 'M.Pharm', 'M.Ed', 'LLM', 'MPT',
    'Diploma', 'ITI', 'PG Diploma', 'Ph.D.', 'Other',
]
COURSE_CHOICES = [(course, course) for course in COURSES_OFFERED]

# Every account is either a Student (candidate) or Institution Staff.
# Note: in this entire project candidates and students are the SAME thing.
ROLE_CHOICES = [
    ('student', 'Student'),
    ('institution_staff', 'Institution Staff'),
]

ROLE_STUDENT = 'student'
ROLE_INSTITUTION_STAFF = 'institution_staff'

INSTITUTION_TYPE_CHOICES = [
    ('University', 'University'),
    ('Deemed University', 'Deemed University'),
    ('Autonomous College', 'Autonomous College'),
    ('College', 'College'),
    ('Institute', 'Institute'),
    ('Polytechnic', 'Polytechnic'),
    ('ITI', 'ITI'),
    ('Other', 'Other'),
]

MOBILE_NUMBER_VALIDATOR = RegexValidator(
    regex=r'^\+?[0-9]{10,15}$',
    message='Enter a valid mobile number (10-15 digits).',
)
PIN_CODE_VALIDATOR = RegexValidator(
    regex=r'^[1-9][0-9]{5}$',
    message='Enter a valid 6-digit PIN Code.',
)


class Institution(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='institution',
    )
    name = models.CharField(max_length=255)

    institution_type = models.CharField(max_length=30, choices=INSTITUTION_TYPE_CHOICES)
    website = models.URLField(blank=True)
    email_domain = models.CharField(max_length=255)
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pin_code = models.CharField(max_length=6, validators=[PIN_CODE_VALIDATOR])
    logo = models.URLField(blank=True, default='')

    placement_department_name = models.CharField(max_length=255)
    placement_office_email = models.EmailField()
    approximate_student_strength = models.PositiveIntegerField()
    courses_offered = models.JSONField(default=list)
    departments = models.CharField(max_length=255, blank=True, default='')
    companies = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if not isinstance(self.courses_offered, list) or not all(
            isinstance(course, str) for course in self.courses_offered
        ):
            raise ValidationError(
                {'courses_offered': 'Courses offered must be a list of course names.'}
            )
        invalid = [
            course for course in self.courses_offered
            if course not in COURSES_OFFERED
        ]
        if invalid:
            raise ValidationError(
                {'courses_offered': f'Invalid course(s): {", ".join(invalid)}'}
            )
        if len(set(self.courses_offered)) != len(self.courses_offered):
            raise ValidationError(
                {'courses_offered': 'Duplicate courses are not allowed.'}
            )


class ClientProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name='profiles',
        null=True, blank=True,
    )

    full_name = models.CharField(max_length=120)
    official_email = models.EmailField()
    avatar = models.URLField(blank=True, default='')
    mobile_number = models.CharField(
        max_length=16, blank=True, default='',
        validators=[MOBILE_NUMBER_VALIDATOR],
    )
    designation = models.CharField(max_length=120, blank=True, default='')
    employee_staff_id = models.CharField(max_length=60, blank=True, default='')

    # Access level for the institution dashboard.
    # Beta = read-only      |      Master = full (create drives, edit data)
    ACCESS_CHOICES = [
        ('beta', 'Beta'),
        ('master', 'Master'),
    ]
    ACCESS_BETA = 'beta'
    ACCESS_MASTER = 'master'
    access = models.CharField(
        max_length=20,
        choices=ACCESS_CHOICES,
        default=ACCESS_BETA,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['full_name']

    def __str__(self):
        if self.institution_id is None:
            return self.full_name
        return f'{self.full_name} ({self.institution.name})'

    @property
    def is_master(self):
        return self.access == self.ACCESS_MASTER

    @property
    def is_beta(self):
        return self.access == self.ACCESS_BETA


WORK_MODE_CHOICES = [
    ('remote', 'Remote'),
    ('hybrid', 'Hybrid'),
    ('onsite', 'On-site'),
    ('field', 'Field / Outside'),
]

RECRUITMENT_STATUS_CHOICES = [
    ('upcoming', 'Upcoming'),
    ('ongoing', 'Active / Ongoing'),
    ('completed', 'Completed'),
    ('cancelled', 'Cancelled'),
]

PLACEMENT_MODE_CHOICES = [
    ('full_time', 'Full-time'),
    ('internship_ppo', 'Internship + PPO'),
    ('contract', 'Contract'),
]

OFFER_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('offered', 'Offered'),
    ('on_hold', 'On Hold'),
    ('revoked', 'Revoked'),
]

COMPANY_TIER_CHOICES = [
    ('super_dream', 'Super Dream'),
    ('dream', 'Dream'),
    ('core', 'Core'),
    ('mass', 'Mass'),
]


class Company(models.Model):
    """A company visiting an institution for a placement drive.

    Companies are recorded by the institution staff (via their ClientProfile)
    for the institution they belong to, so every company row is scoped to
    exactly one Institution and one ClientProfile.
    """

    company_id = models.CharField(
        max_length=30, unique=True, blank=True, default='',
        help_text='Human-friendly unique id. Auto-generated when left blank.',
    )
    company_name = models.CharField(max_length=255)
    industry = models.CharField(max_length=120, blank=True, default='')
    company_description = models.TextField(blank=True, default='')

    job_roles = models.JSONField(default=list, blank=True)
    eligible_courses = models.JSONField(default=list, blank=True)
    eligible_branches = models.JSONField(default=list, blank=True)
    minimum_cgpa = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True,
        help_text='Minimum CGPA required (on a 10-point scale).',
    )
    maximum_backlogs = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text='Maximum number of active backlogs allowed (0 = none).',
    )
    graduation_year = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Batch year eligible for the drive (e.g. 2026).',
    )
    required_skills = models.JSONField(default=list, blank=True)
    preferred_skills = models.JSONField(default=list, blank=True)

    # Annual salary band, expressed in LPA (lakhs per annum) as used across the UI.
    salary_min = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text='Minimum annual CTC in LPA.',
    )
    salary_max = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text='Maximum annual CTC in LPA.',
    )

    work_location = models.CharField(max_length=255, blank=True, default='')
    work_mode = models.CharField(max_length=20, choices=WORK_MODE_CHOICES, default='onsite')
    number_of_openings = models.PositiveIntegerField(null=True, blank=True)
    selection_rounds = models.JSONField(default=list, blank=True)

    application_deadline = models.DateField(null=True, blank=True)
    campus_visit_date = models.DateField(null=True, blank=True)
    recruitment_status = models.CharField(
        max_length=20, choices=RECRUITMENT_STATUS_CHOICES, default='upcoming',
    )
    placement_mode = models.CharField(
        max_length=20, choices=PLACEMENT_MODE_CHOICES, default='full_time',
    )
    tier = models.CharField(
        max_length=20, choices=COMPANY_TIER_CHOICES, default='core',
        help_text='Hiring tier used by placement cells (CTC bracket based).',
    )
    offer_status = models.CharField(
        max_length=20, choices=OFFER_STATUS_CHOICES, default='pending',
    )

    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name='company_records',
        help_text='The institution the company is visiting for placements.',
    )
    client = models.ForeignKey(
        ClientProfile,
        on_delete=models.CASCADE,
        related_name='companies',
        help_text='The institution staff member who recorded this company.',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.company_name} @ {self.institution.name}'

    def save(self, *args, **kwargs):
        if not self.company_id:
            self.company_id = self.generate_company_id()
        super().save(*args, **kwargs)

    def generate_company_id(self):
        """Build a readable unique id like TCS-8F3A2B from the company name."""
        stem = ''.join(
            ch for ch in self.company_name.upper() if ch.isalnum()
        )[:5] or 'CMP'
        suffix = uuid.uuid4().hex[:6].upper()
        return f'{stem}-{suffix}'


GENDER_CHOICES = [
    ('male', 'Male'),
    ('female', 'Female'),
    ('other', 'Other'),
    ('prefer_not_to_say', 'Prefer Not to Say'),
]

PLACEMENT_STATUS_CHOICES = [
    ('not_started', 'Not Started'),
    ('applying', 'Applying'),
    ('shortlisted', 'Shortlisted'),
    ('placed', 'Placed'),
]

ACCOUNT_STATUS_CHOICES = [
    ('active', 'Active'),
    ('inactive', 'Inactive'),
    ('suspended', 'Suspended'),
    ('closed', 'Closed'),
]

# The candidate's preferred language for talks and communication training.
LANGUAGE_CHOICES = [
    ('english', 'English'),
    ('hindi', 'Hindi'),
    ('bengali', 'Bengali'),
    ('tamil', 'Tamil'),
    ('telugu', 'Telugu'),
    ('marathi', 'Marathi'),
    ('kannada', 'Kannada'),
    ('gujarati', 'Gujarati'),
    ('malayalam', 'Malayalam'),
    ('punjabi', 'Punjabi'),
    ('odia', 'Odia'),
    ('assamese', 'Assamese'),
    ('urdu', 'Urdu'),
]


def user_role(user):
    """Derive an account's role from its profile.

    A user with a CandidateProfile (candidate == student) is a Student;
    everyone with staff/superuser flags or a ClientProfile/Institution is
    Institution Staff. Profile-less accounts default to Student, matching this
    app's primary self-serve (candidate) signup flow.
    """
    if user.is_superuser or user.is_staff:
        return ROLE_INSTITUTION_STAFF
    if hasattr(user, 'institution'):
        return ROLE_INSTITUTION_STAFF
    if hasattr(user, 'profile'):
        return ROLE_INSTITUTION_STAFF
    if hasattr(user, 'candidate_profile'):
        return ROLE_STUDENT
    return ROLE_STUDENT


class CandidateProfile(models.Model):
    candidate_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False,
    )
    # The auth User the candidate belongs to. In this project candidates == students,
    # so this is the student's own account (self-serve) or the account created for them.
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='candidate_profile',
        null=True, blank=True,
    )
    # Candidate == student. These fields are self-served so they are optional
    # until the candidate completes them (institution staff may fill them too).
    # The name is split across first / middle / last fields, captured during
    # onboarding (self-serve) or by institution staff. They are nullable /
    # blank-enabled here to allow a placeholder profile row to be created when
    # the account is first created. `full_name` is provided as a computed
    # convenience property.
    first_name = models.CharField(max_length=255, blank=True, default='')
    middle_name = models.CharField(max_length=120, blank=True, default='')
    last_name = models.CharField(max_length=255, blank=True, default='')
    college = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name='candidate_profiles',
        null=True, blank=True,
    )
    department = models.CharField(max_length=120, blank=True, default='')
    program = models.CharField(
        max_length=120, choices=COURSE_CHOICES, default='',
    )
    start_year = models.PositiveIntegerField(null=True, blank=True)
    end_year = models.PositiveIntegerField(null=True, blank=True)

    personal_email = models.EmailField(blank=True, default='')
    avatar = models.URLField(blank=True, default='')
    mobile_number = models.CharField(
        max_length=16, blank=True, default='',
        validators=[MOBILE_NUMBER_VALIDATOR],
    )
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=20, choices=GENDER_CHOICES, default='',
    )
    cgpa = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)

    placement_status = models.CharField(
        max_length=30,
        choices=PLACEMENT_STATUS_CHOICES,
        default='not_started',
    )
    placement_eligible = models.BooleanField(default=True)

    linkedin_url = models.URLField(blank=True, default='')
    github_url = models.URLField(blank=True)
    portfolio_url = models.URLField(blank=True)

    skills = models.JSONField(default=list, blank=True)
    certifications = models.JSONField(default=list, blank=True)
    projects = models.JSONField(default=list, blank=True)
    internships = models.JSONField(default=list, blank=True)

    preferred_roles = models.JSONField(default=list, blank=True)
    preferred_locations = models.JSONField(default=list, blank=True)
    preferred_language = models.CharField(
        max_length=30, blank=True, default='',
        help_text="The candidate's preferred language (e.g., English, Hindi, Bengali).",
    )
    expected_ctc = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
    )
    time_spent = models.PositiveIntegerField(
        default=0, help_text="Total time spent on the platform, in minutes (cumulative across sessions).",
    )

    account_status = models.CharField(
        max_length=20,
        choices=ACCOUNT_STATUS_CHOICES,
        default='active',
    )
    # Set to True by the ID-card verification endpoint once Gemini confirms the
    # student's name, registration number and college against the OCR text. The
    # profile cannot be marked complete until this is True (compulsory step).
    id_verified = models.BooleanField(default=False)
    last_login_at = models.DateTimeField(null=True, blank=True)

    # Total AI (Gemini) spend burnt by this candidate while using TalentBro,
    # in INR and already including the 40% service margin. Kept on the profile
    # row so it keeps rising as the student uses the AI features, and other
    # tables can sum/compare it per candidate without an extra ledger.
    cost_incurred = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=Decimal('0.0000'),
        help_text='Total Gemini cost incurred by this candidate in INR (including 40% markup).',
    )

    # TalentBro Readiness Score and its derived rankings, persisted so the
    # database itself always holds the current values (no on-the-fly need at
    # render time). Recomputed in real time whenever the underlying signals
    # change (mock interviews, self-training, chat engagement).
    readiness_score = models.FloatField(
        null=True, blank=True,
        help_text='Composite TalentBro Readiness Score (0–100) for this candidate.',
    )
    readiness_overall_rank = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='All Institute Rank (AIR) of this candidate within their own college.',
    )
    readiness_overall_total = models.PositiveIntegerField(
        default=0,
        help_text='Number of students in this candidate\'s college (full roll) in the AIR denominator.',
    )
    readiness_department_rank = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Rank of this candidate among same-department peers in their college.',
    )
    readiness_department_total = models.PositiveIntegerField(
        default=0,
        help_text='Number of students in this candidate\'s department (full roll) ranked.',
    )
    readiness_components = models.JSONField(
        default=dict, blank=True,
        help_text='Flattened readiness pillar breakdown (mock/self-training/chat/modules).',
    )
    readiness_updated_at = models.DateTimeField(
        null=True, blank=True,
        help_text='When this candidate\'s readiness score and ranks were last recomputed.',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['first_name', 'last_name']

    @property
    def full_name(self):
        return ' '.join(
            part for part in (self.first_name, self.middle_name, self.last_name)
            if part
        ).strip()

    @full_name.setter
    def full_name(self, value):
        """Split a single full-name string into first/middle/last parts.

        Kept so legacy call sites (signup, seeds, tests) can keep writing a
        combined name; the parts are derived from it.
        """
        parts = str(value or '').strip().split()
        self.first_name = parts[0] if parts else ''
        self.middle_name = ' '.join(parts[1:-1]) if len(parts) > 2 else ''
        self.last_name = parts[-1] if len(parts) > 1 else ''

    def __str__(self):
        name = self.full_name or 'Candidate'
        college = self.college.name if self.college else 'No college'
        return f'{name} ({college})'

    def mark_login(self):
        self.last_login_at = timezone.now()
        self.save(update_fields=['last_login_at', 'updated_at'])


CHAT_ROLE_CHOICES = [
    ('user', 'User'),
    ('assistant', 'Assistant'),
]


class ChatSession(models.Model):
    """Persisted student↔TalentBro Gemini conversation."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_sessions',
    )
    title = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.title or "Untitled chat"} ({self.user.get_full_name() or self.user.username})'


class ChatMessage(models.Model):
    """A single turn inside a ChatSession."""

    session = models.ForeignKey(
        ChatSession, on_delete=models.CASCADE, related_name='messages',
    )
    role = models.CharField(max_length=10, choices=CHAT_ROLE_CHOICES)
    content = models.TextField()
    # Preferred-language rendering of an assistant reply so students who prefer
    # reading in another language can follow along while the canonical reply
    # always stays in English. Empty for user turns and English replies.
    translation = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']

    def __str__(self):
        return f'{self.role}: {self.content[:40]}'


APLR_CATEGORY_CHOICES = [
    ('quantitative', 'Quantitative Aptitude'),
    ('logical_reasoning', 'Logical Reasoning'),
    ('verbal', 'Verbal Reasoning'),
    ('data_interpretation', 'Data Interpretation'),
    ('puzzle', 'Puzzles'),
    ('miscellaneous', 'Miscellaneous'),
]

APLR_STATUS_CHOICES = [
    ('active', 'Active'),
    ('solved', 'Solved'),
    ('gave_up', 'Gave Up'),
]

APLR_STATUS_ACTIVE = 'active'
APLR_STATUS_SOLVED = 'solved'
APLR_STATUS_GAVE_UP = 'gave_up'


class APLRTraining(models.Model):
    """Aptitude & Logical Reasoning (APLR) training session — one question per chat.

    Each session holds A SINGLE placement-style aptitude or logical reasoning
    question. The student works through it inside one chat: they give the answer
    AND the approach/method they used, while Ada (the AI coach) nudges them
    toward the conventional way to solve it. The session is locked as 'solved'
    (points awarded) or 'gave_up' (solution revealed) the moment the question is
    resolved, and the frontend immediately opens a fresh session for the next
    question — one question, one chat.

    The full chat lives in ``transcript`` (same {role, content, created_at}
    shape CommunicationTraining keeps) and every gamification metric is stored
    on the row so history/reporting can derive XP, streaks and accuracy.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='aplr_sessions',
    )
    title = models.CharField(max_length=255, blank=True, default='')
    category = models.CharField(
        max_length=40,
        choices=APLR_CATEGORY_CHOICES,
        default='puzzle',
    )
    question = models.TextField(blank=True, default='')
    # Model-generated ground truth for the question (best-effort). Kept on the
    # row so the evaluator can score the student's answer consistently and the
    # give-up path can always reveal the full conventional solution.
    answer = models.TextField(blank=True, default='')
    solution = models.TextField(blank=True, default='')
    transcript = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=12,
        choices=APLR_STATUS_CHOICES,
        default=APLR_STATUS_ACTIVE,
    )
    attempts = models.PositiveIntegerField(
        default=0,
        help_text='Number of tries the student made before resolving the question.',
    )
    hints_used = models.PositiveIntegerField(
        default=0,
        help_text='Number of hints Ada handed out during the attempt.',
    )
    points_awarded = models.PositiveIntegerField(
        default=0,
        help_text='XP earned for solving this question (0 when given up).',
    )
    star_rating = models.PositiveSmallIntegerField(
        default=0,
        help_text='Approach quality shown by the student (1–5) when solved.',
    )
    solved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title or "APLR question"} ({self.get_status_display().lower()})'


BASIC_MATH_CATEGORY_CHOICES = [
    ('addition_subtraction', 'Addition & Subtraction'),
    ('multiplication_division', 'Multiplication & Division'),
    ('fractions_decimals', 'Fractions & Decimals'),
    ('percentage', 'Percentages'),
    ('ratio_average', 'Ratio & Average'),
    ('mental_math', 'Mental Math'),
]

BASIC_MATH_STATUS_CHOICES = [
    ('active', 'Active'),
    ('solved', 'Solved'),
    ('gave_up', 'Gave Up'),
]

BASIC_MATH_STATUS_ACTIVE = 'active'
BASIC_MATH_STATUS_SOLVED = 'solved'
BASIC_MATH_STATUS_GAVE_UP = 'gave_up'


class BasicMathTraining(models.Model):
    """Basic Mathematics training session — one simple math question per chat.

    Each session holds A SINGLE quick-fire arithmetic question (addition,
    multiplication, fractions, percentages, ratio/average or mental math).
    Albert (the technical coach at TalentBro) sets the question and the
    student works through it inside one chat, replying with the answer and —
    where useful — the working they did. The session is locked as 'solved'
    (points awarded) or 'gave_up' (solution revealed) the moment the question
    is resolved, and the frontend immediately opens a fresh session for the
    next question — one question, one chat.

    The full chat lives in ``transcript`` (same {role, content, created_at}
    shape the other training models keep) and every gamification metric is
    stored on the row so history/reporting can derive XP, streaks and accuracy.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='basic_math_sessions',
    )
    title = models.CharField(max_length=255, blank=True, default='')
    category = models.CharField(
        max_length=40,
        choices=BASIC_MATH_CATEGORY_CHOICES,
        default='mental_math',
    )
    question = models.TextField(blank=True, default='')
    # Model-generated ground truth for the question (best-effort). Kept on the
    # row so the evaluator can score the student consistently and the give-up
    # path can always reveal the full step-by-step solution.
    answer = models.TextField(blank=True, default='')
    solution = models.TextField(blank=True, default='')
    transcript = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=12,
        choices=BASIC_MATH_STATUS_CHOICES,
        default=BASIC_MATH_STATUS_ACTIVE,
    )
    attempts = models.PositiveIntegerField(
        default=0,
        help_text='Number of tries the student made before resolving the question.',
    )
    hints_used = models.PositiveIntegerField(
        default=0,
        help_text='Number of hints Albert handed out during the attempt.',
    )
    points_awarded = models.PositiveIntegerField(
        default=0,
        help_text='XP earned for solving this question (0 when given up).',
    )
    star_rating = models.PositiveSmallIntegerField(
        default=0,
        help_text='Accuracy/speed quality shown by the student (1–5) when solved.',
    )
    solved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'basic_math'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title or "Basic math question"} ({self.get_status_display().lower()})'


SITUATIONAL_CATEGORY_CHOICES = [
    ('workplace_conflict', 'Workplace Conflict'),
    ('leadership_dilemma', 'Leadership Dilemma'),
    ('team_management', 'Team Management'),
    ('decision_making', 'Decision Making'),
    ('ethical_dilemma', 'Ethical Dilemma'),
    ('crisis_management', 'Crisis Management'),
]

SITUATIONAL_STATUS_CHOICES = [
    ('active', 'Active'),
    ('solved', 'Solved'),
    ('gave_up', 'Gave Up'),
]

SITUATIONAL_STATUS_ACTIVE = 'active'
SITUATIONAL_STATUS_SOLVED = 'solved'
SITUATIONAL_STATUS_GAVE_UP = 'gave_up'


class SituationalProblemSolvingTraining(models.Model):
    """Situational Problem Solving training session — one workplace scenario per chat.

    Each session holds A SINGLE management-style situational scenario (workplace
    conflict, leadership dilemma, team management, decision making, ethical
    dilemma or crisis management). Peter (the management coach at TalentBro)
    sets the scenario and the student works through it inside one chat,
    replying with their decision AND the reasoning behind it. The session is
    locked as 'solved' (points awarded) or 'gave_up' (approach revealed) the
    moment the question is resolved, and the frontend immediately opens a fresh
    session for the next scenario — one scenario, one chat.

    The full chat lives in ``transcript`` (same {role, content, created_at}
    shape the other training models keep) and every gamification metric is
    stored on the row so history/reporting can derive XP, streaks and accuracy.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='situational_sessions',
    )
    title = models.CharField(max_length=255, blank=True, default='')
    category = models.CharField(
        max_length=40,
        choices=SITUATIONAL_CATEGORY_CHOICES,
        default='decision_making',
    )
    question = models.TextField(blank=True, default='')
    # Model-generated ground truth for the scenario (best-effort). Kept on the
    # row so the evaluator can score the student consistently and the give-up
    # path can always reveal the model answer and reasoning.
    answer = models.TextField(blank=True, default='')
    solution = models.TextField(blank=True, default='')
    transcript = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=12,
        choices=SITUATIONAL_STATUS_CHOICES,
        default=SITUATIONAL_STATUS_ACTIVE,
    )
    attempts = models.PositiveIntegerField(
        default=0,
        help_text='Number of tries the student made before resolving the scenario.',
    )
    hints_used = models.PositiveIntegerField(
        default=0,
        help_text='Number of hints Peter handed out during the attempt.',
    )
    points_awarded = models.PositiveIntegerField(
        default=0,
        help_text='XP earned for solving this scenario (0 when given up).',
    )
    star_rating = models.PositiveSmallIntegerField(
        default=0,
        help_text='Management judgement quality shown by the student (1–5) when solved.',
    )
    solved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'situational_training'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title or "Situational scenario"} ({self.get_status_display().lower()})'


TECH_CATEGORY_CHOICES = [
    ('basics', 'Basics & Logic'),
    ('arrays_strings', 'Arrays & Strings'),
    ('searching_sorting', 'Searching & Sorting'),
    ('recursion', 'Recursion'),
    ('algorithms', 'Algorithms & Complexity'),
    ('debugging', 'Debugging'),
]

TECH_STATUS_CHOICES = [
    ('active', 'Active'),
    ('solved', 'Solved'),
    ('gave_up', 'Gave Up'),
]

TECH_STATUS_ACTIVE = 'active'
TECH_STATUS_SOLVED = 'solved'
TECH_STATUS_GAVE_UP = 'gave_up'


class TechnicalTraining(models.Model):
    """Technical / coding problem solving session — one coding question per chat.

    Each session holds A SINGLE placement-style technical or coding problem
    (logic basics, arrays & strings, searching & sorting, data structures,
    recursion, algorithms, or debugging). Albert (the technical architect at
    TalentBro) sets the problem and the student works through it inside one
    chat, replying with their solution, pseudocode or explanation AND the
    approach/logic they used. The session is locked as 'solved' (points
    awarded) or 'gave_up' (solution revealed) the moment the problem is
    resolved, and the frontend immediately opens a fresh session for the next
    problem — one problem, one chat.

    The full chat lives in ``transcript`` (same {role, content, created_at}
    shape the other training models keep) and every gamification metric is
    stored on the row so history/reporting can derive XP, streaks and accuracy.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='technical_sessions',
    )
    title = models.CharField(max_length=255, blank=True, default='')
    category = models.CharField(
        max_length=40,
        choices=TECH_CATEGORY_CHOICES,
        default='basics',
    )
    question = models.TextField(blank=True, default='')
    # Model-generated ground truth for the problem (best-effort). Kept on the
    # row so the evaluator can score the student consistently and the give-up
    # path can always reveal the full approach/code sketch.
    answer = models.TextField(blank=True, default='')
    solution = models.TextField(blank=True, default='')
    transcript = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=12,
        choices=TECH_STATUS_CHOICES,
        default=TECH_STATUS_ACTIVE,
    )
    attempts = models.PositiveIntegerField(
        default=0,
        help_text='Number of tries the student made before resolving the problem.',
    )
    hints_used = models.PositiveIntegerField(
        default=0,
        help_text='Number of hints Albert handed out during the attempt.',
    )
    points_awarded = models.PositiveIntegerField(
        default=0,
        help_text='XP earned for solving this problem (0 when given up).',
    )
    star_rating = models.PositiveSmallIntegerField(
        default=0,
        help_text='Logic/approach quality shown by the student (1–5) when solved.',
    )
    solved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'technical_training'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title or "Technical question"} ({self.get_status_display().lower()})'


DSA_CATEGORY_CHOICES = [
    ('arrays_strings', 'Arrays & Strings'),
    ('linked_lists', 'Linked Lists'),
    ('stacks_queues', 'Stacks & Queues'),
    ('hash_maps', 'Hash Maps & Sets'),
    ('trees', 'Trees'),
    ('graphs', 'Graphs'),
    ('searching_sorting', 'Searching & Sorting'),
    ('dynamic_programming', 'Dynamic Programming'),
]

DSA_STATUS_CHOICES = [
    ('active', 'Active'),
    ('solved', 'Solved'),
    ('gave_up', 'Gave Up'),
]

DSA_STATUS_ACTIVE = 'active'
DSA_STATUS_SOLVED = 'solved'
DSA_STATUS_GAVE_UP = 'gave_up'


class DSATraining(models.Model):
    """DSA (Data Structures & Algorithms) session — one classic problem per chat.

    Each session holds A SINGLE placement-style data-structures & algorithms
    problem (arrays & strings, linked lists, stacks & queues, hash maps, trees,
    graphs, searching & sorting, or dynamic programming). Albert (the technical
    architect at TalentBro) sets the problem and the student works it out inside
    one chat, replying with their solution, pseudocode or explanation AND the
    approach/logic they used. The session is locked as 'solved' (points
    awarded) or 'gave_up' (solution revealed) the moment the problem is
    resolved, and the frontend immediately opens a fresh session for the next
    problem — one problem, one chat.

    The full chat lives in ``transcript`` (same {role, content, created_at}
    shape the other training models keep) and every gamification metric is
    stored on the row so history/reporting can derive XP, streaks and accuracy.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='dsa_sessions',
    )
    title = models.CharField(max_length=255, blank=True, default='')
    category = models.CharField(
        max_length=40,
        choices=DSA_CATEGORY_CHOICES,
        default='arrays_strings',
    )
    question = models.TextField(blank=True, default='')
    # Model-generated ground truth for the problem (best-effort). Kept on the
    # row so the evaluator can score the student consistently and the give-up
    # path can always reveal the full approach/code sketch.
    answer = models.TextField(blank=True, default='')
    solution = models.TextField(blank=True, default='')
    transcript = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=12,
        choices=DSA_STATUS_CHOICES,
        default=DSA_STATUS_ACTIVE,
    )
    attempts = models.PositiveIntegerField(
        default=0,
        help_text='Number of tries the student made before resolving the problem.',
    )
    hints_used = models.PositiveIntegerField(
        default=0,
        help_text='Number of hints Albert handed out during the attempt.',
    )
    points_awarded = models.PositiveIntegerField(
        default=0,
        help_text='XP earned for solving this problem (0 when given up).',
    )
    star_rating = models.PositiveSmallIntegerField(
        default=0,
        help_text='Logic/approach quality shown by the student (1–5) when solved.',
    )
    solved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'dsa_training'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title or "DSA question"} ({self.get_status_display().lower()})'


MOCK_INTERVIEW_STATUS_CHOICES = [
    ('active', 'Active'),
    ('completed', 'Completed'),
]


class MockInterview(models.Model):
    """A student-run AI mock interview targeting a specific company."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='mock_interviews',
    )
    company_name = models.CharField(max_length=255)
    role = models.CharField(max_length=255, blank=True)
    questions = models.JSONField(default=list, blank=True)
    duration = models.CharField(max_length=20, blank=True, default='standard')
    panelists = models.JSONField(default=list, blank=True)
    panelist_response = models.JSONField(
        default=dict, blank=True,
        help_text='Per-panelist feedback after the interview completes. Keys are panelist IDs, values are their feedback text.',
    )
    suspection = models.IntegerField(
        default=0,
        help_text='Number of times the candidate looked away from the screen during the interview.',
    )
    status = models.CharField(
        max_length=20,
        choices=MOCK_INTERVIEW_STATUS_CHOICES,
        default='active',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.company_name} mock ({self.user.get_full_name() or self.user.username})'


MOCK_INTERVIEW_PANELIST_CHOICES = [
    ('atlas', 'Atlas (Integrity Monitor)'),
    ('maya', 'Maya (Communication & HR)'),
    ('albert', 'Albert (Technical Architect)'),
    ('peter', 'Peter (Management & Leadership)'),
    ('daniel', 'Daniel (Decision Science)'),
    ('ada', 'Ada (Analytical & Logical Thinking)'),
    ('carl', 'Carl (Behavioral Intelligence)'),
]


class MockInterviewMessage(models.Model):
    """A single question/answer turn inside a MockInterview."""

    interview = models.ForeignKey(
        MockInterview, on_delete=models.CASCADE, related_name='messages',
    )
    role = models.CharField(max_length=10, choices=CHAT_ROLE_CHOICES)
    panelist = models.CharField(
        max_length=20,
        choices=MOCK_INTERVIEW_PANELIST_CHOICES,
        blank=True,
        default='',
        help_text='Which panel member produced this message (assistant messages only).',
    )
    tone = models.CharField(
        max_length=10,
        blank=True,
        default='',
        help_text='Detected engagement/tone of the candidate\'s answer (positive, neutral, negative).',
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']

    def __str__(self):
        return f'{self.role}: {self.content[:40]}'


MOCK_INTERVIEW_ANALYSIS_DIMENSIONS = [
    ('communication_skills', 'Communication Skills', 'How clearly, fluently and persuasively the candidate communicates.'),
    ('confidence', 'Confidence', 'Self-assurance and poise while answering, without arrogance.'),
    ('knowledge_awareness', 'Knowledge & Awareness', 'General grasp of the domain, industry and role context.'),
    ('clarity_of_thought', 'Clarity of Thought', 'How well ideas are reasoned through and expressed coherently.'),
    ('analytical_problem_solving', 'Analytical & Problem-Solving Ability', 'Approach to breaking down and solving problems.'),
    ('personality_presence', 'Personality & Presence', 'Professional demeanour, warmth and likeability.'),
    ('attitude', 'Attitude', 'Positive, constructive and professional outlook during the interview.'),
    ('emotional_maturity', 'Emotional Maturity', 'Composure and maturity when challenged or under pressure.'),
    ('leadership_initiative', 'Leadership & Initiative', 'Signs of ownership, drive and leading others.'),
    ('teamwork_interpersonal_skills', 'Teamwork & Interpersonal Skills', 'Evidence of collaborating and relating with others.'),
    ('integrity_values', 'Integrity & Values', 'Honesty, authenticity and sound professional values.'),
    ('motivation_fit', 'Motivation & Fit', 'Demonstrated interest and alignment with the company and role.'),
    ('subject_knowledge', 'Subject Knowledge', 'Depth and correctness of technical or academic knowledge.'),
    ('general_awareness', 'General Awareness', 'Awareness of current events, market and the outside world.'),
    ('logical_reasoning', 'Logical Reasoning', 'Sound logic and reasoning in answers and follow-ups.'),
    ('curiosity', 'Curiosity', 'Genuine interest to learn, explore and ask good questions.'),
    ('creativity', 'Creativity', 'Originality and fresh thinking in responses.'),
    ('verbal_fluency', 'Verbal Fluency', 'Smooth, articulate and unhindered speaking ability.'),
    ('conciseness', 'Conciseness', 'Answering with the right amount of detail, without rambling.'),
    ('vocabulary', 'Vocabulary', 'Rich and appropriate use of language.'),
    ('listening', 'Listening', 'Carefully hearing and accurately responding to the actual question.'),
    ('ability_structure_answer', 'Ability to Structure an Answer', 'Organised, logical flow within each answer.'),
    ('ability_defend_opinion', 'Ability to Defend an Opinion', 'Holding and substantiating a position when challenged.'),
    ('energy', 'Energy', 'Vigour, enthusiasm and liveliness conveyed during the interview.'),
    ('adaptability', 'Adaptability', 'Flexibility and quick thinking when the interviewer shifts direction.'),
    ('self_awareness', 'Self-Awareness', 'Honest, specific understanding of strengths and weaknesses.'),
    ('empathy', 'Empathy', 'Consideration and understanding of others\' perspectives.'),
    ('conflict_management', 'Conflict Management', 'Handling disagreement or difficult situations constructively.'),
    ('respect_for_others', 'Respect for Others', 'Courtesy, attentiveness and respect toward the interviewers.'),
    ('ability_to_influence', 'Ability to Influence', 'Persuading others and having their point land.'),
    ('responsibility', 'Responsibility', 'Ownership and accountability for commitments and outcomes.'),
    ('discipline', 'Discipline', 'Consistency, preparation and follow-through.'),
    ('ambition', 'Ambition', 'Clear, credible career goals and drive to achieve them.'),
    ('learning_orientation', 'Learning Orientation', 'Humility and a clear appetite for continuous learning.'),
]


class MockInterviewAnalysis(models.Model):
    """Detailed AI-generated assessment of a completed mock interview.

    One analysis per interview, generated when the interview finishes. Every
    dimension in ``MOCK_INTERVIEW_ANALYSIS_DIMENSIONS`` gets its own percentage
    field (0–100) plus a matching ``<field>_desc`` field with the evidence-based
    explanation for that score. A per-interview SWOT analysis is also stored.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    interview = models.OneToOneField(
        MockInterview, on_delete=models.CASCADE, related_name='analysis',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='mock_analyses',
    )
    company_name = models.CharField(max_length=255, blank=True, default='')
    role = models.CharField(max_length=255, blank=True, default='')
    swot_strengths = models.TextField(
        blank=True, default='',
        help_text='Strengths identified from the interview transcript.',
    )
    swot_weaknesses = models.TextField(
        blank=True, default='',
        help_text='Weaknesses identified from the interview transcript.',
    )
    swot_opportunities = models.TextField(
        blank=True, default='',
        help_text='Opportunities identified from the interview transcript.',
    )
    swot_threats = models.TextField(
        blank=True, default='',
        help_text='Threats identified from the interview transcript.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'Analysis for {self.interview}'

    @property
    def metrics(self):
        """Per-dimension scores as [{dimension, percentage, description}, ...]."""
        return [
            {
                'dimension': name,
                'percentage': getattr(self, field),
                'description': getattr(self, f'{field}_desc'),
            }
            for field, name, _ in MOCK_INTERVIEW_ANALYSIS_DIMENSIONS
        ]

    @property
    def metric_count(self):
        return len(MOCK_INTERVIEW_ANALYSIS_DIMENSIONS)


for _dim_field, _dim_name, _dim_definition in MOCK_INTERVIEW_ANALYSIS_DIMENSIONS:
    MockInterviewAnalysis.add_to_class(
        _dim_field,
        models.PositiveSmallIntegerField(
            default=0,
            help_text=f'{_dim_name} score as a percentage (0–100).',
        ),
    )
    MockInterviewAnalysis.add_to_class(
        f'{_dim_field}_desc',
        models.TextField(
            blank=True, default='',
            help_text=f'Evidence-based description explaining the {_dim_name} score for this candidate.',
        ),
    )


class CommunicationTraining(models.Model):
    """A student's communication-training session with Maya.

    Stores the full chat transcription (the same user/assistant turns a
    ChatSession holds) together with Maya's per-session speech analysis:
    delivery metrics, counts and narrative feedback. This mirrors
    ChatSession/ChatMessage for the transcript but keeps the analysis in one
    place, as a fresh record per session.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='communication_training_sessions',
    )
    title = models.CharField(max_length=255, blank=True, default='')
    # Conversation history as [{role, content, created_at}, ...] — same shape
    # ChatMessage rows would produce, kept inline so the whole session is one row.
    transcript = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[('active', 'Active'), ('completed', 'Completed')],
        default='active',
    )
    finalized_at = models.DateTimeField(
        null=True, blank=True,
        help_text='When the session ended and the transcript was locked so the analysis could be generated.',
    )

    clarity = models.PositiveSmallIntegerField(default=0, help_text='Clarity score (0–100).')
    fluency = models.PositiveSmallIntegerField(default=0, help_text='Fluency score (0–100).')
    grammar = models.PositiveSmallIntegerField(default=0, help_text='Grammar score (0–100).')
    vocabulary = models.PositiveSmallIntegerField(default=0, help_text='Vocabulary score (0–100).')
    pronunciation = models.PositiveSmallIntegerField(default=0, help_text='Pronunciation score (0–100).')
    confidence = models.PositiveSmallIntegerField(default=0, help_text='Confidence score (0–100).')
    answer_structure = models.PositiveSmallIntegerField(default=0, help_text='Answer Structure score (0–100).')
    relevance = models.PositiveSmallIntegerField(default=0, help_text='Relevance score (0–100).')
    speaking_rate = models.PositiveSmallIntegerField(default=0, help_text='Speaking Rate score (0–100).')
    pause_frequency = models.PositiveSmallIntegerField(default=0, help_text='Pause Frequency score (0–100).')
    average_pause_duration = models.FloatField(
        default=0.0,
        help_text='Average pause duration in seconds.',
    )
    filler_words = models.PositiveIntegerField(default=0, help_text='Count of filler words (uh, um, like, you know...).')
    repeated_words = models.PositiveIntegerField(default=0, help_text='Count of repeated words/phrases.')
    sentence_restarts = models.PositiveIntegerField(default=0, help_text='Count of sentence restarts.')
    intonation = models.PositiveSmallIntegerField(default=0, help_text='Intonation score (0–100).')
    speech_rhythm = models.PositiveSmallIntegerField(default=0, help_text='Speech Rhythm score (0–100).')
    voice_modulation = models.PositiveSmallIntegerField(default=0, help_text='Voice Modulation score (0–100).')
    listening_skills = models.PositiveSmallIntegerField(default=0, help_text='Listening Skills score (0–100).')
    response_quality = models.PositiveSmallIntegerField(default=0, help_text='Response Quality score (0–100).')
    professional_tone = models.PositiveSmallIntegerField(default=0, help_text='Professional Tone score (0–100).')
    conversational_skills = models.PositiveSmallIntegerField(default=0, help_text='Conversational Skills score (0–100).')
    vocabulary_diversity = models.PositiveSmallIntegerField(default=0, help_text='Vocabulary Diversity score (0–100).')
    grammar_error_count = models.PositiveIntegerField(default=0, help_text='Number of grammar errors detected (0–100).')
    pronunciation_accuracy = models.PositiveSmallIntegerField(default=0, help_text='Pronunciation Accuracy score (0–100).')
    communication_score = models.PositiveSmallIntegerField(default=0, help_text='Overall Communication Score (0–100).')
    workplace_communication_readiness = models.PositiveSmallIntegerField(default=0, help_text='Workplace Communication Readiness score (0–100).')
    interview_readiness = models.PositiveSmallIntegerField(default=0, help_text='Interview Readiness score (0–100).')
    improvement_rate = models.PositiveSmallIntegerField(default=0, help_text='Improvement Rate (0–100 or %).')

    recurring_mistakes = models.TextField(blank=True, default='')
    strengths = models.TextField(blank=True, default='')
    areas_for_improvement = models.TextField(blank=True, default='')
    ai_recommendations = models.TextField(blank=True, default='')
    practice_priorities = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'Communication training ({self.user.get_full_name() or self.user.username})'


class EnglishTraining(models.Model):
    """A student's single, lifelong English writing practice record.

    Unlike CommunicationTraining (one row per session), this is exactly ONE row
    per student: the typed conversation transcript plus Maya's cumulative
    corporate-writing scores live together and keep updating in place as the
    student practises — there are no sessions inside it.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='english_training',
        help_text='One English training record per user.',
    )
    # Conversation history as [{role, content, created_at}, ...] — the whole
    # practice so far, kept trimmed to the most recent turns to bound growth.
    transcript = models.JSONField(default=list, blank=True)

    clarity = models.PositiveSmallIntegerField(default=0, help_text='Clarity of the message score (0–100).')
    structure = models.PositiveSmallIntegerField(default=0, help_text='Structure and organisation score (0–100).')
    grammar = models.PositiveSmallIntegerField(default=0, help_text='Grammar score (0–100).')
    vocabulary = models.PositiveSmallIntegerField(default=0, help_text='Vocabulary and word choice score (0–100).')
    spelling = models.PositiveSmallIntegerField(default=0, help_text='Spelling and punctuation score (0–100).')
    conciseness = models.PositiveSmallIntegerField(default=0, help_text='Conciseness score (0–100).')
    task_focus = models.PositiveSmallIntegerField(default=0, help_text='Task focus and format score (0–100).')
    professional_tone = models.PositiveSmallIntegerField(default=0, help_text='Professional tone score (0–100).')
    writing_score = models.PositiveSmallIntegerField(default=0, help_text='Overall English writing score (0–100).')

    recurring_mistakes = models.TextField(blank=True, default='')
    strengths = models.TextField(blank=True, default='')
    areas_for_improvement = models.TextField(blank=True, default='')
    ai_recommendations = models.TextField(blank=True, default='')

    practice_count = models.PositiveIntegerField(
        default=0,
        help_text='Number of practice rounds finished (recomputed on each finalize).',
    )
    last_practiced_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'english_training'

    def __str__(self):
        return f'English writing training ({self.user.get_full_name() or self.user.username})'


class EnglishTrainingSession(models.Model):
    """One English writing practice session with Maya (a fresh row per session).

    Mirrors CommunicationTraining: the typed transcript of this session, the
    per-session corporate-writing scores Maya computed at finalize, narrative
    feedback, and a structured ``mistakes`` list that points each mistake back
    to the exact user turn it appeared in, alongside the corrected phrasing and
    why it is better. :model:`EnglishTraining` (the OneToOne summary) stays in
    sync with the latest session so the chat header and placement profile
    refresh still work.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='english_training_sessions',
    )
    title = models.CharField(max_length=255, blank=True, default='')
    # Conversation history as [{role, content, created_at}, ...] — this session only.
    transcript = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[('active', 'Active'), ('completed', 'Completed')],
        default='active',
    )
    finalized_at = models.DateTimeField(
        null=True, blank=True,
        help_text='When this session ended and its transcript was locked so the analysis could be generated.',
    )

    clarity = models.PositiveSmallIntegerField(default=0, help_text='Clarity of the message score (0–100).')
    structure = models.PositiveSmallIntegerField(default=0, help_text='Structure and organisation score (0–100).')
    grammar = models.PositiveSmallIntegerField(default=0, help_text='Grammar score (0–100).')
    vocabulary = models.PositiveSmallIntegerField(default=0, help_text='Vocabulary and word choice score (0–100).')
    spelling = models.PositiveSmallIntegerField(default=0, help_text='Spelling and punctuation score (0–100).')
    conciseness = models.PositiveSmallIntegerField(default=0, help_text='Conciseness score (0–100).')
    task_focus = models.PositiveSmallIntegerField(default=0, help_text='Task focus and format score (0–100).')
    professional_tone = models.PositiveSmallIntegerField(default=0, help_text='Professional tone score (0–100).')
    writing_score = models.PositiveSmallIntegerField(default=0, help_text='Overall English writing score (0–100).')

    # Structured, machine-readable mistake list so the report page can show
    # EXACTLY where each mistake was (which user turn) and how to fix it.
    # Each entry: {"turn_index": int (index into user turns), "category": str,
    # "original": str, "corrected": str, "explanation": str}.
    mistakes = models.JSONField(default=list, blank=True)

    recurring_mistakes = models.TextField(blank=True, default='')
    strengths = models.TextField(blank=True, default='')
    areas_for_improvement = models.TextField(blank=True, default='')
    ai_recommendations = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'english_training_session'
        ordering = ['-created_at']

    def __str__(self):
        return f'English writing session ({self.user.get_full_name() or self.user.username})'


NOTIFICATION_SENDER_CHOICES = [
    ('placement_cell', 'Placement Cell'),
    ('platform', 'TalentBro Platform'),
]

NOTIFICATION_SENDER_PLACEMENT_CELL = 'placement_cell'
NOTIFICATION_SENDER_PLATFORM = 'platform'


class Notification(models.Model):
    """A broadcast message pushed to students by an institution's placement
    cell or by the TalentBro platform itself.

    Only placement-cell staff and platform administrators may create these;
    students only read them. Per-student read state lives in
    NotificationReceipt (created lazily the first time a student updates it).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sender = models.CharField(max_length=30, choices=NOTIFICATION_SENDER_CHOICES)
    # The account that pushed the broadcast. Platform broadcasts are created by
    # superusers/staff; placement-cell broadcasts by institution staff whose
    # linked Institution is stored in ``institution``. Auto-generated score
    # reports leave this empty (the platform/system pushes them).
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='notifications_created',
    )
    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='notifications',
        help_text='Scopes a placement-cell broadcast to this institution\'s students. Unset for platform broadcasts.',
    )
    # Personal notices (e.g. the per-user score report TalentBro sends after a
    # mock interview or self-training module completes) target exactly one user
    # and are only ever listed for that recipient. Broadcasts leave this empty.
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='personal_notifications',
        help_text='When set, this notice is delivered only to this user. Broadcasts leave it unset.',
    )
    # Frontend route to open when the student taps the notification, e.g.
    # /interview-analysis/<id> for a mock interview score or
    # /communication-training-report/<id> for a self-training module score.
    redirect_path = models.CharField(
        max_length=500, blank=True, default='',
        help_text='Frontend route to open when the user taps the notification.',
    )
    # Stable unique key (e.g. "mock_interview:<id>") so repeated completion
    # events — idempotent finalizers, keepalive retries, lazy analysis reads —
    # can never duplicate the same report. Broadcasts leave this empty.
    dedupe_key = models.CharField(
        max_length=255, null=True, blank=True, unique=True,
        help_text='Stable unique key so repeated completion events create only one notification.',
    )
    title = models.CharField(max_length=255)
    body = models.TextField()
    pinned = models.BooleanField(default=False)
    important = models.BooleanField(default=False)
    active = models.BooleanField(
        default=True,
        help_text='Soft-delete flag: inactive broadcasts are hidden from students.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_sender_display()}: {self.title}'

    def clean(self):
        super().clean()
        if self.sender == NOTIFICATION_SENDER_PLACEMENT_CELL and not self.institution_id:
            raise ValidationError(
                {'institution': 'A placement-cell broadcast must be scoped to an institution.'}
            )
        if self.sender == NOTIFICATION_SENDER_PLATFORM and self.institution_id:
            raise ValidationError(
                {'institution': 'A platform broadcast cannot be scoped to an institution.'}
            )


class NotificationReceipt(models.Model):
    """Per-student read marker for a Notification.

    Rows are created lazily — only when a student actually marks a notification
    read (or marks the whole inbox). A notification with no receipt for a user
    is treated as unread for that user.
    """

    notification = models.ForeignKey(
        Notification, on_delete=models.CASCADE, related_name='receipts',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_receipts',
    )
    read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('notification', 'user')
        ordering = ['-read_at']

    def __str__(self):
        return f'{self.user} -> {self.notification} ({"read" if self.read else "unread"})'


class ProfileUpdateSummary(models.Model):
    """JSON summary of profile facts learned during a mock interview or
    self-training session, plus the profile fields that were updated from it.

    Generated for the candidate whenever a session completes (mock interview
    finished, communication/English training finalised, a question is resolved,
    etc.) so that anything the candidate says that enriches their profile (new
    skill, project, certification, preferred role/location, CTC expectation...)
    is captured and applied to their CandidateProfile. One row per
    (user, source, source_id) — re-running is idempotent and updates the row in
    place.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile_update_summaries',
    )
    # Feature that produced the summary, e.g. mock_interview, communication,
    # english, aplr, basic_math, situational, technical, dsa.
    source = models.CharField(max_length=40)
    # PK of the session/record the summary was generated from.
    source_id = models.CharField(max_length=64)
    summary = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'source', 'source_id')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.source} summary for {self.user.get_full_name() or self.user.username}'


GD_STATUS_CHOICES = [
    ('active', 'Active'),
    ('completed', 'Completed'),
]

GD_STATUS_ACTIVE = 'active'
GD_STATUS_COMPLETED = 'completed'

GD_PHASE_CHOICES = [
    ('intro', 'Introductions'),
    ('discussion', 'Discussion'),
    ('completed', 'Completed'),
]

GD_PHASE_DISCUSSION = 'discussion'
GD_PHASE_COMPLETED = 'completed'

# The eight dimensions a campus GD is judged on. Each gets its own 0-100 column
# so a completed round can be interpreted and reported on directly.
GD_CRITERIA = [
    ('content_quality', 'Content Quality'),
    ('reasoning', 'Reasoning'),
    ('communication', 'Communication'),
    ('confidence', 'Confidence'),
    ('teamwork', 'Teamwork'),
    ('initiative', 'Initiative'),
    ('active_listening', 'Active Listening'),
    ('build_challenge', 'Build / Challenge'),
]

GD_CRITERIA_FIELDS = [slug for slug, _ in GD_CRITERIA]


class GdTraining(models.Model):
    """A single student-run group discussion training round.

    Every GD round is stored as one row: the topic Gemini picked from recent
    current affairs, the members present (the student + AI panelists), the full
    transcript, plus the student's performance-metric columns and AI analysis
    so each round can be interpreted after the discussion ends.
    """

    # Pool of AI panelist names used to build the 6 + 1 GD roster
    # (3 random Indian women + 3 random Indian men + the student).
    GD_FEMALE_PANELISTS = [
        'Aanya', 'Aditi', 'Ananya', 'Diya', 'Ishita', 'Kavya', 'Meera',
        'Nisha', 'Pooja', 'Priya', 'Riya', 'Shreya', 'Tanvi', 'Vaishnavi',
    ]
    GD_MALE_PANELISTS = [
        'Aarav', 'Aditya', 'Arjun', 'Dev', 'Harsh', 'Ishaan', 'Kabir',
        'Karan', 'Pranav', 'Rahul', 'Rohan', 'Siddharth', 'Tarun', 'Vivaan',
    ]

    @classmethod
    def random_participants(cls, user):
        """Build the 7-member roster: 3 random Indian women, 3 random Indian
        men, and the student (is_user=True) that owns the round."""
        women = [
            {'name': name, 'gender': 'female', 'is_user': False}
            for name in random.sample(cls.GD_FEMALE_PANELISTS, 3)
        ]
        men = [
            {'name': name, 'gender': 'male', 'is_user': False}
            for name in random.sample(cls.GD_MALE_PANELISTS, 3)
        ]
        return women + men + [
            {
                'name': user.get_full_name() or user.username,
                'gender': '',
                'is_user': True,
            }
        ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='gd_sessions',
    )
    title = models.CharField(max_length=255, blank=True, default='')
    # The GD topic picked by Gemini from recent current affairs.
    topic = models.TextField(blank=True, default='')
    # Members of the discussion: the student (is_user=True) plus AI panelists.
    # Each entry is {name, gender, is_user}.
    participants = models.JSONField(default=list, blank=True)
    # Conversation history as [{role, speaker, gender, content, created_at}, ...].
    transcript = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=20,
        choices=GD_STATUS_CHOICES,
        default=GD_STATUS_ACTIVE,
    )
    phase = models.CharField(
        max_length=20,
        choices=GD_PHASE_CHOICES,
        default=GD_PHASE_DISCUSSION,
    )
    duration_minutes = models.PositiveIntegerField(
        default=15,
        help_text='How long the discussion is meant to run before it auto-ends.',
    )
    ended_at = models.DateTimeField(null=True, blank=True)

    # ------------------------------------------------------------------
    # User analysis + performance metrics (0-100 each) for this round.
    # ------------------------------------------------------------------
    content_quality = models.PositiveSmallIntegerField(default=0, help_text='Content Quality score (0-100).')
    reasoning = models.PositiveSmallIntegerField(default=0, help_text='Reasoning score (0-100).')
    communication = models.PositiveSmallIntegerField(default=0, help_text='Communication score (0-100).')
    confidence = models.PositiveSmallIntegerField(default=0, help_text='Confidence score (0-100).')
    teamwork = models.PositiveSmallIntegerField(default=0, help_text='Teamwork score (0-100).')
    initiative = models.PositiveSmallIntegerField(default=0, help_text='Initiative score (0-100).')
    active_listening = models.PositiveSmallIntegerField(default=0, help_text='Active Listening score (0-100).')
    build_challenge = models.PositiveSmallIntegerField(default=0, help_text='Build / Challenge score (0-100).')
    overall_score = models.PositiveSmallIntegerField(default=0, help_text='Overall GD score (0-100).')
    grade = models.CharField(max_length=10, blank=True, default='', help_text='Overall grade (Excellent, Good, Average, Poor).')
    overall_summary = models.TextField(blank=True, default='', help_text='AI narrative summary of the student\'s performance.')
    strengths = models.JSONField(default=list, blank=True)
    improvement_areas = models.JSONField(default=list, blank=True)
    # Per-member breakdown: [{name, gender, is_user, <criterion>: <0-100>, score, summary}].
    evaluations = models.JSONField(default=list, blank=True)
    # Full analysis payload including strengths/improvement areas/criteria.
    assessment = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'gd_training'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.topic[:60] or self.title or "GD round"} ({self.user.get_full_name() or self.user.username})'
