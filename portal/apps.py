from django.apps import AppConfig
from django.utils.module_loading import autodiscover_modules


class PortalConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "portal"

    def ready(self) -> None:
        autodiscover_modules("api")
