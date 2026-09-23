from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.contrib.auth.models import User

from .models import (
    APLRTraining,
    BasicMathTraining,
    CandidateProfile,
    ChatMessage,
    ChatSession,
    ClientProfile,
    CommunicationTraining,
    Company,
    EnglishTraining,
    EnglishTrainingSession,
    GdTraining,
    Institution,
    MockInterview,
    MOCK_INTERVIEW_ANALYSIS_DIMENSIONS,
    MockInterviewAnalysis,
    MockInterviewMessage,
    Notification,
    NotificationReceipt,
    SituationalProblemSolvingTraining,
    TechnicalTraining,
    DSATraining,
)

admin.site.site_header = "TalentBro Institutions"
admin.site.site_title = "TalentBro Institutions"
admin.site.index_title = "TalentBro Institutions Administration Panel for Management"

admin.site.unregister(User)


class TalentBroUserForm(UserChangeForm):
    """Change form for a user (role is derived, not editable here)."""

    class Meta(UserChangeForm.Meta):
        model = User
        fields = '__all__'


class TalentBroUserCreationForm(UserCreationForm):
    """Add form for a new user."""

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name')


@admin.register(User)
class TalentBroUserAdmin(UserAdmin):
    """Django admin view of every account — students and institution staff."""

    form = TalentBroUserForm
    add_form = TalentBroUserCreationForm
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'first_name', 'last_name',
                       'password1', 'password2'),
        }),
    )
    readonly_fields = ('date_joined', 'last_login')

    list_display = (
        'email',
        'display_name',
        'is_active',
        'is_staff',
        'last_login',
        'date_joined',
    )
    list_filter = ('is_active', 'is_staff', 'is_superuser')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    actions = ('activate_users', 'deactivate_users')

    @admin.display(description='Name')
    def display_name(self, obj):
        return obj.get_full_name() or obj.username

    @admin.action(description='Activate selected users')
    def activate_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} user(s) activated.')

    @admin.action(description='Deactivate selected users')
    def deactivate_users(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} user(s) deactivated.')


@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'institution_type',
        'city',
        'state',
        'placement_department_name',
    )
    list_filter = ('institution_type', 'state')
    search_fields = ('name', 'email_domain', 'placement_office_email')
    fieldsets = (
        ('Institution', {
            'fields': (
                'user',
                'name',
                'institution_type',
                'website',
                'email_domain',
                'address',
                'city',
                'state',
                'pin_code',
                'logo',
            ),
        }),
        ('Placement Cell', {
            'fields': (
                'placement_department_name',
                'placement_office_email',
                'approximate_student_strength',
                'courses_offered',
                'departments',
                'companies',
            ),
        }),
    )


class CompanyInline(admin.TabularInline):
    model = Company
    extra = 0
    fields = ('company_name', 'industry', 'recruitment_status', 'offer_status')
    readonly_fields = ('company_id',)


@admin.register(ClientProfile)
class ClientProfileAdmin(admin.ModelAdmin):
    list_display = (
        'full_name',
        'official_email',
        'designation',
        'institution',
        'access',
    )
    list_filter = ('access', 'institution')
    search_fields = (
        'full_name',
        'official_email',
        'employee_staff_id',
        'institution__name',
    )
    autocomplete_fields = ('user', 'institution')
    fieldsets = (
        ('Person', {
            'fields': (
                'user',
                'institution',
                'full_name',
                'official_email',
                'mobile_number',
                'designation',
                'employee_staff_id',
            ),
        }),
        ('Access', {
            'fields': (
                'access',
            ),
            'description': (
                'Beta = read-only access to the institution dashboard. '
                'Master = can create drives and edit data.'
            ),
        }),
    )
    inlines = (CompanyInline,)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = (
        'company_id',
        'company_name',
        'industry',
        'institution',
        'client',
        'recruitment_status',
        'placement_mode',
        'offer_status',
        'campus_visit_date',
    )
    list_filter = (
        'industry',
        'work_mode',
        'recruitment_status',
        'placement_mode',
        'offer_status',
        'institution',
    )
    search_fields = (
        'company_id',
        'company_name',
        'industry',
        'work_location',
        'institution__name',
        'client__full_name',
    )
    autocomplete_fields = ('institution', 'client')
    readonly_fields = ('company_id', 'created_at', 'updated_at')
    fieldsets = (
        ('Identity', {
            'fields': (
                'company_id',
                'company_name',
                'industry',
                'company_description',
            ),
        }),
        ('Drive Details', {
            'fields': (
                'institution',
                'client',
                'job_roles',
                'number_of_openings',
                'work_location',
                'work_mode',
                'salary_min',
                'salary_max',
                'graduation_year',
            ),
        }),
        ('Eligibility', {
            'fields': (
                'eligible_courses',
                'eligible_branches',
                'minimum_cgpa',
                'maximum_backlogs',
                'required_skills',
                'preferred_skills',
            ),
        }),
        ('Schedule', {
            'fields': (
                'application_deadline',
                'campus_visit_date',
                'selection_rounds',
                'recruitment_status',
                'placement_mode',
                'offer_status',
            ),
        }),
        ('Meta', {
            'fields': ('created_at', 'updated_at'),
        }),
    )


