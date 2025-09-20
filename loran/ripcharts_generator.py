"""
LORAN-C Grid Generator

Generates LORAN-C grid lines with TD calculation, calibration, and line generation.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
import json
from geopy.distance import geodesic

from .ripcharts_schemas import (
    RipChartsConfig, RegionConfig, GridLine, GridLabel, GridResult,
    CalibrationAnchor, ProcessingConfig
)


# Speed of light in km/μs
SPEED_OF_LIGHT = 0.299792458


def calculate_raw_td(
    lat: float,
    lon: float,
    master_lat: float,
    master_lon: float,
    secondary_lat: float,
    secondary_lon: float,
    emission_delay: float,
    asf: float = 0.0
) -> float:
    """Calculate raw TD value at a point."""
    # Calculate distances using geodesic
    master_dist = geodesic((lat, lon), (master_lat, master_lon)).kilometers
    secondary_dist = geodesic((lat, lon), (secondary_lat, secondary_lon)).kilometers
    
    # Calculate propagation time difference
    propagation_td = (secondary_dist - master_dist) / SPEED_OF_LIGHT
    
    # Total TD = emission_delay + propagation_delay + ASF
    return emission_delay + propagation_td + asf


def apply_calibration(
    td_grid: np.ndarray,
    lat_grid: np.ndarray,
    lon_grid: np.ndarray,
    anchors: List[CalibrationAnchor],
    pair_id: str
) -> np.ndarray:
    """Apply calibration offset from user-provided anchors."""
    if not anchors:
        return td_grid
    
    # Find all anchors that have TD values for this pair
    valid_anchors = [anchor for anchor in anchors if pair_id in anchor.td_values]
    if not valid_anchors:
        return td_grid
    
    # Calculate offsets for each anchor
    offsets = []
    for anchor in valid_anchors:
        # Find closest grid point to anchor
        distances = np.sqrt(
            (lat_grid - anchor.latitude)**2 + 
            (lon_grid - anchor.longitude)**2
        )
        min_idx = np.unravel_index(np.argmin(distances), distances.shape)
        
        # Calculate offset needed
        current_td = td_grid[min_idx]
        target_td = anchor.td_values[pair_id]
        offset = target_td - current_td
        offsets.append(offset)
    
    # Use average offset from all anchors
    avg_offset = np.mean(offsets)
    
    # Apply offset to entire grid
    return td_grid + avg_offset


def crop_to_bounds(
    coordinates: List[Tuple[float, float]],
    bounds: List[float]
) -> List[Tuple[float, float]]:
    """Simple crop: keep only points inside rectangle."""
    if not coordinates:
        return []
    
    min_lon, min_lat, max_lon, max_lat = bounds
    cropped = []
    
    for lon, lat in coordinates:
        if min_lon <= lon <= max_lon and min_lat <= lat <= max_lat:
            cropped.append((lon, lat))
    
    return cropped


def generate_contour_line(
    td_grid: np.ndarray,
    lat_grid: np.ndarray,
    lon_grid: np.ndarray,
    td_value: float
) -> List[Tuple[float, float]]:
    """Generate contour line for specific TD value."""
    try:
        import matplotlib.pyplot as plt
        
        # Create contour
        fig, ax = plt.subplots(figsize=(1, 1))
        cs = ax.contour(lon_grid, lat_grid, td_grid, levels=[td_value])
        plt.close(fig)
        
        # Extract coordinates
        coordinates = []
        for collection in cs.collections:
            for path in collection.get_paths():
                vertices = path.vertices
                coordinates.extend([(lon, lat) for lon, lat in vertices])
        
        return coordinates
        
    except ImportError:
        # Fallback: threshold-based approach
        coordinates = []
        threshold = 25.0  # μs tolerance
        
        mask = np.abs(td_grid - td_value) < threshold
        indices = np.where(mask)
        
        for i, j in zip(indices[0], indices[1]):
            lon = lon_grid[i, j]
            lat = lat_grid[i, j]
            coordinates.append((lon, lat))
        
        return coordinates


def generate_labels_for_line(
    coordinates: List[Tuple[float, float]],
    td_value: float,
    placement: List[str] = ["middle"]
) -> List[Tuple[float, float, str]]:
    """Generate labels for a line."""
    if len(coordinates) < 2:
        return []
    
    # Format label as 5-digit integer
    label = f"{int(td_value):05d}"
    labels = []
    
    if "start" in placement and coordinates:
        lon, lat = coordinates[0]
        labels.append((lon, lat, label))
    
    if "middle" in placement and len(coordinates) > 2:
        mid_idx = len(coordinates) // 2
        lon, lat = coordinates[mid_idx]
        labels.append((lon, lat, label))
    
    if "end" in placement and coordinates:
        lon, lat = coordinates[-1]
        labels.append((lon, lat, label))
    
    return labels


def generate_region_grid(
    config: RipChartsConfig,
    region_name: str
) -> GridResult:
    """Generate LORAN grid for a region."""
    if region_name not in config.regions:
        raise ValueError(f"Region '{region_name}' not found")
    
    region = config.regions[region_name]
    bounds = region.bounds  # [min_lon, min_lat, max_lon, max_lat]
    
    # Create coordinate grids with buffer for complete line generation
    resolution = config.grid_resolution
    buffer = resolution * 10
    
    extended_bounds = [
        bounds[0] - buffer, bounds[1] - buffer,
        bounds[2] + buffer, bounds[3] + buffer
    ]
    
    lon_range = np.arange(extended_bounds[0], extended_bounds[2] + resolution, resolution)
    lat_range = np.arange(extended_bounds[1], extended_bounds[3] + resolution, resolution)
    lon_grid, lat_grid = np.meshgrid(lon_range, lat_range)
    
    grid_lines = []
    grid_labels = []
    
    # Process each station pair
    for pair in region.pairs:
        chain_id = pair.chain_id
        secondary_id = pair.secondary_id
        pair_id = f"{chain_id}_{secondary_id}"
        
        if pair_id not in region.td_ranges:
            continue
        
        # Get station coordinates
        chain = config.chains[chain_id]
        master = chain.master
        secondary = chain.secondaries[secondary_id]
        
        # Calculate TD field
        td_grid = np.zeros_like(lon_grid)
        for i in range(td_grid.shape[0]):
            for j in range(td_grid.shape[1]):
                lat = lat_grid[i, j]
                lon = lon_grid[i, j]
                td_grid[i, j] = calculate_raw_td(
                    lat, lon,
                    master.latitude, master.longitude,
                    secondary.latitude, secondary.longitude,
                    secondary.emission_delay,
                    secondary.asf
                )
        
        # Apply calibration
        td_grid = apply_calibration(
            td_grid, lat_grid, lon_grid,
            region.calibration_anchors, pair_id
        )
        
        # Generate lines every 50 μs
        td_range = region.td_ranges[pair_id]
        td_values = np.arange(td_range.min_td, td_range.max_td + td_range.step, td_range.step)
        
        for td_value in td_values:
            # Generate contour line
            raw_coordinates = generate_contour_line(
                td_grid, lat_grid, lon_grid, td_value
            )
            
            if raw_coordinates:
                # Crop to bounds
                coordinates = crop_to_bounds(raw_coordinates, bounds)
                
                if len(coordinates) >= 2:  # Keep lines with at least 2 points
                    # Create grid line
                    line = GridLine(
                        chain_id=chain_id,
                        secondary_id=secondary_id,
                        family=pair.family,
                        td_value=td_value,
                        coordinates=coordinates
                    )
                    grid_lines.append(line)
                    
                    # Generate labels
                    if region.labels.enabled:
                        label_positions = generate_labels_for_line(
                            coordinates, td_value, region.labels.placement
                        )
                        
                        for lon, lat, label_text in label_positions:
                            label = GridLabel(
                                chain_id=chain_id,
                                secondary_id=secondary_id,
                                family=pair.family,
                                td_value=td_value,
                                label=label_text,
                                latitude=lat,
                                longitude=lon
                            )
                            grid_labels.append(label)
    
    return GridResult(
        region_name=region_name,
        lines=grid_lines,
        labels=grid_labels,
        metadata={
            "bounds": bounds,
            "total_lines": len(grid_lines),
            "total_labels": len(grid_labels)
        }
    )


def grid_result_to_geojson(
    result: GridResult,
    config: RipChartsConfig
) -> Dict[str, Any]:
    """Convert grid result to GeoJSON."""
    features = []
    
    # Add line features
    for line in result.lines:
        feature = {
            "type": "Feature",
            "properties": {
                "kind": "line",
                "family": line.family,
                "td": line.td_value,
                "chain_id": line.chain_id,
                "secondary_id": line.secondary_id
            },
            "geometry": {
                "type": "LineString",
                "coordinates": [[round(coord[0], 6), round(coord[1], 6)] for coord in line.coordinates]
            }
        }
        features.append(feature)
    
    # Add label features
    for label in result.labels:
        feature = {
            "type": "Feature",
            "properties": {
                "kind": "label",
                "family": label.family,
                "td": label.td_value,
                "label": label.label,
                "chain_id": label.chain_id,
                "secondary_id": label.secondary_id
            },
            "geometry": {
                "type": "Point",
                "coordinates": [round(label.longitude, 6), round(label.latitude, 6)]
            }
        }
        features.append(feature)
    
    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": result.metadata
    }


def save_geojson(data: Dict[str, Any], output_path: str) -> None:
    """Save GeoJSON data to file."""
    output_dir = Path(output_path).parent
    output_dir.mkdir(exist_ok=True, parents=True)
    
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)