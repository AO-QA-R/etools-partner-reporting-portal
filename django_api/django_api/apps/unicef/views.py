import logging
from datetime import datetime

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404

from rest_framework import status as statuses
from rest_framework.exceptions import ValidationError
from rest_framework.generics import RetrieveAPIView, ListAPIView
from rest_framework.parsers import FileUploadParser, FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

import django_filters.rest_framework
from easy_pdf.rendering import render_to_pdf_response

from core.api_error_codes import APIErrorCode
from core.common import (
    PROGRESS_REPORT_STATUS,
    INDICATOR_REPORT_STATUS,
    OVERALL_STATUS,
    PD_STATUS
)
from core.paginations import SmallPagination
from core.permissions import (
    IsAuthenticated,
    IsPartnerAuthorizedOfficer,
    AnyPermission,
    IsPartnerEditor,
    IsPartnerViewer,
)
from core.models import Location, PartnerAuthorizedOfficerRole
from core.serializers import ShortLocationSerializer

from indicator.models import Reportable, IndicatorReport, IndicatorBlueprint, IndicatorLocationData
from indicator.serializers import (
    IndicatorListSerializer,
    PDReportContextIndicatorReportSerializer
)
from indicator.filters import PDReportsFilter
from indicator.serializers import IndicatorBlueprintSimpleSerializer
from partner.models import Partner
from unicef.exports.reportables import ReportableListXLSXExporter, ReportableListPDFExporter

from unicef.exports.annex_c_excel import AnnexCXLSXExporter, SingleProgressReportsXLSXExporter
from unicef.exports.programme_documents import ProgrammeDocumentsXLSXExporter, ProgrammeDocumentsPDFExporter
from unicef.exports.progress_reports import ProgressReportDetailPDFExporter, ProgressReportListPDFExporter
from unicef.exports.utilities import group_indicator_reports_by_lower_level_output
from utils.mixins import ListExportMixin, ObjectExportMixin
from utils.emails import send_email_from_template

from .serializers import (
    ProgrammeDocumentSerializer,
    ProgrammeDocumentDetailSerializer,
    ProgressReportSimpleSerializer,
    ProgressReportSerializer,
    ProgressReportReviewSerializer,
    LLOutputSerializer,
    ProgrammeDocumentCalculationMethodsSerializer,
    ProgrammeDocumentProgressSerializer,
    ProgressReportUpdateSerializer,
    ProgressReportAttachmentSerializer,
    ProgressReportSRUpdateSerializer,
    ProgressReportPullHFDataSerializer,
)
from .models import ProgrammeDocument, ProgressReport, LowerLevelOutput
from .permissions import (
    CanChangePDCalculationMethod,
    UnicefPartnershipManagerOrRead
)
from .filters import (
    ProgrammeDocumentFilter, ProgressReportFilter,
    ProgrammeDocumentIndicatorFilter
)

logger = logging.getLogger(__name__)


class ProgrammeDocumentAPIView(ListExportMixin, ListAPIView):
    """
    Endpoint for getting a list of Programme Documents and being able to
    filter by them.
    """
    serializer_class = ProgrammeDocumentSerializer
    permission_classes = (AnyPermission(IsPartnerAuthorizedOfficer, IsPartnerEditor, IsPartnerViewer), )
    pagination_class = SmallPagination
    filter_backends = (django_filters.rest_framework.DjangoFilterBackend, )
    filter_class = ProgrammeDocumentFilter
    exporters = {
        'xlsx': ProgrammeDocumentsXLSXExporter,
        'pdf': ProgrammeDocumentsPDFExporter,
    }

    def get_queryset(self):
        return ProgrammeDocument.objects.filter(
            partner=self.request.user.partner, workspace=self.kwargs['workspace_id']
        )


