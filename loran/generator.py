"""
LORAN-C Grid Generator

Functions for creating LORAN-C grid lines based on configuration and physics calculations.
"""

import json
from typing import Dict, List, Tuple, Optional, Any
import concurrent.futures
from pathlib import Path

from .schemas import LORConfig, StationPair, GridLine, TDRange
from .physics import (
    calculate_td_range,
    generate_td_values,
    sample_hyperbola,
)


def load_config(config_path: str) -> LORConfig:
    """
    Load LORAN-C configuration from a JSON file.
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        LORConfig object
        
    Raises:
        FileNotFoundError: If the configuration file doesn't exist
        ValueError: If the configuration is invalid
    """
    try:
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        
        return LORConfig(**config_data)
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    except Exception as e:
        raise ValueError(f"Invalid configuration: {e}")


def calculate_td_ranges(config: LORConfig) -> Dict[str, TDRange]:
    """
    Calculate TD ranges for each master-secondary pair.
    
    Args:
        config: LORAN-C configuration
        
    Returns:
        Dictionary mapping pair identifiers to TD ranges
    """
    td_ranges = {}
    bbox = config.get_bounding_box().to_list()
    
    for pair in config.station_pairs:
        chain_id = pair.chain_id
        secondary_id = pair.secondary_id
        
        chain = config.chains[chain_id]
        master = chain.master
        secondary = chain.secondaries[secondary_id]
        
        min_td, max_td = calculate_td_range(
            master.latitude,
            master.longitude,
            secondary.latitude,
            secondary.longitude,
            bbox,
            secondary.emission_delay,
        )
        
        pair_id = f"{chain_id}_{secondary_id}"
        td_ranges[pair_id] = TDRange(
            min_td=min_td,
            max_td=max_td,
            step=config.grid_spacing
        )
    
    return td_ranges


def generate_grid_line(
    config: LORConfig,
    chain_id: str,
    secondary_id: str,
    td_value: float,
) -> Optional[GridLine]:
    """
    Generate a single grid line for a given TD value.
    
    Args:
        config: LORAN-C configuration
        chain_id: Chain identifier
        secondary_id: Secondary station identifier
        td_value: TD value in microseconds
        
    Returns:
        GridLine object or None if no points were found
    """
    chain = config.chains[chain_id]
    master = chain.master
    secondary = chain.secondaries[secondary_id]
    bbox = config.get_bounding_box().to_list()
    
    # Sample the hyperbola
    points = sample_hyperbola(
        master.latitude,
        master.longitude,
        secondary.latitude,
        secondary.longitude,
        td_value,
        secondary.emission_delay,
        secondary.asf,
        bbox,
    )
    
    if not points:
        return None
    
    return GridLine(
        chain_id=chain_id,
        secondary_id=secondary_id,
        td_value=td_value,
        coordinates=points,
    )


def generate_grid_lines(
    config: LORConfig,
    td_ranges: Optional[Dict[str, TDRange]] = None,
) -> List[GridLine]:
    """
    Generate all grid lines based on configuration.
    
    Args:
        config: LORAN-C configuration
        td_ranges: Optional TD ranges (if not provided, will be calculated)
        
    Returns:
        List of GridLine objects
    """
    if td_ranges is None:
        td_ranges = calculate_td_ranges(config)
    
    grid_lines = []
    
    # Process each station pair
    for pair in config.station_pairs:
        chain_id = pair.chain_id
        secondary_id = pair.secondary_id
        pair_id = f"{chain_id}_{secondary_id}"
        
        if pair_id not in td_ranges:
            continue
        
        td_range = td_ranges[pair_id]
        td_values = generate_td_values(
            td_range.min_td,
            td_range.max_td,
            td_range.step,
        )
        
        # Process each TD value
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(
                    generate_grid_line,
                    config,
                    chain_id,
                    secondary_id,
                    td_value,
                )
                for td_value in td_values
            ]
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    line = future.result()
                    if line:
                        grid_lines.append(line)
                except Exception as e:
                    print(f"Error generating grid line: {e}")
    
    return grid_lines


def generate_region_grid_lines(
    config: LORConfig,
    region_code: str,
) -> List[GridLine]:
    """
    Generate grid lines for a specific region.
    
    Args:
        config: LORAN-C configuration
        region_code: Region code (e.g., "9960wy")
        
    Returns:
        List of GridLine objects
        
    Raises:
        ValueError: If the region code is invalid
    """
    raw_config = None
    
    # The config dict has regions but Pydantic doesn't know about them
    # Get the raw config data to access regions
    with open('config/loran_config.json', 'r') as f:
        raw_config = json.load(f)
    
    if not raw_config or 'regions' not in raw_config or region_code not in raw_config['regions']:
        raise ValueError(f"Invalid region code: {region_code}")
    
    region = raw_config['regions'][region_code]
    
    # Create a modified config with the region's bounds and pairs
    modified_config = LORConfig(
        bounds=region['bounds'],
        grid_spacing=config.grid_spacing,
        chains=config.chains,
        station_pairs=region['pairs'],
    )
    
    return generate_grid_lines(modified_config)


def grid_lines_to_geojson(grid_lines: List[GridLine]) -> Dict[str, Any]:
    """
    Convert grid lines to GeoJSON FeatureCollection.
    
    Args:
        grid_lines: List of GridLine objects
        
    Returns:
        GeoJSON FeatureCollection as dictionary
    """
    features = []
    
    for line in grid_lines:
        # Create a clean feature for each TD line
        feature = {
            "type": "Feature",
            "properties": {
                "chain": line.chain_id,
                "secondary": line.secondary_id,
                "td": line.td_value,
                "label": f"{int(line.td_value)} µs"
            },
            "geometry": {
                "type": "LineString",
                "coordinates": line.coordinates
            }
        }
        features.append(feature)
    
    return {
        "type": "FeatureCollection",
        "features": features
    }


def save_geojson(data: Dict[str, Any], output_path: str) -> None:
    """
    Save GeoJSON data to a file.
    
    Args:
        data: GeoJSON data as dictionary
        output_path: Path to save the GeoJSON file
    """
    # Ensure output directory exists
    output_dir = Path(output_path).parent
    output_dir.mkdir(exist_ok=True, parents=True)
    
    # Save the file
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2) 