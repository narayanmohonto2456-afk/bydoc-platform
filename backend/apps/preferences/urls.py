from django.urls import path

from .views import (
    MyPreferenceView,
    SupportedLanguageListView,
)


app_name = "preferences"


urlpatterns = [
    path(
        "languages/",
        SupportedLanguageListView.as_view(),
        name="language-list",
    ),
    path(
        "mine/",
        MyPreferenceView.as_view(),
        name="my-preferences",
    ),
]