class ProgrammeDocumentDetailsAPIView(RetrieveAPIView):

    serializer_class = ProgrammeDocumentDetailSerializer
    permission_classes = (AnyPermission(IsPartnerAuthorizedOfficer, IsPartnerEditor, IsPartnerViewer), )
    lookup_url_kwarg = 'pd_id'

    def get(self, request, workspace_id, pd_id, *args, **kwargs):
        """
        Get Programme Document Details by given pk.
        """
        self.workspace_id = workspace_id
        serializer = self.get_serializer(
            self.get_object(pd_id)
        )
        return Response(serializer.data, status=statuses.HTTP_200_OK)

    def get_object(self, pd_id):
        try:
            return ProgrammeDocument.objects.get(
                partner=self.request.user.partner,
                workspace=self.workspace_id,
                pk=pd_id)
        except ProgrammeDocument.DoesNotExist as exp:
            logger.exception({
                "endpoint": "ProgrammeDocumentDetailsAPIView",
                "request.data": self.request.data,
                "pk": pd_id,
                "exception": exp,
            })
            raise Http404


class ProgrammeDocumentProgressAPIView(RetrieveAPIView):

    serializer_class = ProgrammeDocumentProgressSerializer
    permission_classes = (AnyPermission(IsPartnerAuthorizedOfficer, IsPartnerEditor, IsPartnerViewer), )
    lookup_url_kwarg = 'pd_id'

    def get(self, request, workspace_id, pd_id, *args, **kwargs):
        """
        Get Programme Document Details by given pk.
        """
        self.workspace_id = workspace_id
        serializer = self.get_serializer(
            self.get_object(pd_id)
        )
        return Response(serializer.data, status=statuses.HTTP_200_OK)

    def get_object(self, pd_id):
        user_has_global_view = self.request.user.is_unicef
        external_request = self.request.query_params.get('external', False)
        search_by = 'external_id' if external_request else 'pk'
        query_params = {}
        if not user_has_global_view:
            query_params['partner'] = self.request.user.partner
        query_params['workspace'] = self.workspace_id,
        query_params[search_by] = pd_id
        try:
            return ProgrammeDocument.objects.get(**query_params)
        except ProgrammeDocument.DoesNotExist as exp:
            logger.exception({
                "endpoint": "ProgrammeDocumentProgressAPIView",
                "request.data": self.request.data,
                search_by: pd_id,
                "exception": exp,
            })
            raise Http404


class ProgrammeDocumentLocationsAPIView(ListAPIView):

    queryset = Location.objects.all()
    serializer_class = ShortLocationSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        programme_documents = ProgrammeDocument.objects.filter(
            partner=self.request.user.partner,
            workspace=self.kwargs['workspace_id']
        )
        return super(ProgrammeDocumentLocationsAPIView, self).get_queryset().filter(
            indicator_location_data__indicator_report__progress_report__programme_document__in=programme_documents
        ).distinct()


class ProgrammeDocumentIndicatorsAPIView(ListExportMixin, ListAPIView):

    queryset = Reportable.objects.filter(lower_level_outputs__isnull=False)
    serializer_class = IndicatorListSerializer
    pagination_class = SmallPagination
    filter_backends = (django_filters.rest_framework.DjangoFilterBackend,)
    filter_class = ProgrammeDocumentIndicatorFilter
    exporters = {
        'xlsx': ReportableListXLSXExporter,
        'pdf': ReportableListPDFExporter,
    }
    permission_classes = (AnyPermission(IsPartnerAuthorizedOfficer, IsPartnerEditor, IsPartnerViewer), )

    def get_queryset(self):
        programme_documents = ProgrammeDocument.objects.filter(
            partner=self.request.user.partner,
            workspace=self.kwargs['workspace_id']
        )
        return super(ProgrammeDocumentIndicatorsAPIView, self).get_queryset().filter(
            indicator_reports__progress_report__programme_document__in=programme_documents
        ).distinct()


