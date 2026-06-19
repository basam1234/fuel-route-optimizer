from django.urls import path
from django.views.generic import RedirectView
from fueling.views import MapView, RouteOptimizeView

urlpatterns = [
    path("", RedirectView.as_view(url="/map/", permanent=False)),
    path("api/route/", RouteOptimizeView.as_view(), name="route-optimize"),
    path("map/", MapView.as_view(), name="map"),
]