@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
    list_display = (
        'candidate_id',
        'first_name',
        'middle_name',
        'last_name',
        'college',
        'program',
        'start_year',
        'end_year',
        'id_verified',
        'cost_incurred',
        'time_spent',
    )
    list_filter = (
        'college',
        'program',
        'start_year',
        'end_year',
        'gender',
        'account_status',
        'id_verified',
    )
    search_fields = (
        'candidate_id',
        'first_name',
        'middle_name',
        'last_name',
        'mobile_number',
        'college__name',
        'user__email',
        'user__first_name',
        'user__last_name',
    )
    autocomplete_fields = ('user', 'college')
    fieldsets = (
        ('Identity', {
            'fields': (
                'candidate_id',
                'user',
                'first_name',
                'middle_name',
                'last_name',
                'college',
                'department',
                'program',
                'start_year',
                'end_year',
            ),
        }),
        ('Contact', {
            'fields': (
                'mobile_number',
                'date_of_birth',
                'gender',
                'cgpa',
            ),
        }),
        ('Placement', {
            'fields': (
                'linkedin_url',
                'github_url',
                'portfolio_url',
            ),
        }),
        ('Experience & Profile', {
            'fields': (
                'skills',
                'certifications',
                'projects',
                'internships',
            ),
        }),
        ('Preferences', {
            'fields': (
                'preferred_roles',
                'preferred_locations',
                'preferred_language',
                'expected_ctc',
            ),
        }),
        ('Account', {
            'fields': (
                'account_status',
                'last_login_at',
                'time_spent',
            ),
            'description': (
                'time_spent is the cumulative active platform time in minutes. '
                'The frontend adds to it automatically; edit to correct.'
            ),
        }),
        ('AI Usage', {
            'fields': (
                'cost_incurred',
            ),
            'description': (
                'Total Gemini cost incurred by this candidate in INR '
                '(including 40% markup). Updated automatically by embeddings.'
            ),
        }),
    )
    readonly_fields = ('candidate_id', 'last_login_at', 'cost_incurred')


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ('role', 'content', 'created_at')
    can_delete = True


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ('title', 'user_name', 'message_count', 'created_at', 'updated_at')
    search_fields = ('title', 'user__email', 'user__first_name', 'user__last_name')
    autocomplete_fields = ('user',)
    readonly_fields = ('id', 'created_at', 'updated_at', 'message_count')
    inlines = (ChatMessageInline,)

    @admin.display(description='User')
    def user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username

    @admin.display(description='Messages')
    def message_count(self, obj):
        return obj.messages.count()


class MockInterviewMessageInline(admin.TabularInline):
    model = MockInterviewMessage
    extra = 0
    readonly_fields = ('role', 'content', 'created_at')
    can_delete = True


@admin.register(MockInterview)
class MockInterviewAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'user_name', 'role', 'status', 'message_count', 'updated_at')
    list_filter = ('status',)
    search_fields = ('company_name', 'role', 'user__email', 'user__first_name', 'user__last_name')
    autocomplete_fields = ('user',)
    readonly_fields = ('id', 'created_at', 'updated_at', 'message_count')
    inlines = (MockInterviewMessageInline,)

    @admin.display(description='User')
    def user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username

    @admin.display(description='Messages')
    def message_count(self, obj):
        return obj.messages.count()