class ProgressReportAPIView(ListExportMixin, ListAPIView):
    """
    Endpoint for getting list of all Progress Reports. Supports filtering
    as per ProgressReportFilter by status, pd_ref_title, programme_document
    (id) etc.

    Supports additional GET param to filter by external_partner_id
    """
    serializer_class = ProgressReportSimpleSerializer
    pagination_class = SmallPagination
    permission_classes = (AnyPermission(IsPartnerAuthorizedOfficer, IsPartnerEditor, IsPartnerViewer), )
    filter_backends = (django_filters.rest_framework.DjangoFilterBackend, )
    filter_class = ProgressReportFilter
    exporters = {
        'xlsx': AnnexCXLSXExporter,
        'pdf': ProgressReportListPDFExporter,
    }
    # TODO: use django filter for ordering
    order_options = {
        'due_date', 'status', 'programme_document__reference_number', 'submission_date', 'start_date'
    }

    def get_queryset(self):
        user_has_global_view = self.request.user.is_unicef

        external_partner_id = self.request.GET.get('external_partner_id')
        if external_partner_id is not None:
            partners = Partner.objects.filter(external_id=external_partner_id)
            queryset = ProgressReport.objects.filter(programme_document__partner__in=partners)
        else:
            # TODO: In case of UNICEF user.. allow for all (maybe create a special group for the unicef api user?)
            # Limit reports to this user's partner only
            if user_has_global_view:
                queryset = ProgressReport.objects.all()
            else:
                queryset = ProgressReport.objects.filter(programme_document__partner=self.request.user.partner)
        return queryset.filter(programme_document__workspace=self.kwargs['workspace_id']).distinct()

    def list(self, request, *args, **kwargs):
        filtered = ProgressReportFilter(request.GET, queryset=self.get_queryset())

        qs = filtered.qs
        order = request.query_params.get('sort', None)
        if order:
            order_field = order.split('.')[0]
            if order_field in self.order_options:
                qs = qs.order_by(order_field)
                if len(order.split('.')) > 1 and order.split('.')[1] == 'desc':
                    qs = qs.order_by('-%s' % order_field)

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(qs, many=True)
        return Response(
            serializer.data,
            status=statuses.HTTP_200_OK
        )


class ProgressReportAnnexCPDFView(RetrieveAPIView):
    """
    Endpoint for getting PDF of Progress Report Annex C.
    """
    queryset = ProgressReport.objects.all()
    permission_classes = (AnyPermission(IsPartnerAuthorizedOfficer, IsPartnerEditor), )

    def get(self, request, *args, **kwargs):
        report = self.get_object()

        data = {
            'report': report,
            'pd': report.programme_document,
            'challenges_in_the_reporting_period': report.challenges_in_the_reporting_period,
            'proposed_way_forward': report.proposed_way_forward,
            'partner_contribution_to_date': report.partner_contribution_to_date,
            'submission_date': report.get_submission_date(),
            'authorized_officer': report.programme_document.unicef_officers.first(),
            'outputs': group_indicator_reports_by_lower_level_output(report.indicator_reports.all()),
            'title': 'Progress Report',
            'header': 'PART 2: programme progress/final report - to '
                      'be completed by CSO as part of reporting with FACE'.upper(),
        }

        return render_to_pdf_response(request, "report_annex_c_pdf.html", data, encoding='utf8')


class ProgressReportDetailsUpdateAPIView(APIView):
    """
        Endpoint for updating Progress Report narrative fields
    """
    permission_classes = (
        AnyPermission(IsPartnerAuthorizedOfficer, IsPartnerEditor),
    )

    def get_object(self, pk):
        try:
            return ProgressReport.objects.get(
                programme_document__partner=self.request.user.partner,  # TODO: check if needed?
                programme_document__workspace=self.workspace_id,
                pk=pk
            )
        except ProgressReport.DoesNotExist as exp:
            logger.exception({
                "endpoint": "ProgressReportDetailsUpdateAPIView",
                "request.data": self.request.data,
                "pk": pk,
                "exception": exp,
            })
            raise Http404

    def put(self, request, workspace_id, pk, *args, **kwargs):
        self.workspace_id = workspace_id
        pr = self.get_object(pk)

        if pr.report_type == "SR":
            serializer = ProgressReportSRUpdateSerializer(instance=pr, data=request.data)
        else:
            serializer = ProgressReportUpdateSerializer(instance=pr, data=request.data)

        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=statuses.HTTP_200_OK)


class ProgressReportDetailsAPIView(ObjectExportMixin, RetrieveAPIView):
    """
    Endpoint for getting a single Progress Report
    """
    serializer_class = ProgressReportSerializer
    permission_classes = (AnyPermission(IsPartnerAuthorizedOfficer, IsPartnerEditor, IsPartnerViewer), )
    filter_backends = (django_filters.rest_framework.DjangoFilterBackend, )
    exporters = {
        'pdf': ProgressReportDetailPDFExporter,
        'xlsx': SingleProgressReportsXLSXExporter,
    }

    def get_object(self):
        pk = self.kwargs['pk']
        user_has_global_view = self.request.user.is_unicef
        query_params = {}
        if not user_has_global_view:
            query_params["programme_document__partner"] = self.request.user.partner
        query_params['programme_document__workspace'] = self.kwargs['workspace_id']
        query_params['pk'] = pk
        try:
            return ProgressReport.objects.get(**query_params)
        except ProgressReport.DoesNotExist as exp:
            logger.exception({
                "endpoint": "ProgressReportDetailsAPIView",
                "request.data": self.request.data,
                "pk": pk,
                "exception": exp,
            })
            raise Http404


