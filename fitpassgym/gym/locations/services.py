from math import asin, cos, radians, sin, sqrt


def find_nearby_gyms(queryset, latitude, longitude, radius_km=25):
    """Return active gyms within the radius, ordered by Haversine distance."""
    def distance(gym):
        values = (float(latitude), float(longitude), float(gym.latitude), float(gym.longitude))
        lat1, lon1, lat2, lon2 = map(radians, values)
        delta_lat = sin((lat2 - lat1) / 2) ** 2
        delta_lon = cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
        return 6371 * 2 * asin(sqrt(delta_lat + delta_lon))

    results = ((gym, distance(gym)) for gym in queryset.filter(active=True))
    return sorted(
        ((gym, km) for gym, km in results if km <= float(radius_km)),
        key=lambda item: item[1],
    )