@admin.register(MockInterviewAnalysis)
class MockInterviewAnalysisAdmin(admin.ModelAdmin):
    list_display = (
        'company_name',
        'user_name',
        'role',
        'metric_count',
        'updated_at',
    )
    list_filter = ('interview__status',)
    search_fields = (
        'company_name',
        'role',
        'swot_strengths',
        'swot_weaknesses',
        'swot_opportunities',
        'swot_threats',
        'user__email',
        'user__first_name',
        'user__last_name',
    )
    autocomplete_fields = ('user', 'interview')
    readonly_fields = ('id', 'created_at', 'updated_at', 'metric_count')
    fieldsets = (
        ('Interview', {
            'fields': ('interview', 'user', 'company_name', 'role'),
        }),
        ('SWOT Analysis', {
            'fields': ('swot_strengths', 'swot_weaknesses', 'swot_opportunities', 'swot_threats'),
        }),
        *(
            (dimension_name, {'fields': (metric_field, f'{metric_field}_desc')})
            for metric_field, dimension_name, _ in MOCK_INTERVIEW_ANALYSIS_DIMENSIONS
        ),
        ('Meta', {
            'fields': ('id', 'metric_count', 'created_at', 'updated_at'),
        }),
    )

    @admin.display(description='User')
    def user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username


@admin.register(APLRTraining)
class APLRTrainingAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'user_name',
        'category',
        'status',
        'points_awarded',
        'star_rating',
        'updated_at',
    )
    list_filter = ('status', 'category')
    search_fields = ('title', 'question', 'user__email', 'user__first_name', 'user__last_name')
    autocomplete_fields = ('user',)
    readonly_fields = ('id', 'created_at', 'updated_at', 'solved_at')
    fieldsets = (
        ('Session', {
            'fields': ('id', 'user', 'title', 'category', 'status'),
        }),
        ('Question', {
            'fields': ('question', 'answer', 'solution'),
        }),
        ('Transcript', {
            'fields': ('transcript',),
        }),
        ('Gamification', {
            'fields': ('attempts', 'hints_used', 'points_awarded', 'star_rating'),
        }),
        ('Meta', {
            'fields': ('solved_at', 'created_at', 'updated_at'),
        }),
    )

    @admin.display(description='User')
    def user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username


@admin.register(BasicMathTraining)
class BasicMathTrainingAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'user_name',
        'category',
        'status',
        'points_awarded',
        'star_rating',
        'updated_at',
    )
    list_filter = ('status', 'category')
    search_fields = ('title', 'question', 'user__email', 'user__first_name', 'user__last_name')
    autocomplete_fields = ('user',)
    readonly_fields = ('id', 'created_at', 'updated_at', 'solved_at')
    fieldsets = (
        ('Session', {
            'fields': ('id', 'user', 'title', 'category', 'status'),
        }),
        ('Question', {
            'fields': ('question', 'answer', 'solution'),
        }),
        ('Transcript', {
            'fields': ('transcript',),
        }),
        ('Gamification', {
            'fields': ('attempts', 'hints_used', 'points_awarded', 'star_rating'),
        }),
        ('Meta', {
            'fields': ('solved_at', 'created_at', 'updated_at'),
        }),
    )

    @admin.display(description='User')
    def user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username


@admin.register(TechnicalTraining)
class TechnicalTrainingAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'user_name',
        'category',
        'status',
        'points_awarded',
        'star_rating',
        'updated_at',
    )
    list_filter = ('status', 'category')
    search_fields = ('title', 'question', 'user__email', 'user__first_name', 'user__last_name')
    autocomplete_fields = ('user',)
    readonly_fields = ('id', 'created_at', 'updated_at', 'solved_at')
    fieldsets = (
        ('Session', {
            'fields': ('id', 'user', 'title', 'category', 'status'),
        }),
        ('Problem', {
            'fields': ('question', 'answer', 'solution'),
        }),
        ('Transcript', {
            'fields': ('transcript',),
        }),
        ('Gamification', {
            'fields': ('attempts', 'hints_used', 'points_awarded', 'star_rating'),
        }),
        ('Meta', {
            'fields': ('solved_at', 'created_at', 'updated_at'),
        }),
    )

    @admin.display(description='User')
    def user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username


