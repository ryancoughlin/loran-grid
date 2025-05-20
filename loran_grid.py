#!/usr/bin/env python3
"""
LORAN Grid Generator for Atlantic Region

This script generates LORAN grid data for the Atlantic region,
used by offshore fishermen for navigation.
"""

import json
import argparse
from pathlib import Path

from loran.calculator import calculate_loran_grid, calculate_td_range, calculate_hyperbolic_contours
from loran.visualizer import plot_loran_grid, plot_td_intersections
from loran.utils import generate_td_values


def load_config(config_path):
    """Load configuration from JSON file."""
    with open(config_path, 'r') as f:
        return json.load(f)


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Generate LORAN grid for Atlantic region')
    parser.add_argument('--config', type=str, default='config/atlantic_config.json',
                        help='Path to configuration file')
    parser.add_argument('--output', type=str, default='output',
                        help='Directory to save output files')
    parser.add_argument('--plot', action='store_true',
                        help='Generate visualization plot')
    parser.add_argument('--plot-intersections', action='store_true',
                        help='Generate plot of TD intersections')
    parser.add_argument('--td-step', type=int, default=500,
                        help='TD value step size for plotting (in microseconds)')
    return parser.parse_args()


def main():
    """Main entry point for the LORAN grid generator."""
    args = parse_arguments()
    
    # Ensure output directory exists
    output_dir = Path(args.output)
    output_dir.mkdir(exist_ok=True, parents=True)
    
    # Load configuration
    try:
        config = load_config(args.config)
        print(f"Loaded configuration from {args.config}")
    except FileNotFoundError:
        print(f"Configuration file not found: {args.config}")
        print("Creating a sample configuration file...")
        from loran.utils import create_sample_config
        create_sample_config(args.config)
        config = load_config(args.config)
    
    # Calculate LORAN grid
    print("Calculating LORAN grid...")
    grid_data = calculate_loran_grid(config)
    
    # Save grid data
    grid_output_path = output_dir / "grid_data.csv"
    grid_data.to_csv(grid_output_path, index=False)
    print(f"Grid data saved to {grid_output_path}")
    
    # Calculate TD ranges for each chain and secondary
    td_ranges = calculate_td_range(config)
    
    # If plotting is requested
    if args.plot:
        print("Generating visualization...")
        plot_path = output_dir / "loran_grid.png"
        plot_loran_grid(grid_data, config, plot_path)
        print(f"Plot saved to {plot_path}")
    
    # If TD intersection plotting is requested
    if args.plot_intersections:
        print("Generating TD intersection plot...")
        
        # Generate TD values to plot intersections for
        td_values = {}
        for pair, td_range in td_ranges.items():
            # Use specified step size or default
            td_range['step'] = args.td_step
            td_values[pair] = generate_td_values(td_range)
        
        # Calculate hyperbolic contours for the TD values
        contours = calculate_hyperbolic_contours(config, td_values)
        
        # Plot the intersections
        intersection_path = output_dir / "loran_intersections.png"
        plot_td_intersections(grid_data, config, td_values, intersection_path)
        print(f"Intersection plot saved to {intersection_path}")
    
    print("LORAN grid generation complete!")


if __name__ == "__main__":
    main() 