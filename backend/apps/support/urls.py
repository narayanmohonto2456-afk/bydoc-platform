from django.urls import path

from .views import (
    StaffSupportCaseAssignView,
    StaffSupportCaseStatusView,
    SupportCaseCommentView,
    SupportCaseDetailView,
    SupportCaseListCreateView,
)


app_name = "support"


urlpatterns = [
    path(
        "cases/",
        SupportCaseListCreateView.as_view(),
        name="case-list-create",
    ),
    path(
        "cases/<uuid:case_id>/",
        SupportCaseDetailView.as_view(),
        name="case-detail",
    ),
    path(
        "cases/<uuid:case_id>/comments/",
        SupportCaseCommentView.as_view(),
        name="case-comment",
    ),
    path(
        "staff/cases/<uuid:case_id>/assign/",
        StaffSupportCaseAssignView.as_view(),
        name="staff-case-assign",
    ),
    path(
        "staff/cases/<uuid:case_id>/status/",
        StaffSupportCaseStatusView.as_view(),
        name="staff-case-status",
    ),
]