@admin.register(DSATraining)
class DSATrainingAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'user_name',
        'category',
        'status',
        'points_awarded',
        'star_rating',
        'updated_at',
    )
    list_filter = ('status', 'category')
    search_fields = ('title', 'question', 'user__email', 'user__first_name', 'user__last_name')
    autocomplete_fields = ('user',)
    readonly_fields = ('id', 'created_at', 'updated_at', 'solved_at')
    fieldsets = (
        ('Session', {
            'fields': ('id', 'user', 'title', 'category', 'status'),
        }),
        ('Problem', {
            'fields': ('question', 'answer', 'solution'),
        }),
        ('Transcript', {
            'fields': ('transcript',),
        }),
        ('Gamification', {
            'fields': ('attempts', 'hints_used', 'points_awarded', 'star_rating'),
        }),
        ('Meta', {
            'fields': ('solved_at', 'created_at', 'updated_at'),
        }),
    )

    @admin.display(description='User')
    def user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username


@admin.register(SituationalProblemSolvingTraining)
class SituationalProblemSolvingTrainingAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'user_name',
        'category',
        'status',
        'points_awarded',
        'star_rating',
        'updated_at',
    )
    list_filter = ('status', 'category')
    search_fields = ('title', 'question', 'user__email', 'user__first_name', 'user__last_name')
    autocomplete_fields = ('user',)
    readonly_fields = ('id', 'created_at', 'updated_at', 'solved_at')
    fieldsets = (
        ('Session', {
            'fields': ('id', 'user', 'title', 'category', 'status'),
        }),
        ('Scenario', {
            'fields': ('question', 'answer', 'solution'),
        }),
        ('Transcript', {
            'fields': ('transcript',),
        }),
        ('Gamification', {
            'fields': ('attempts', 'hints_used', 'points_awarded', 'star_rating'),
        }),
        ('Meta', {
            'fields': ('solved_at', 'created_at', 'updated_at'),
        }),
    )

    @admin.display(description='User')
    def user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username


@admin.register(CommunicationTraining)
class CommunicationTrainingAdmin(admin.ModelAdmin):
    list_display = (
        'title_display',
        'user_name',
        'status',
        'communication_score',
        'updated_at',
    )
    search_fields = ('title', 'user__email', 'user__first_name', 'user__last_name')
    autocomplete_fields = ('user',)
    readonly_fields = ('id', 'created_at', 'updated_at', 'finalized_at')

    fieldsets = (
        ('Session', {
            'fields': ('id', 'user', 'title'),
        }),
        ('Transcript', {
            'fields': ('transcript',),
        }),
        ('Delivery Scores (0–100)', {
            'fields': (
                'clarity', 'fluency', 'grammar', 'vocabulary', 'pronunciation',
                'confidence', 'answer_structure', 'relevance', 'speaking_rate',
                'intonation', 'speech_rhythm', 'voice_modulation',
            ),
        }),
        ('Speech Metrics', {
            'fields': (
                'pause_frequency', 'average_pause_duration', 'filler_words',
                'repeated_words', 'sentence_restarts', 'grammar_error_count',
            ),
        }),
        ('Advanced Scores (0–100)', {
            'fields': (
                'listening_skills', 'response_quality', 'professional_tone',
                'conversational_skills', 'vocabulary_diversity',
                'pronunciation_accuracy', 'communication_score',
                'workplace_communication_readiness', 'interview_readiness',
                'improvement_rate',
            ),
        }),
        ('Narrative Feedback', {
            'fields': (
                'recurring_mistakes', 'strengths', 'areas_for_improvement',
                'ai_recommendations', 'practice_priorities',
            ),
        }),
        ('Meta', {
            'fields': ('status', 'finalized_at', 'created_at', 'updated_at'),
        }),
    )

    @admin.display(description='Title')
    def title_display(self, obj):
        return obj.title or '(untitled session)'

    @admin.display(description='User')
    def user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username


@admin.register(EnglishTraining)
class EnglishTrainingAdmin(admin.ModelAdmin):
    list_display = (
        'user_name',
        'writing_score',
        'practice_count',
        'last_practiced_at',
        'updated_at',
    )
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    autocomplete_fields = ('user',)
    readonly_fields = ('id', 'created_at', 'updated_at', 'last_practiced_at')

    fieldsets = (
        ('Student', {
            'fields': ('id', 'user', 'practice_count', 'last_practiced_at'),
        }),
        ('Transcript', {
            'fields': ('transcript',),
        }),
        ('Writing Scores (0–100)', {
            'fields': (
                'clarity', 'structure', 'grammar', 'vocabulary', 'spelling',
                'conciseness', 'task_focus', 'professional_tone', 'writing_score',
            ),
        }),
        ('Narrative Feedback', {
            'fields': (
                'strengths', 'areas_for_improvement',
                'ai_recommendations', 'recurring_mistakes',
            ),
        }),
        ('Meta', {
            'fields': ('created_at', 'updated_at'),
        }),
    )

    @admin.display(description='User')
    def user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username


