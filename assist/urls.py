from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.Health.as_view()),
    path("widget.js", views.widget_js),
    path("api/sessions/", views.SessionStart.as_view()),
    path("api/sessions/<uuid:pk>/messages/", views.SessionMessages.as_view()),
    path("api/sessions/<uuid:pk>/actions/<uuid:action_id>/", views.SessionAction.as_view()),
    path("api/sessions/<uuid:pk>/escalate/", views.SessionEscalate.as_view()),
    path("api/sessions/<uuid:pk>/end/", views.SessionEnd.as_view()),
    path("api/sessions/<uuid:pk>/messages/<int:message_id>/feedback/", views.MessageFeedback.as_view()),
    path("api/admin/sessions/", views.AdminSessions.as_view()),
    path("api/admin/sessions/<uuid:pk>/", views.AdminSessionDetail.as_view()),
]
