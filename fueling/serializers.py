from rest_framework import serializers


class RouteRequestSerializer(serializers.Serializer):
    start = serializers.CharField(allow_blank=False, trim_whitespace=True)
    finish = serializers.CharField(allow_blank=False, trim_whitespace=True)


class EndpointSerializer(serializers.Serializer):
    query = serializers.CharField()
    lat = serializers.FloatField()
    lng = serializers.FloatField()


class RouteGeometrySerializer(serializers.Serializer):
    total_distance_miles = serializers.FloatField()
    geometry = serializers.JSONField()


class FuelStopSerializer(serializers.Serializer):
    opis_id = serializers.IntegerField()
    name = serializers.CharField()
    city = serializers.CharField()
    state = serializers.CharField()
    price_per_gallon = serializers.FloatField()
    miles_along_route = serializers.FloatField()
    gallons_purchased = serializers.FloatField()
    leg_cost = serializers.FloatField()


class ExternalCallsSerializer(serializers.Serializer):
    geocoding = serializers.IntegerField()
    routing = serializers.IntegerField()


class RouteOptimizeResponseSerializer(serializers.Serializer):
    start = EndpointSerializer()
    finish = EndpointSerializer()
    route = RouteGeometrySerializer()
    fuel_stops = FuelStopSerializer(many=True)
    total_gallons = serializers.FloatField()
    total_fuel_cost = serializers.FloatField()
    map_url = serializers.CharField()
    external_calls = ExternalCallsSerializer()