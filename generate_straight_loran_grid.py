#!/usr/bin/env python3
"""
Generate simplified LORAN grid with straight lines instead of hyperbolic curves.
This matches the commercial display format shown in reference images.
"""

import json
import math
from shapely.geometry import LineString
import shapely.geometry

def load_config(filepath):
    """Loads a JSON configuration file."""
    with open(filepath, 'r') as f:
        return json.load(f)

def generate_straight_line_grid():
    """Generate straight-line LORAN grid matching the reference image."""
    
    # Load configurations
    atlantic_config = load_config('config/atlantic_config.json')
    loran_config = load_config('config/loran_config.json')
    
    # Get region bounds
    region_details = loran_config['regions']['9960xy']
    bounds = region_details['bounds']  # [min_lat, min_lon, max_lat, max_lon]
    
    features = []
    
    # Y Secondary (Carolina Beach) - Vertical lines
    # TD values: 26250 to 26950 in 50µs steps
    y_td_values = list(range(26250, 26951, 50))
    
    for td_value in y_td_values:
        # Create vertical line spanning the bounding box
        # Distribute vertical lines evenly across longitude range
        lon_fraction = (td_value - 26250) / (26950 - 26250)
        longitude = bounds[1] + lon_fraction * (bounds[3] - bounds[1])
        
        line_coords = [
            [longitude, bounds[0]],  # Bottom of bounds
            [longitude, bounds[2]]   # Top of bounds
        ]
        
        line_geom = LineString(line_coords)
        
        features.append({
            "type": "Feature",
            "geometry": shapely.geometry.mapping(line_geom),
            "properties": {
                "chain_id": "9960",
                "master_name": "Seneca, NY",
                "secondary_name": "Carolina Beach, NC",
                "secondary_id": "Y",
                "td_display": td_value,
                "line_type": "vertical"
            }
        })
    
    # X Secondary (Nantucket) - Radiating lines from master station
    # TD values: 43000 to 43800 in 50µs steps
    x_td_values = list(range(43000, 43801, 50))
    
    # Master station location (Seneca, NY)
    master_lat = 42.714088
    master_lon = -76.825919
    
    for i, td_value in enumerate(x_td_values):
        # Create lines radiating from master station
        # Each line has a different angle to create the fan pattern
        angle_start = 45  # Start angle in degrees
        angle_end = 135   # End angle in degrees
        angle = angle_start + (angle_end - angle_start) * i / (len(x_td_values) - 1)
        
        # Convert angle to radians
        angle_rad = math.radians(angle)
        
        # Calculate far point on the line
        # Use a large distance to ensure line crosses bounding box
        distance = 1000000  # 1000 km in meters, converted to degrees roughly
        distance_deg = distance / 111320  # Rough conversion to degrees
        
        end_lat = master_lat + distance_deg * math.sin(angle_rad)
        end_lon = master_lon + distance_deg * math.cos(angle_rad)
        
        line_coords = [
            [master_lon, master_lat],  # Start at master station
            [end_lon, end_lat]         # End at calculated point
        ]
        
        line_geom = LineString(line_coords)
        
        features.append({
            "type": "Feature",
            "geometry": shapely.geometry.mapping(line_geom),
            "properties": {
                "chain_id": "9960",
                "master_name": "Seneca, NY", 
                "secondary_name": "Nantucket, MA",
                "secondary_id": "X",
                "td_display": td_value,
                "line_type": "diagonal"
            }
        })
    
    # Create GeoJSON output
    geojson_output = {
        "type": "FeatureCollection",
        "features": features
    }
    
    output_path = 'loran_straight_grid_9960xy.geojson'
    with open(output_path, 'w') as f:
        json.dump(geojson_output, f, indent=2)
    
    print(f"Generated {len(features)} straight LORAN grid lines.")
    print(f"  Y secondary (vertical): {len(y_td_values)} lines")
    print(f"  X secondary (diagonal): {len(x_td_values)} lines")
    print(f"Output saved to {output_path}")

if __name__ == "__main__":
    generate_straight_line_grid()