class ProgressReportIndicatorsAPIView(ListAPIView):
    serializer_class = PDReportContextIndicatorReportSerializer
    pagination_class = SmallPagination
    permission_classes = (AnyPermission(IsPartnerAuthorizedOfficer, IsPartnerEditor, IsPartnerViewer), )
    filter_backends = (django_filters.rest_framework.DjangoFilterBackend,)
    filter_class = PDReportsFilter

    def get_queryset(self):
        # Limit reports to partner only
        return IndicatorReport.objects.filter(progress_report__programme_document__partner=self.request.user.partner)

    def list(self, request, workspace_id, progress_report_id, *args, **kwargs):
        """
        Get Programme Document Details by given pk.
        """
        queryset = self.get_queryset().filter(
            progress_report__id=progress_report_id,
            progress_report__programme_document__workspace=workspace_id)
        filtered = PDReportsFilter(request.GET, queryset=queryset)

        page = self.paginate_queryset(filtered.qs)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(filtered.qs, many=True)
        return Response(serializer.data, status=statuses.HTTP_200_OK)


class ProgressReportLocationsAPIView(ListAPIView):
    queryset = Location.objects.all()
    serializer_class = ShortLocationSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self, pk):
        try:
            return ProgressReport.objects.get(
                programme_document__partner=self.request.user.partner,
                programme_document__workspace=self.workspace_id,
                pk=pk
            )
        except ProgressReport.DoesNotExist as exp:
            logger.exception({
                "endpoint": "ProgressReportLocationsAPIView",
                "request.data": self.request.data,
                "pk": pk,
                "exception": exp,
            })
            raise Http404

    def list(self, request, workspace_id, progress_report_id, *args, **kwargs):
        self.workspace_id = workspace_id
        pr = self.get_object(progress_report_id)
        queryset = self.get_queryset().filter(
            indicator_location_data__indicator_report__progress_report=pr).distinct()
        filtered = ProgressReportFilter(request.GET, queryset=queryset)

        page = self.paginate_queryset(filtered.qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(filtered.qs, many=True)
        return Response(
            serializer.data,
            status=statuses.HTTP_200_OK
        )


class ProgressReportSubmitAPIView(APIView):
    """
    Only a partner authorized officer can submit a progress report.
    """
    permission_classes = (IsPartnerAuthorizedOfficer,)

    def get_object(self):
        try:
            return ProgressReport.objects.get(
                programme_document__partner=self.request.user.partner,
                programme_document__workspace=self.kwargs['workspace_id'],
                pk=self.kwargs['pk'])
        except ProgressReport.DoesNotExist as exp:
            logger.exception({
                "endpoint": "ProgressReportSubmitAPIView",
                "request.data": self.request.data,
                "pk": self.kwargs['pk'],
                "exception": exp,
            })
            raise Http404

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        progress_report = self.get_object()

        if progress_report.programme_document.status \
                not in [PD_STATUS.active, PD_STATUS.ended, PD_STATUS.terminated, PD_STATUS.suspended]:
            raise ValidationError(
                "Updating Progress Report for a {} Programme Document is not allowed. "
                "Only Active/Ended/Suspended/Terminated "
                "PDs can be reported on.".format(progress_report.programme_document.get_status_display())
            )

        for ir in progress_report.indicator_reports.all():
            # Check if all indicator data is fulfilled
            for data in ir.indicator_location_data.all():
                for key, vals in data.disaggregation.items():
                    if (vals.get('d', 0) in [0, None, '']):
                        raise ValidationError(
                            "You have not completed all indicator location data across "
                            "all indicator reports for this progress report."
                        )

            # Check if indicator was already submitted or SENT BACK
            if ir.submission_date is None or ir.report_status == INDICATOR_REPORT_STATUS.sent_back:
                ir.submission_date = datetime.now().date()
                ir.report_status = INDICATOR_REPORT_STATUS.submitted
                ir.save()

        # QPR report type specific validations
        if progress_report.report_type == "QPR":
            # Check for IndicatorReport narrative assessment for overall status Met or No Progress
            if ir.overall_status not in {OVERALL_STATUS.met, OVERALL_STATUS.no_progress} \
                    and not ir.narrative_assessment:
                raise ValidationError(
                    "You have not completed narrative assessment for one of Outputs ({}). Unless your Output "
                    "status is Met or No Progress.".format(
                        ir.reportable.content_object
                    )
                )

            # Check if PR other tab is fulfilled
            other_tab_errors = []
            if not progress_report.partner_contribution_to_date:
                other_tab_errors.append("You have not completed Partner Contribution To Date field on Other Info tab.")
            if not progress_report.challenges_in_the_reporting_period:
                other_tab_errors.append(
                    "You have not completed Challenges / bottlenecks in the reporting period field on Other Info tab."
                )
            if not progress_report.proposed_way_forward:
                other_tab_errors.append("You have not completed Proposed way forward field on Other Info tab.")

            if other_tab_errors:
                raise ValidationError(other_tab_errors)

        if progress_report.submission_date is None or progress_report.status == PROGRESS_REPORT_STATUS.sent_back:
            provided_email = request.data.get('submitted_by_email')

            authorized_officer_user = get_user_model().objects.filter(
                email=provided_email or self.request.user.email,
                groups=PartnerAuthorizedOfficerRole.as_group(),
                email__in=progress_report.programme_document.partner_focal_point.values_list('email', flat=True)
            ).first()

            if not authorized_officer_user:
                if provided_email:
                    _error_message = 'Report could not be submitted, because {} is not the authorized ' \
                                     'officer assigned to the PCA that is connected to that PD.'.format(provided_email)
                else:
                    _error_message = 'Your report could not be submitted, because you are not the authorized ' \
                                     'officer assigned to the PCA that is connected to that PD.'
                raise ValidationError(
                    _error_message, code=APIErrorCode.PR_SUBMISSION_FAILED_USER_NOT_AUTHORIZED_OFFICER
                )

            # HR report type progress report is automatically accepted
            if progress_report.report_type == "HR":
                progress_report.status = PROGRESS_REPORT_STATUS.accepted

            # QPR report type is submitted at this stage
            else:
                progress_report.status = PROGRESS_REPORT_STATUS.submitted

            progress_report.submission_date = datetime.now().date()
            progress_report.submitted_by = authorized_officer_user
            progress_report.submitting_user = self.request.user
            progress_report.save()

            # IndicatorLocationData lock marking
            ild_ids = progress_report.indicator_reports.values_list('indicator_location_data', flat=True)
            IndicatorLocationData.objects.filter(id__in=ild_ids).update(is_locked=True)

            parent_irs = progress_report.indicator_reports.values_list('parent', flat=True)
            IndicatorLocationData.objects.filter(indicator_report__in=parent_irs).update(is_locked=True)

            serializer = ProgressReportSerializer(instance=progress_report)
            return Response(serializer.data, status=statuses.HTTP_200_OK)
        else:
            raise ValidationError(
                "Progress report was already submitted. Your IMO will need to send it "
                "back for you to edit your submission."
            )


class ProgressReportSRSubmitAPIView(APIView):
    """
    A dedicated API endpoint for submitting SR Progress Report.
    Only a partner authorized officer can submit a progress report.
    """
    permission_classes = (IsPartnerAuthorizedOfficer,)

    def get_object(self):
        try:
            return ProgressReport.objects.get(
                programme_document__partner=self.request.user.partner,
                programme_document__workspace=self.kwargs['workspace_id'],
                pk=self.kwargs['pk'],
                report_type="SR")
        except ProgressReport.DoesNotExist as exp:
            logger.exception({
                "endpoint": "ProgressReportSRSubmitAPIView",
                "request.data": self.request.data,
                "pk": self.kwargs['pk'],
                "exception": exp,
            })
            raise Http404

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        progress_report = self.get_object()
        if progress_report.programme_document.status \
                not in [PD_STATUS.active, PD_STATUS.ended, PD_STATUS.terminated, PD_STATUS.suspended]:
            raise ValidationError(
                "Updating Progress Report for a {} Programme Document is not allowed. "
                "Only Active/Ended/Suspended/Terminated "
                "PDs can be reported on.".format(progress_report.programme_document.get_status_display())
            )

        if not progress_report.narrative:
            raise ValidationError(
                "Narrative is required for SR report type"
            )

        # Attachment field validation
        if not progress_report.attachment:
            raise ValidationError(
                "Attachment is required for SR report type"
            )

        # Accept/send back validation and submission on behalf feature
        if progress_report.submission_date is None or progress_report.status == PROGRESS_REPORT_STATUS.sent_back:
            provided_email = request.data.get('submitted_by_email')

            authorized_officer_user = get_user_model().objects.filter(
                email=provided_email or self.request.user.email,
                groups=PartnerAuthorizedOfficerRole.as_group(),
                email__in=progress_report.programme_document.partner_focal_point.values_list('email', flat=True)
            ).first()

            if not authorized_officer_user:
                if provided_email:
                    _error_message = 'Report could not be submitted, because {} is not the authorized ' \
                                     'officer assigned to the PCA that is connected to that PD.'.format(provided_email)
                else:
                    _error_message = 'Your report could not be submitted, because you are not the authorized ' \
                                     'officer assigned to the PCA that is connected to that PD.'
                raise ValidationError(
                    _error_message, code=APIErrorCode.PR_SUBMISSION_FAILED_USER_NOT_AUTHORIZED_OFFICER
                )

            progress_report.status = PROGRESS_REPORT_STATUS.submitted
            progress_report.submission_date = datetime.now().date()
            progress_report.submitted_by = authorized_officer_user
            progress_report.submitting_user = self.request.user
            progress_report.save()

            serializer = ProgressReportSerializer(instance=progress_report)
            return Response(serializer.data, status=statuses.HTTP_200_OK)
        else:
            raise ValidationError(
                "Progress report was already submitted. Your IMO will need to send it "
                "back for you to edit your submission."
            )


class ProgressReportPullHFDataAPIView(APIView):
    """
    Reserved only for a LLO Reportable's IndicatorLocationData on QPR ProgressReport
    to pull data from LLO Reportable's IndicatorLocationData on HR ProgressReports
    with overlapping start and end date period to QPR end date.
    """
    permission_classes = (IsPartnerAuthorizedOfficer,)

    def get_object(self):
        try:
            return ProgressReport.objects.get(
                programme_document__workspace=self.kwargs['workspace_id'],
                pk=self.kwargs['pk'],
            )
        except ProgressReport.DoesNotExist as exp:
            logger.exception({
                "endpoint": "ProgressReportPullHFDataAPIView",
                "request.data": self.request.data,
                "pk": self.kwargs['pk'],
                "exception": exp,
            })
            raise Http404

    def _get_target_hf_reports_with_indicator_report(self):
        self.progress_report = self.get_object()

        if self.progress_report.report_type != "QPR":
            raise ValidationError("This Progress Report is not QPR type.")

        try:
            indicator_report = IndicatorReport.objects.get(id=self.kwargs['indicator_report_pk'])
        except IndicatorReport.DoesNotExist:
            raise ValidationError("IndicatorReport does not exist.")

        if not isinstance(indicator_report.reportable.content_object, LowerLevelOutput):
            raise ValidationError("Reportable is not LLO type.")

        pd_from_reportable = indicator_report.reportable.content_object.cp_output.programme_document

        if self.progress_report.programme_document != pd_from_reportable:
            raise ValidationError("Reportable does not belong to the passed-in progress report.")

        hf_reports = ProgressReport.objects.filter(
            programme_document=self.progress_report.programme_document,
            report_type="HR",
            start_date__gte=self.progress_report.start_date,
            end_date__lte=self.progress_report.end_date,
        )

        return indicator_report, hf_reports

    def _calculate_report_location_totals_per_reports(self, indicator_report, hf_reports, locations):
        ir_ids = hf_reports.values_list('indicator_reports', flat=True)
        target_hf_irs = IndicatorReport.objects.filter(
            id__in=ir_ids,
            time_period_start__gte=self.progress_report.start_date,
            time_period_end__lte=self.progress_report.end_date,
            reportable=indicator_report.reportable,
        )

        calculated = {loc_id: {'c': 0, 'v': 0, 'd': 0} for loc_id in locations}

        for ir in target_hf_irs:
            for ild in ir.indicator_location_data.all():
                calculated[ild.location.id]['c'] += ild.disaggregation['()']['c']
                calculated[ild.location.id]['v'] += ild.disaggregation['()']['v']

                if indicator_report.reportable.blueprint.unit == IndicatorBlueprint.NUMBER:
                    calculated[ild.location.id]['d'] = 1

                else:
                    calculated[ild.location.id]['d'] += ild.disaggregation['()']['d']

        return calculated

    def get(self, request, *args, **kwargs):
        indicator_report, hf_reports = self._get_target_hf_reports_with_indicator_report()

        serializer = ProgressReportPullHFDataSerializer(
            hf_reports,
            many=True,
            context={'indicator_report': indicator_report}
        )
        return Response(serializer.data, status=statuses.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        indicator_report, hf_reports = self._get_target_hf_reports_with_indicator_report()
        locations = indicator_report.indicator_location_data.values_list('location', flat=True)
        loc_totals = {loc_id: {'()': {'c': 0, 'v': 0, 'd': 0}} for loc_id in locations}

        consolidated_total_per_location_dict = self._calculate_report_location_totals_per_reports(
            indicator_report,
            hf_reports,
            locations
        )

        # Data pull total consolidation
        for loc_id, total in consolidated_total_per_location_dict.items():
            loc_totals[loc_id]['()'] = dict(list(loc_totals[loc_id]['()'].items()) + list(total.items()))

        # Data pull updates
        for ild in indicator_report.indicator_location_data.all():
            ild.disaggregation = loc_totals[ild.location.id]
            ild.save()

        return Response(loc_totals, status=statuses.HTTP_200_OK)


class ProgressReportReviewAPIView(APIView):
    """
    Called by PO to accept or send back a submitted progress report. Called
    from outside of PRP.

    Only a PO (not a partner user) should be allowed to do this action.
    """
    permission_classes = (UnicefPartnershipManagerOrRead,)

    def get_object(self):
        try:
            return ProgressReport.objects.get(
                programme_document__workspace=self.kwargs['workspace_id'],
                pk=self.kwargs['pk']
            )
        except ProgressReport.DoesNotExist as exp:
            logger.exception({
                "endpoint": "ProgressReportReviewAPIView",
                "request.data": self.request.data,
                "pk": self.kwargs['pk'],
                "exception": exp,
            })
            raise Http404

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        progress_report = self.get_object()

        if progress_report.status not in {
            PROGRESS_REPORT_STATUS.submitted,
            PROGRESS_REPORT_STATUS.accepted,
        }:
            raise ValidationError("This report is not in submitted / accepted state.")

        serializer = ProgressReportReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        progress_report.status = serializer.validated_data['status']
        progress_report.review_date = datetime.now().date()

        if progress_report.status == PROGRESS_REPORT_STATUS.sent_back:
            progress_report.sent_back_feedback = serializer.validated_data['comment']

        elif progress_report.status == PROGRESS_REPORT_STATUS.accepted:
            progress_report.review_overall_status = serializer.validated_data['overall_status']

        progress_report.save()
        serializer = ProgressReportSerializer(instance=progress_report)
        return Response(serializer.data, status=statuses.HTTP_200_OK)


class ProgrammeDocumentCalculationMethodsAPIView(APIView):
    """
    Supports GET request to get the unit and calculation for each indicator
    grouped by LLO for a particular PD.

    POST request takes same format data to update the calculation methods then.
    Only partner authorized officer and partner editor can change the
    calculation methods.
    """
    permission_classes = (CanChangePDCalculationMethod,)
    serializer_class = ProgrammeDocumentCalculationMethodsSerializer

    def get(self, request, workspace_id, pd_id):
        """
        Construct the input data to the serializer for the LLO and its
        associated indicators.
        """
        pd = get_object_or_404(
            ProgrammeDocument, id=pd_id, workspace__id=workspace_id
        )

        data = {'ll_outputs_and_indicators': []}
        for llo in pd.lower_level_outputs:
            indicator_blueprints = []
            for reportable in llo.reportables.all():
                indicator_blueprints.append(reportable.blueprint)

            inner_data = {
                'll_output': LLOutputSerializer(instance=llo).data,
                'indicators': IndicatorBlueprintSimpleSerializer(indicator_blueprints, many=True).data
            }

            data['ll_outputs_and_indicators'].append(inner_data)

        return Response(ProgrammeDocumentCalculationMethodsSerializer(
            data).data)

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        """
        The goal of this is to set the calculation methods for the indicators
        associated with lower level outputs of this PD.
        """
        serializer = ProgrammeDocumentCalculationMethodsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        notify_email_flag = False
        pd_to_notify = None

        for llo_and_indicators in serializer.validated_data[
                'll_outputs_and_indicators']:
            for indicator_blueprint in llo_and_indicators['indicators']:
                instance = get_object_or_404(IndicatorBlueprint, id=indicator_blueprint['id'])

                old_formulas = {
                    instance.calculation_formula_across_periods,
                    instance.calculation_formula_across_locations
                }

                new_formulas = {
                    indicator_blueprint['calculation_formula_across_locations'],
                    indicator_blueprint['calculation_formula_across_periods']
                }

                llo = instance.reportables.first().content_object
                pd = llo.cp_output.programme_document
                accepted_progress_reports = pd.progress_reports.filter(status=PROGRESS_REPORT_STATUS.accepted)

                if not notify_email_flag and accepted_progress_reports.exists():
                    if not old_formulas == new_formulas:
                        notify_email_flag = True
                        pd_to_notify = pd

                instance.calculation_formula_across_periods = indicator_blueprint['calculation_formula_across_periods']
                instance.calculation_formula_across_locations = indicator_blueprint[
                    'calculation_formula_across_locations'
                ]
                instance.clean()
                instance.save()

        if notify_email_flag:
            focal_points = list(pd_to_notify.unicef_focal_point.values('name', 'email'))
            template_data = dict()
            template_data['pd'] = pd_to_notify

            for focal_point in focal_points:
                template_data['focal_point_name'] = focal_point['name']
                send_email_from_template(
                    'email/notify_partner_on_calculation_method_change_subject.txt',
                    'email/notify_partner_on_calculation_method_change.txt',
                    template_data,
                    settings.DEFAULT_FROM_EMAIL,
                    [focal_point['email']],
                    fail_silently=False
                )

        return Response(serializer.data, status=statuses.HTTP_200_OK)


class ProgressReportAttachmentAPIView(APIView):
    permission_classes = (AnyPermission(IsPartnerAuthorizedOfficer, IsPartnerEditor), )
    parser_classes = (FormParser, MultiPartParser, FileUploadParser)

    def get(self, request, workspace_id, progress_report_id):
        progress_report = get_object_or_404(
            ProgressReport,
            id=progress_report_id,
            programme_document__workspace_id=workspace_id
        )

        try:
            # lookup just so the possible FileNotFoundError can be triggered
            progress_report.attachment
            serializer = ProgressReportAttachmentSerializer(progress_report)
            return Response(serializer.data, status=statuses.HTTP_200_OK)
        except FileNotFoundError:
            pass

        return Response({"message": "Attachment does not exist."}, status=statuses.HTTP_404_NOT_FOUND)

    @transaction.atomic
    def delete(self, request, workspace_id, progress_report_id):
        pr = get_object_or_404(
            ProgressReport,
            id=progress_report_id,
            programme_document__workspace_id=workspace_id
        )

        if pr.attachment:
            try:
                pr.attachment.delete()
                return Response({}, status=statuses.HTTP_204_NO_CONTENT)
            except ValueError:
                pass
        else:
            return Response({"message": "Attachment does not exist."}, status=statuses.HTTP_404_NOT_FOUND)

    @transaction.atomic
    def put(self, request, workspace_id, progress_report_id):
        pr = get_object_or_404(
            ProgressReport,
            id=progress_report_id,
            programme_document__workspace_id=workspace_id)

        serializer = ProgressReportAttachmentSerializer(
            instance=pr,
            data=request.data
        )

        serializer.is_valid(raise_exception=True)
        if pr.attachment:
            try:
                pr.attachment.delete()
            except ValueError:
                pass

        pr = serializer.save()

        return Response(
            ProgressReportAttachmentSerializer(pr).data, status=statuses.HTTP_200_OK
        )
