#!/usr/bin/env python3
"""
Check for clean boundary edges by finding coordinates exactly on boundaries.
"""

import json
import sys

def check_boundary_edges(geojson_file: str, bounds: list) -> None:
    """Check for coordinates exactly on boundary edges."""
    
    with open(geojson_file, 'r') as f:
        data = json.load(f)
    
    min_lon, min_lat, max_lon, max_lat = bounds
    tolerance = 1e-10  # Very small tolerance for floating point comparison
    
    boundary_points = {
        'left': [],    # lon = min_lon
        'right': [],   # lon = max_lon  
        'bottom': [],  # lat = min_lat
        'top': []      # lat = max_lat
    }
    
    for feature in data['features']:
        if feature['properties'].get('kind') != 'line':
            continue
            
        coords = feature['geometry']['coordinates']
        for lon, lat in coords:
            # Check if point is exactly on any boundary
            if abs(lon - min_lon) < tolerance:
                boundary_points['left'].append((lon, lat))
            elif abs(lon - max_lon) < tolerance:
                boundary_points['right'].append((lon, lat))
            
            if abs(lat - min_lat) < tolerance:
                boundary_points['bottom'].append((lon, lat))
            elif abs(lat - max_lat) < tolerance:
                boundary_points['top'].append((lon, lat))
    
    print(f"Boundary Edge Analysis")
    print(f"{'='*40}")
    print(f"Bounds: [{min_lon}, {min_lat}, {max_lon}, {max_lat}]")
    print()
    
    for edge, points in boundary_points.items():
        print(f"{edge.upper()} edge ({len(points)} points):")
        if points:
            # Show first few points
            for i, (lon, lat) in enumerate(points[:5]):
                print(f"  ({lon:.6f}, {lat:.6f})")
            if len(points) > 5:
                print(f"  ... and {len(points) - 5} more")
        else:
            print("  No points exactly on boundary")
        print()
    
    total_boundary_points = sum(len(points) for points in boundary_points.values())
    print(f"Total boundary intersection points: {total_boundary_points}")
    
    if total_boundary_points > 0:
        print("✅ CLEAN BOUNDARY INTERSECTIONS FOUND!")
    else:
        print("❌ NO BOUNDARY INTERSECTIONS - Lines may not be properly clipped")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python check_boundary_edges.py <geojson_file>")
        sys.exit(1)
    
    bounds = [-77.0, 36.0, -65.0, 42.0]
    check_boundary_edges(sys.argv[1], bounds)
