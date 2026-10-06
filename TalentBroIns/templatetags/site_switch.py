"""Template tags for the admin dashboard's site downtime panel."""
from django import template
from django.urls import reverse

from TalentBroIns.models import SiteSetting

register = template.Library()


@register.simple_tag
def site_switch():
    """Everything the dashboard's Down/Up panel needs to draw itself.

    Returns a dict rather than markup on purpose: the panel lives in
    ``templates/admin/index.html`` so it can be restyled, or thrown away when
    Django changes its own dashboard, without editing Python.

    The toggle URL is built here rather than hardcoded in the template so that
    moving the ModelAdmin's URL does not quietly break the button — a broken
    ``{% url %}`` raises at render time, which is the failure mode worth having.
    """
    setting = SiteSetting.load()
    changed_by = setting.updated_by
    return {
        'down': setting.site_down,
        'message': setting.display_message,
        'changed_at': setting.updated_at,
        'changed_by': (
            (changed_by.get_full_name() or changed_by.username) if changed_by else None
        ),
        'toggle_url': reverse('admin:TalentBroIns_sitesetting_toggle'),
        'change_url': reverse('admin:TalentBroIns_sitesetting_change', args=[setting.pk]),
    }