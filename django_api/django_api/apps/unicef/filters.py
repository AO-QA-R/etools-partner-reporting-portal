from datetime import datetime
from django.conf import settings
from django.db.models import Q
import django_filters
from distutils.util import strtobool
from django_filters.filters import (
    ChoiceFilter, CharFilter, DateFilter, TypedChoiceFilter, CharFilter
)

from core.common import PD_LIST_REPORT_STATUS, PD_STATUS, PROGRESS_REPORT_STATUS
from indicator.models import Reportable
from .models import ProgrammeDocument, ProgressReport

BOOLEAN_CHOICES = (('0', 'False'), ('1', 'True'),)


class ProgrammeDocumentIndicatorFilter(django_filters.FilterSet):

    pd_statuses = CharFilter(method='get_status')
    pds = CharFilter(method='get_programme_document')
    location = CharFilter(method='get_locations')
    blueprint__title = CharFilter(method='get_blueprint_title')
    incomplete = CharFilter(method='get_incomplete')

    class Meta:
        model = Reportable
        fields = (
            'id', 'blueprint__title',
        )

    def get_status(self, queryset, name, value):
        return queryset.filter(
            lower_level_outputs__cp_output__programme_document__status__in=value.split(','))

    def get_programme_document(self, queryset, name, value):
        return queryset.filter(
            lower_level_outputs__cp_output__programme_document_id__in=map(lambda x: int(x), value.split(',')))

    def get_locations(self, queryset, name, value):
        return queryset.filter(locations=value)

    def get_blueprint_title(self, queryset, name, value):
        return queryset.filter(blueprint__title__contains=value)

    def get_incomplete(self, queryset, name, value):
        return queryset.filter(
            lower_level_outputs__cp_output__programme_document__progress_reports__indicator_reports__submission_date__isnull=True) if value == "1" else queryset


class ProgrammeDocumentFilter(django_filters.FilterSet):
    ref_title = CharFilter(method='get_reference_number_title')
    status = CharFilter(method='get_status')
    location = CharFilter(method='get_location')

    class Meta:
        model = ProgrammeDocument
        fields = ['ref_title', 'status', 'location']

    def get_status(self, queryset, name, value):
        return queryset.filter(status__in=value.split(','))

    def get_reference_number_title(self, queryset, name, value):
        return queryset.filter(
            Q(reference_number__icontains=value) | Q(title__icontains=value)
        )

    def get_location(self, queryset, name, value):
        return queryset.filter(
            progress_reports__indicator_reports__indicator_location_data__location=value)


class ProgressReportFilter(django_filters.FilterSet):
    status = CharFilter(
        name='status',
        label='Status')
    pd_ref_title = CharFilter(name='pd ref title', method='get_pd_ref_title',
                              label='PD/Ref # title')
    due_date = DateFilter(name='due date', method='get_due_date', label='Due date',
                          input_formats=[settings.PRINT_DATA_FORMAT])
    due = TypedChoiceFilter(name='due', choices=BOOLEAN_CHOICES, coerce=strtobool,
                            method='get_due_overdue_status', label='Show only due or overdue')
    location = CharFilter(name='location', method='get_location',
                          label='Location')
    programme_document_ext = CharFilter(name='programme_document_ext', method='get_pd_ext',
                                        label='programme_document_ext')
    section = CharFilter(name='section', method='get_section')
    cp_output = CharFilter(name='cp_output', method='get_cp_output')

    class Meta:
        model = ProgressReport
        fields = ['status', 'pd_ref_title', 'due_date', 'programme_document',
                  'programme_document__id', 'programme_document__external_id', 'section', 'cp_output']

    def get_status(self, queryset, name, value):
        return queryset.filter(status__in=value.split(','))

    def get_pd_ext(self, queryset, name, value):
        return queryset.filter(programme_document__external_id=value)

    def get_section(self, queryset, name, value):
        return queryset.filter(programme_document__sections__external_id=value)

    def get_cp_output(self, queryset, name, value):
        return queryset.filter(programme_document__cp_outputs__external_cp_output_id=value)


    def get_due_overdue_status(self, queryset, name, value):
        if value:
            return queryset.filter(
                status__in=[PROGRESS_REPORT_STATUS.due, PROGRESS_REPORT_STATUS.overdue])
        return queryset

    def get_pd_ref_title(self, queryset, name, value):
        return queryset.filter(
            Q(programme_document__reference_number__icontains=value) |
            Q(programme_document__title__icontains=value)
        )

    def get_due_date(self, queryset, name, value):
        return queryset.filter(due_date__lte=value)

    def get_location(self, queryset, name, value):
        return queryset.filter(
            indicator_reports__indicator_location_data__location=value)
