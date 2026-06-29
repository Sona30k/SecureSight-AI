def point_feature(longitude: float, latitude: float, properties: dict) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
        "properties": properties,
    }