@admin.register(EnglishTrainingSession)
class EnglishTrainingSessionAdmin(admin.ModelAdmin):
    list_display = (
        'title_display',
        'user_name',
        'status',
        'writing_score',
        'mistake_count',
        'updated_at',
    )
    search_fields = ('title', 'user__email', 'user__first_name', 'user__last_name')
    autocomplete_fields = ('user',)
    readonly_fields = ('id', 'created_at', 'updated_at', 'finalized_at')

    fieldsets = (
        ('Session', {
            'fields': ('id', 'user', 'title'),
        }),
        ('Transcript', {
            'fields': ('transcript',),
        }),
        ('Writing Scores (0–100)', {
            'fields': (
                'clarity', 'structure', 'grammar', 'vocabulary', 'spelling',
                'conciseness', 'task_focus', 'professional_tone', 'writing_score',
            ),
        }),
        ('Mistakes (structured)', {
            'fields': ('mistakes',),
        }),
        ('Narrative Feedback', {
            'fields': (
                'strengths', 'areas_for_improvement',
                'ai_recommendations', 'recurring_mistakes',
            ),
        }),
        ('Meta', {
            'fields': ('status', 'finalized_at', 'created_at', 'updated_at'),
        }),
    )

    @admin.display(description='Title')
    def title_display(self, obj):
        return obj.title or '(untitled session)'

    @admin.display(description='Mistakes')
    def mistake_count(self, obj):
        return len(obj.mistakes or [])

    @admin.display(description='User')
    def user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username


class NotificationReceiptInline(admin.TabularInline):
    model = NotificationReceipt
    extra = 0
    readonly_fields = ('user', 'read', 'read_at')
    can_delete = True


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'get_sender_display',
        'institution',
        'pinned',
        'important',
        'active',
        'created_at',
    )
    list_filter = ('sender', 'active', 'pinned', 'important', 'institution')
    search_fields = ('title', 'body', 'institution__name')
    autocomplete_fields = ('created_by', 'institution')
    readonly_fields = ('id', 'created_at', 'updated_at')
    fieldsets = (
        ('Broadcast', {
            'fields': (
                'sender',
                'institution',
                'created_by',
                'title',
                'body',
            ),
        }),
        ('Flags', {
            'fields': (
                'pinned',
                'important',
                'active',
            ),
        }),
        ('Meta', {
            'fields': (
                'id',
                'created_at',
                'updated_at',
            ),
        }),
    )
    inlines = (NotificationReceiptInline,)


@admin.register(NotificationReceipt)
class NotificationReceiptAdmin(admin.ModelAdmin):
    list_display = ('notification', 'user', 'read', 'read_at')
    list_filter = ('read',)
    search_fields = (
        'notification__title',
        'user__email',
        'user__first_name',
        'user__last_name',
    )
    autocomplete_fields = ('notification', 'user')


@admin.register(GdTraining)
class GdTrainingAdmin(admin.ModelAdmin):
    list_display = ('title_display', 'user_name', 'topic', 'status', 'phase', 'overall_score', 'grade', 'updated_at')
    list_filter = ('status', 'phase', 'grade')
    search_fields = ('title', 'topic', 'user__email', 'user__first_name', 'user__last_name')
    autocomplete_fields = ('user',)
    readonly_fields = ('id', 'created_at', 'updated_at')

    fieldsets = (
        ('Session', {
            'fields': ('id', 'user', 'title', 'topic', 'participants', 'duration_minutes'),
        }),
        ('Transcript', {
            'fields': ('transcript',),
        }),
        ('Scores (0–100)', {
            'fields': (
                'content_quality', 'reasoning', 'communication', 'confidence',
                'teamwork', 'initiative', 'active_listening', 'build_challenge',
            ),
        }),
        ('Result', {
            'fields': (
                'overall_score', 'grade', 'overall_summary', 'strengths',
                'improvement_areas', 'evaluations', 'assessment',
            ),
        }),
        ('Meta', {
            'fields': ('status', 'phase', 'ended_at', 'created_at', 'updated_at'),
        }),
    )

    @admin.display(description='Title')
    def title_display(self, obj):
        return obj.title or '(untitled session)'

    @admin.display(description='User')
    def user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username



