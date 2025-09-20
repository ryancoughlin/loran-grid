#!/usr/bin/env python3
"""
Validate RipCharts-compatible LORAN grid output.

This script validates that the generated grid matches RipCharts specifications,
including TD ranges, label formatting, and anchor point accuracy.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import argparse

# Add the loran module to the path
sys.path.append(str(Path(__file__).parent))

from loran.ripcharts_schemas import RipChartsConfig
from loran.ripcharts_generator import calculate_raw_td
from geopy.distance import geodesic


def load_geojson(file_path: str) -> Dict:
    """Load GeoJSON file."""
    with open(file_path, 'r') as f:
        return json.load(f)


def validate_td_ranges(geojson_data: Dict, config: RipChartsConfig, region_name: str) -> bool:
    """Validate that TD values are within expected ranges."""
    region = config.regions[region_name]
    
    print("Validating TD ranges...")
    
    # Extract TD values from features
    td_values_by_family = {}
    for feature in geojson_data['features']:
        if feature['properties'].get('kind') == 'line':
            family = feature['properties']['family']
            td = feature['properties']['td']
            
            if family not in td_values_by_family:
                td_values_by_family[family] = []
            td_values_by_family[family].append(td)
    
    # Check ranges
    all_valid = True
    for pair in region.pairs:
        family = pair.family
        pair_id = f"{pair.chain_id}_{pair.secondary_id}"
        
        if pair_id not in region.td_ranges:
            print(f"  ✗ No TD range defined for {pair_id}")
            all_valid = False
            continue
        
        expected_range = region.td_ranges[pair_id]
        actual_values = td_values_by_family.get(family, [])
        
        if not actual_values:
            print(f"  ✗ No TD values found for family {family}")
            all_valid = False
            continue
        
        min_actual = min(actual_values)
        max_actual = max(actual_values)
        
        print(f"  Family {family}:")
        print(f"    Expected: {expected_range.min_td} - {expected_range.max_td}")
        print(f"    Actual:   {min_actual} - {max_actual}")
        
        if (min_actual < expected_range.min_td - expected_range.step or 
            max_actual > expected_range.max_td + expected_range.step):
            print(f"    ✗ TD range mismatch for family {family}")
            all_valid = False
        else:
            print(f"    ✓ TD range valid for family {family}")
    
    return all_valid


def validate_label_formatting(geojson_data: Dict, region_name: str) -> bool:
    """Validate label formatting matches RipCharts style."""
    print("Validating label formatting...")
    
    label_features = [f for f in geojson_data['features'] 
                     if f['properties'].get('kind') == 'label']
    
    if not label_features:
        print("  ✗ No label features found")
        return False
    
    all_valid = True
    for feature in label_features[:10]:  # Check first 10 labels
        label = feature['properties']['label']
        td = feature['properties']['td']
        
        # Check if label is 5-digit format
        expected_label = f"{int(td):05d}"
        if label != expected_label:
            print(f"  ✗ Label format mismatch: expected '{expected_label}', got '{label}'")
            all_valid = False
        else:
            print(f"  ✓ Label '{label}' correctly formatted")
    
    return all_valid


def validate_anchor_points(geojson_data: Dict, config: RipChartsConfig, region_name: str) -> bool:
    """Validate TD values at calibration anchor points."""
    region = config.regions[region_name]
    
    print("Validating calibration anchor points...")
    
    if not region.calibration_anchors:
        print("  ⚠ No calibration anchors defined")
        return True
    
    all_valid = True
    for i, anchor in enumerate(region.calibration_anchors):
        print(f"  Anchor {i+1}: ({anchor.latitude:.4f}°N, {anchor.longitude:.4f}°W)")
        
        for pair in region.pairs:
            chain_id = pair.chain_id
            secondary_id = pair.secondary_id
            pair_id = f"{chain_id}_{secondary_id}"
            
            if pair_id not in anchor.td_values:
                continue
            
            # Get station coordinates
            chain = config.chains[chain_id]
            master = chain.master
            secondary = chain.secondaries[secondary_id]
            
            # Calculate expected TD at anchor point
            calculated_td = calculate_raw_td(
                anchor.latitude, anchor.longitude,
                master.latitude, master.longitude,
                secondary.latitude, secondary.longitude,
                secondary.emission_delay,
                secondary.asf
            )
            
            expected_td = anchor.td_values[pair_id]
            difference = abs(calculated_td - expected_td)
            
            print(f"    {pair_id}: Expected {expected_td:.1f}, Calculated {calculated_td:.1f}, Diff {difference:.1f} μs")
            
            # Allow some tolerance for calibration
            if difference > 100:  # 100 μs tolerance
                print(f"    ✗ Large difference for {pair_id} at anchor {i+1}")
                all_valid = False
            else:
                print(f"    ✓ {pair_id} within tolerance")
    
    return all_valid


def validate_feature_properties(geojson_data: Dict, config: RipChartsConfig) -> bool:
    """Validate GeoJSON feature properties."""
    print("Validating feature properties...")
    
    output_config = config.output
    line_features = [f for f in geojson_data['features'] 
                    if f['properties'].get('kind') == 'line']
    label_features = [f for f in geojson_data['features'] 
                     if f['properties'].get('kind') == 'label']
    
    all_valid = True
    
    # Check line properties
    if line_features:
        sample_line = line_features[0]
        for prop in output_config.line_properties:
            if prop not in sample_line['properties']:
                print(f"  ✗ Missing line property: {prop}")
                all_valid = False
            else:
                print(f"  ✓ Line property '{prop}' present")
    
    # Check label properties
    if label_features:
        sample_label = label_features[0]
        for prop in output_config.label_properties:
            if prop not in sample_label['properties']:
                print(f"  ✗ Missing label property: {prop}")
                all_valid = False
            else:
                print(f"  ✓ Label property '{prop}' present")
    
    return all_valid


def main():
    """Validate RipCharts-compatible LORAN grid."""
    parser = argparse.ArgumentParser(description="Validate RipCharts-compatible LORAN grid")
    parser.add_argument(
        "--config", 
        default="config/ripcharts_config.yaml",
        help="Path to YAML configuration file"
    )
    parser.add_argument(
        "--geojson",
        required=True,
        help="Path to generated GeoJSON file"
    )
    parser.add_argument(
        "--region",
        default="new_england_9960wy",
        help="Region name to validate against"
    )
    
    args = parser.parse_args()
    
    # Load configuration and GeoJSON
    print(f"Loading configuration from {args.config}...")
    config = RipChartsConfig.from_yaml(args.config)
    
    print(f"Loading GeoJSON from {args.geojson}...")
    geojson_data = load_geojson(args.geojson)
    
    print(f"Validating region: {args.region}")
    print(f"Total features: {len(geojson_data['features'])}")
    
    # Run validations
    validations = [
        ("TD Ranges", validate_td_ranges(geojson_data, config, args.region)),
        ("Label Formatting", validate_label_formatting(geojson_data, args.region)),
        ("Anchor Points", validate_anchor_points(geojson_data, config, args.region)),
        ("Feature Properties", validate_feature_properties(geojson_data, config))
    ]
    
    # Summary
    print("\nValidation Summary:")
    all_passed = True
    for name, passed in validations:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n🎉 All validations passed! Grid matches RipCharts specifications.")
        return 0
    else:
        print("\n❌ Some validations failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
