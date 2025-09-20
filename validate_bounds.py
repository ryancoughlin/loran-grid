#!/usr/bin/env python3
"""
Validate that all coordinates in GeoJSON are strictly within specified bounds.
"""

import json
import sys

def validate_bounds(geojson_file: str, expected_bounds: list) -> bool:
    """Validate all coordinates are within bounds."""
    
    with open(geojson_file, 'r') as f:
        data = json.load(f)
    
    min_lon, min_lat, max_lon, max_lat = expected_bounds
    
    violations = []
    total_coords = 0
    
    for feature in data['features']:
        geom = feature['geometry']
        
        if geom['type'] == 'LineString':
            coords = geom['coordinates']
            for lon, lat in coords:
                total_coords += 1
                if not (min_lon <= lon <= max_lon and min_lat <= lat <= max_lat):
                    violations.append((lon, lat, f"Line feature"))
        
        elif geom['type'] == 'Point':
            lon, lat = geom['coordinates']
            total_coords += 1
            if not (min_lon <= lon <= max_lon and min_lat <= lat <= max_lat):
                violations.append((lon, lat, f"Point feature"))
    
    print(f"Bounds Validation Report")
    print(f"{'='*40}")
    print(f"Expected bounds: [{min_lon}, {min_lat}, {max_lon}, {max_lat}]")
    print(f"Total coordinates checked: {total_coords}")
    print(f"Violations found: {len(violations)}")
    
    if violations:
        print(f"\n❌ VIOLATIONS:")
        for i, (lon, lat, desc) in enumerate(violations[:10]):  # Show first 10
            print(f"  {i+1}. ({lon:.6f}, {lat:.6f}) - {desc}")
        if len(violations) > 10:
            print(f"  ... and {len(violations) - 10} more")
        return False
    else:
        print(f"\n✅ ALL COORDINATES WITHIN BOUNDS!")
        return True

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python validate_bounds.py <geojson_file>")
        sys.exit(1)
    
    # New England bounds
    bounds = [-77.0, 36.0, -65.0, 42.0]
    
    success = validate_bounds(sys.argv[1], bounds)
    sys.exit(0 if success else 1)
