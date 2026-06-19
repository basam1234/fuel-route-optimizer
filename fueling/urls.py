from django.urls import path

from fueling.views import MapView, RouteOptimizeView

urlpatterns = [
    path("api/route/", RouteOptimizeView.as_view(), name="route-optimize"),
    path("map/", MapView.as_view(), name="map"),
]