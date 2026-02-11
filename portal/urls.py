from django.urls import path

from portal import views

urlpatterns = [
    path("", views.LookupView.as_view(), name="lookup"),
    path(
        "<str:order_number>/articles/",
        views.ArticlesView.as_view(),
        name="articles",
    ),
]
