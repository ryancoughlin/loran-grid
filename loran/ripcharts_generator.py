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
    """Clean crop: clip lines to bounding box with proper intersections."""
    if not coordinates or len(coordinates) < 2:
        return []
    
    min_lon, min_lat, max_lon, max_lat = bounds
    cropped = []
    
    # Process line segments
    for i in range(len(coordinates) - 1):
        p1 = coordinates[i]
        p2 = coordinates[i + 1]
        
        # Clip line segment to bounds using Cohen-Sutherland algorithm
        clipped_segment = clip_line_segment(p1, p2, min_lon, min_lat, max_lon, max_lat)
        
        if clipped_segment:
            # Add start point if it's the first segment or if it's different from last point
            if not cropped or cropped[-1] != clipped_segment[0]:
                cropped.append(clipped_segment[0])
            
            # Add end point
            cropped.append(clipped_segment[1])
    
    return cropped


def clip_line_segment(p1: Tuple[float, float], p2: Tuple[float, float], 
                     min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> Optional[List[Tuple[float, float]]]:
    """Clip a line segment to a rectangle using Cohen-Sutherland algorithm."""
    x1, y1 = p1
    x2, y2 = p2
    
    # Compute region codes for both points
    def compute_code(x, y):
        code = 0
        if x < min_lon: code |= 1  # left
        if x > max_lon: code |= 2  # right
        if y < min_lat: code |= 4  # bottom
        if y > max_lat: code |= 8  # top
        return code
    
    code1 = compute_code(x1, y1)
    code2 = compute_code(x2, y2)
    
    while True:
        # Both points inside rectangle
        if code1 == 0 and code2 == 0:
            return [(x1, y1), (x2, y2)]
        
        # Both points outside rectangle on same side
        if code1 & code2 != 0:
            return None
        
        # At least one point is outside, clip it
        code_out = code1 if code1 != 0 else code2
        
        # Find intersection point
        if code_out & 8:  # top
            x = x1 + (x2 - x1) * (max_lat - y1) / (y2 - y1)
            y = max_lat
        elif code_out & 4:  # bottom
            x = x1 + (x2 - x1) * (min_lat - y1) / (y2 - y1)
            y = min_lat
        elif code_out & 2:  # right
            y = y1 + (y2 - y1) * (max_lon - x1) / (x2 - x1)
            x = max_lon
        elif code_out & 1:  # left
            y = y1 + (y2 - y1) * (min_lon - x1) / (x2 - x1)
            x = min_lon
        
        # Update the point outside the rectangle
        if code_out == code1:
            x1, y1 = x, y
            code1 = compute_code(x1, y1)
        else:
            x2, y2 = x, y
            code2 = compute_code(x2, y2)


def generate_contour_line(
    td_grid: np.ndarray,
    lat_grid: np.ndarray,
    lon_grid: np.ndarray,
    td_value: float
) -> List[Tuple[float, float]]:
    """Generate contour line for specific TD value using matplotlib contouring."""
    try:
        import matplotlib.pyplot as plt
        
        # Create contour with higher resolution for smoother lines
        fig, ax = plt.subplots(figsize=(1, 1))
        
        # Use contour with specific level and higher resolution
        cs = ax.contour(lon_grid, lat_grid, td_grid, levels=[td_value], colors='black')
        plt.close(fig)
        
        # Extract coordinates from contour collections
        coordinates = []
        for collection in cs.collections:
            for path in collection.get_paths():
                vertices = path.vertices
                if len(vertices) > 1:  # Only keep paths with multiple points
                    # Convert to (lon, lat) tuples
                    for vertex in vertices:
                        lon, lat = vertex[0], vertex[1]
                        coordinates.append((lon, lat))
        
        return coordinates
        
    except Exception as e:
        print(f"Warning: Contour generation failed for TD {td_value}: {e}")
        # Fallback: return empty list
        return []


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
    
    # Create coordinate grids with large buffer for complete line generation
    resolution = config.grid_resolution
    buffer = resolution * 50  # Much larger buffer to capture full TD range
    
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