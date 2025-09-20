#!/usr/bin/env python3
"""
Analyze LORAN grid coverage and show improvements.
"""

import json
import sys
from collections import defaultdict

def analyze_geojson(file_path: str) -> dict:
    """Analyze GeoJSON file and return coverage statistics."""
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    stats = {
        'total_features': len(data['features']),
        'lines': 0,
        'labels': 0,
        'families': defaultdict(list),
        'bounds': {'min_lon': float('inf'), 'max_lon': float('-inf'),
                  'min_lat': float('inf'), 'max_lat': float('-inf')}
    }
    
    for feature in data['features']:
        props = feature['properties']
        
        if props.get('kind') == 'line':
            stats['lines'] += 1
            family = props.get('family')
            td = props.get('td')
            if family and td:
                stats['families'][family].append(td)
            
            # Update bounds from coordinates
            coords = feature['geometry']['coordinates']
            for lon, lat in coords:
                stats['bounds']['min_lon'] = min(stats['bounds']['min_lon'], lon)
                stats['bounds']['max_lon'] = max(stats['bounds']['max_lon'], lon)
                stats['bounds']['min_lat'] = min(stats['bounds']['min_lat'], lat)
                stats['bounds']['max_lat'] = max(stats['bounds']['max_lat'], lat)
        
        elif props.get('kind') == 'label':
            stats['labels'] += 1
    
    # Calculate family ranges
    for family, tds in stats['families'].items():
        stats['families'][family] = {
            'min': min(tds),
            'max': max(tds),
            'count': len(tds),
            'range': max(tds) - min(tds)
        }
    
    return stats

def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_coverage.py <geojson_file> [comparison_file]")
        return 1
    
    primary_file = sys.argv[1]
    comparison_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    print(f"Analyzing: {primary_file}")
    primary_stats = analyze_geojson(primary_file)
    
    print(f"\n📊 Coverage Analysis")
    print(f"{'='*50}")
    print(f"Total Features: {primary_stats['total_features']}")
    print(f"Grid Lines: {primary_stats['lines']}")
    print(f"Labels: {primary_stats['labels']}")
    
    print(f"\n🗺️  Geographic Bounds:")
    bounds = primary_stats['bounds']
    print(f"  Longitude: {bounds['min_lon']:.3f}° to {bounds['max_lon']:.3f}°")
    print(f"  Latitude:  {bounds['min_lat']:.3f}° to {bounds['max_lat']:.3f}°")
    print(f"  Width:     {bounds['max_lon'] - bounds['min_lon']:.3f}°")
    print(f"  Height:    {bounds['max_lat'] - bounds['min_lat']:.3f}°")
    
    print(f"\n📈 Family Coverage:")
    for family, data in primary_stats['families'].items():
        print(f"  {family}-family: {data['min']:.0f} → {data['max']:.0f} μs")
        print(f"    Lines: {data['count']}, Range: {data['range']:.0f} μs")
    
    if comparison_file:
        print(f"\n🔄 Comparison with: {comparison_file}")
        comp_stats = analyze_geojson(comparison_file)
        
        print(f"{'Metric':<20} {'Before':<15} {'After':<15} {'Change':<15}")
        print(f"{'-'*65}")
        
        # Feature counts
        print(f"{'Total Features':<20} {comp_stats['total_features']:<15} {primary_stats['total_features']:<15} {primary_stats['total_features'] - comp_stats['total_features']:+d}")
        print(f"{'Grid Lines':<20} {comp_stats['lines']:<15} {primary_stats['lines']:<15} {primary_stats['lines'] - comp_stats['lines']:+d}")
        print(f"{'Labels':<20} {comp_stats['labels']:<15} {primary_stats['labels']:<15} {primary_stats['labels'] - comp_stats['labels']:+d}")
        
        # Family ranges
        print(f"\n📊 Family Range Changes:")
        for family in primary_stats['families']:
            if family in comp_stats['families']:
                before = comp_stats['families'][family]
                after = primary_stats['families'][family]
                print(f"  {family}-family:")
                print(f"    Range: {before['range']:.0f} → {after['range']:.0f} μs ({after['range'] - before['range']:+.0f})")
                print(f"    Lines: {before['count']} → {after['count']} ({after['count'] - before['count']:+d})")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
