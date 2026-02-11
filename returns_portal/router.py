from rest_framework.routers import DefaultRouter

from portal.api import ReturnsViewSet

router = DefaultRouter()

router.register("returns", ReturnsViewSet, basename="returns")

urlpatterns = router.urls
