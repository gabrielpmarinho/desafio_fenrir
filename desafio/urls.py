from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("ordens/", views.ordens, name="ordens"),
    path(
        "ordens/<int:ordem_id>/cancelar/",
        views.cancelar_ordem,
        name="cancelar_ordem",
    ),
    path("ranking/", views.ranking, name="ranking"),
    path("extrato/", views.extrato, name="extrato"),
]
