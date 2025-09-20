#!/usr/bin/env python3
"""
Generate RipCharts-compatible LORAN grid for New England 9960 WY region.

This script generates a LORAN grid that exactly matches RipCharts output,
including proper TD unwrapping, calibration anchors, and label formatting.
"""

import sys
from pathlib import Path
import argparse

# Add the loran module to the path
sys.path.append(str(Path(__file__).parent))

from loran.ripcharts_schemas import RipChartsConfig
from loran.ripcharts_generator import generate_region_grid, grid_result_to_geojson, save_geojson


def main():
    """Generate RipCharts-compatible LORAN grid."""
    parser = argparse.ArgumentParser(description="Generate RipCharts-compatible LORAN grid")
    parser.add_argument(
        "--config", 
        default="config/ripcharts_config.yaml",
        help="Path to YAML configuration file"
    )
    parser.add_argument(
        "--region",
        default="new_england_9960wy",
        help="Region to generate (default: new_england_9960wy)"
    )
    parser.add_argument(
        "--output",
        help="Output GeoJSON file path (default: auto-generated)"
    )
    
    args = parser.parse_args()
    
    # Load configuration
    print(f"Loading configuration from {args.config}...")
    try:
        config = RipChartsConfig.from_yaml(args.config)
        print(f"✓ Configuration loaded successfully")
    except Exception as e:
        print(f"✗ Error loading configuration: {e}")
        return 1
    
    # Validate region
    if args.region not in config.regions:
        print(f"✗ Region '{args.region}' not found in configuration")
        print(f"Available regions: {list(config.regions.keys())}")
        return 1
    
    region_config = config.regions[args.region]
    print(f"✓ Region '{region_config.name}' ({region_config.display_name}) selected")
    
    # Generate output filename if not provided
    if not args.output:
        args.output = f"output/loran_grid_{region_config.display_name}_ripcharts.geojson"
    
    print(f"Generating grid for region: {region_config.name}")
    print(f"Bounds: {region_config.bounds}")
    print(f"Station pairs: {len(region_config.pairs)}")
    
    # Generate grid
    try:
        print("Generating grid lines and labels...")
        result = generate_region_grid(config, args.region)
        print(f"✓ Generated {len(result.lines)} lines and {len(result.labels)} labels")
        
        # Convert to GeoJSON
        print("Converting to GeoJSON...")
        geojson_data = grid_result_to_geojson(result, config)
        print(f"✓ Created GeoJSON with {len(geojson_data['features'])} features")
        
        # Save to file
        print(f"Saving to {args.output}...")
        save_geojson(geojson_data, args.output)
        print(f"✓ Grid saved successfully")
        
        # Print summary
        print("\nGeneration Summary:")
        print(f"  Region: {result.region_name}")
        print(f"  Grid lines: {len(result.lines)}")
        print(f"  Labels: {len(result.labels)}")
        print(f"  Output file: {args.output}")
        print(f"  File size: {Path(args.output).stat().st_size / 1024:.1f} KB")
        
        return 0
        
    except Exception as e:
        print(f"✗ Error generating grid: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
