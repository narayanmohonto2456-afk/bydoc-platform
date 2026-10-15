from django.urls import path

from . import views

urlpatterns = [
    path("me/", views.MeView.as_view()),
    path("summary/", views.SummaryView.as_view()),
    path("providers/", views.ProvidersView.as_view()),
    path("providers/active/", views.ActiveProvidersView.as_view()),
    path("providers/<str:kind>/<uuid:application_id>/review/", views.ReviewProviderView.as_view()),
    path("providers/<str:kind>/<uuid:provider_id>/status/", views.ProviderStatusView.as_view()),
    path("payments/", views.PaymentsView.as_view()),
    path("payments/<uuid:intent_id>/reconcile/", views.ReconcilePaymentView.as_view()),
    path("payments/<uuid:intent_id>/investigation/", views.PaymentInvestigationView.as_view()),
    path("support/", views.SupportQueueView.as_view()),
    path("support/<uuid:case_id>/escalate/", views.EscalateSupportView.as_view()),
    path("appointments/", views.AppointmentsView.as_view()),
    path("appointments/<uuid:appointment_id>/cancel/", views.CancelAppointmentView.as_view()),
    path("deliveries/", views.DeliveriesView.as_view()),
    path("deliveries/<uuid:notification_id>/retry/", views.RetryDeliveryView.as_view()),
    path("audit/", views.AuditView.as_view()),
    path("staff/", views.StaffView.as_view()),
    path("staff/<uuid:user_id>/grant/", views.StaffGrantView.as_view()),
]
