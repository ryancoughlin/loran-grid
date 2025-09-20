"""
RipCharts-compatible LORAN-C Grid Generator

Functions for creating LORAN-C grid lines that exactly match RipCharts output,
including proper TD unwrapping, calibration anchors, and label formatting.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
import json
from scipy.interpolate import griddata
from scipy.ndimage import gaussian_filter
from geopy.distance import geodesic
import concurrent.futures

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
    """
    Calculate raw TD value at a point.
    
    Args:
        lat, lon: Point coordinates
        master_lat, master_lon: Master station coordinates
        secondary_lat, secondary_lon: Secondary station coordinates
        emission_delay: Secondary emission delay (μs)
        asf: Additional Secondary Factor (μs)
    
    Returns:
        Raw TD value in microseconds
    """
    # Calculate distances using geodesic
    master_dist = geodesic((lat, lon), (master_lat, master_lon)).kilometers
    secondary_dist = geodesic((lat, lon), (secondary_lat, secondary_lon)).kilometers
    
    # Calculate propagation time difference
    propagation_td = (secondary_dist - master_dist) / SPEED_OF_LIGHT
    
    # Total TD = emission_delay + propagation_delay + ASF
    return emission_delay + propagation_td + asf


def unwrap_td_field(
    td_grid: np.ndarray,
    gri: float,
    smooth_iterations: int = 3
) -> np.ndarray:
    """
    Unwrap TD field by adding/subtracting GRI multiples for smoothness.
    
    Args:
        td_grid: 2D array of raw TD values
        gri: Group Repetition Interval (μs)
        smooth_iterations: Number of smoothing passes
    
    Returns:
        Unwrapped TD field
    """
    unwrapped = td_grid.copy()
    
    # Apply smoothing to reduce noise before unwrapping
    for _ in range(smooth_iterations):
        # Calculate gradients
        grad_y, grad_x = np.gradient(unwrapped)
        
        # Find large jumps (> GRI/2)
        jump_threshold = gri / 2
        
        # Correct jumps by adding/subtracting GRI
        large_jumps_x = np.abs(grad_x) > jump_threshold
        large_jumps_y = np.abs(grad_y) > jump_threshold
        
        # Apply corrections
        correction_x = np.round(grad_x / gri) * gri
        correction_y = np.round(grad_y / gri) * gri
        
        unwrapped[large_jumps_x] -= correction_x[large_jumps_x]
        unwrapped[large_jumps_y] -= correction_y[large_jumps_y]
        
        # Light smoothing to maintain continuity
        unwrapped = gaussian_filter(unwrapped, sigma=0.5)
    
    return unwrapped


def apply_calibration(
    td_grid: np.ndarray,
    lat_grid: np.ndarray,
    lon_grid: np.ndarray,
    anchors: List[CalibrationAnchor],
    pair_id: str
) -> np.ndarray:
    """
    Apply calibration offset based on anchor points.
    
    Args:
        td_grid: 2D array of TD values
        lat_grid: 2D array of latitudes
        lon_grid: 2D array of longitudes
        anchors: List of calibration anchor points
        pair_id: Station pair identifier (e.g., "9960_W")
    
    Returns:
        Calibrated TD field
    """
    if not anchors:
        return td_grid
    
    # Find anchors that have TD values for this pair
    valid_anchors = [a for a in anchors if pair_id in a.td_values]
    if not valid_anchors:
        return td_grid
    
    # Calculate offsets at anchor points
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
    
    # Apply average offset
    if offsets:
        avg_offset = np.mean(offsets)
        return td_grid + avg_offset
    
    return td_grid


def clip_line_to_bounds(
    coordinates: List[Tuple[float, float]],
    bounds: List[float]
) -> List[Tuple[float, float]]:
    """
    Clip a line to stay within bounding box using Sutherland-Hodgman algorithm.
    
    Args:
        coordinates: Line coordinates as (lon, lat) pairs
        bounds: [min_lon, min_lat, max_lon, max_lat]
    
    Returns:
        Clipped coordinates
    """
    if not coordinates:
        return []
    
    min_lon, min_lat, max_lon, max_lat = bounds
    clipped = []
    
    for i, (lon, lat) in enumerate(coordinates):
        # Simple bounding box clipping
        if (min_lon <= lon <= max_lon and min_lat <= lat <= max_lat):
            clipped.append((lon, lat))
        elif clipped:  # If we were inside and now outside, we're done with this segment
            # Add intersection point if needed (simplified)
            prev_lon, prev_lat = coordinates[i-1] if i > 0 else (lon, lat)
            if (min_lon <= prev_lon <= max_lon and min_lat <= prev_lat <= max_lat):
                # Calculate intersection with boundary
                if lon < min_lon:
                    intersect_lon = min_lon
                    intersect_lat = lat + (prev_lat - lat) * (min_lon - lon) / (prev_lon - lon)
                elif lon > max_lon:
                    intersect_lon = max_lon
                    intersect_lat = lat + (prev_lat - lat) * (max_lon - lon) / (prev_lon - lon)
                elif lat < min_lat:
                    intersect_lat = min_lat
                    intersect_lon = lon + (prev_lon - lon) * (min_lat - lat) / (prev_lat - lat)
                elif lat > max_lat:
                    intersect_lat = max_lat
                    intersect_lon = lon + (prev_lon - lon) * (max_lat - lat) / (prev_lat - lat)
                else:
                    continue
                
                if (min_lon <= intersect_lon <= max_lon and 
                    min_lat <= intersect_lat <= max_lat):
                    clipped.append((intersect_lon, intersect_lat))
            break
    
    return clipped


def generate_contour_line(
    td_grid: np.ndarray,
    lat_grid: np.ndarray,
    lon_grid: np.ndarray,
    td_value: float,
    bounds: List[float]
) -> List[Tuple[float, float]]:
    """
    Generate contour line for a specific TD value with bounding box clipping.
    
    Args:
        td_grid: 2D array of TD values
        lat_grid: 2D array of latitudes
        lon_grid: 2D array of longitudes
        td_value: Target TD value
        bounds: [min_lon, min_lat, max_lon, max_lat]
    
    Returns:
        List of (longitude, latitude) coordinate pairs clipped to bounds
    """
    try:
        import matplotlib.pyplot as plt
        from matplotlib.contour import QuadContourSet
        
        # Create contour
        fig, ax = plt.subplots(figsize=(1, 1))
        cs = ax.contour(lon_grid, lat_grid, td_grid, levels=[td_value])
        plt.close(fig)
        
        # Extract all coordinates first
        all_coordinates = []
        for collection in cs.collections:
            for path in collection.get_paths():
                vertices = path.vertices
                segment_coords = [(lon, lat) for lon, lat in vertices]
                if segment_coords:
                    all_coordinates.extend(segment_coords)
        
        # Apply bounding box clipping
        if all_coordinates:
            return clip_line_to_bounds(all_coordinates, bounds)
        
        return []
        
    except ImportError:
        # Fallback: simple threshold-based approach with clipping
        coordinates = []
        threshold = 25.0  # μs tolerance
        
        mask = np.abs(td_grid - td_value) < threshold
        indices = np.where(mask)
        
        for i, j in zip(indices[0], indices[1]):
            lon = lon_grid[i, j]
            lat = lat_grid[i, j]
            coordinates.append((lon, lat))
        
        # Apply bounding box clipping
        return clip_line_to_bounds(coordinates, bounds)


def generate_labels_for_line(
    coordinates: List[Tuple[float, float]],
    td_value: float,
    label_format: str,
    placement: List[str],
    min_length_km: float = 5.0
) -> List[Tuple[float, float, str]]:
    """
    Generate labels for a contour line.
    
    Args:
        coordinates: Line coordinates
        td_value: TD value
        label_format: Format string for label
        placement: Label placement positions
        min_length_km: Minimum line length for labeling
    
    Returns:
        List of (longitude, latitude, label) tuples
    """
    if len(coordinates) < 2:
        return []
    
    # Calculate line length
    total_length = 0.0
    for i in range(1, len(coordinates)):
        dist = geodesic(
            (coordinates[i-1][1], coordinates[i-1][0]),
            (coordinates[i][1], coordinates[i][0])
        ).kilometers
        total_length += dist
    
    if total_length < min_length_km:
        return []
    
    # Format label - ensure proper formatting with trailing zeros
    try:
        label = label_format.format(int(td_value))
    except (ValueError, TypeError):
        # Fallback to simple integer formatting
        label = f"{int(td_value):05d}"
    
    labels = []
    
    if "start" in placement and len(coordinates) > 0:
        lon, lat = coordinates[0]
        labels.append((lon, lat, label))
    
    if "middle" in placement and len(coordinates) > 2:
        mid_idx = len(coordinates) // 2
        lon, lat = coordinates[mid_idx]
        labels.append((lon, lat, label))
    
    if "end" in placement and len(coordinates) > 0:
        lon, lat = coordinates[-1]
        labels.append((lon, lat, label))
    
    return labels


def filter_and_process_line(
    coordinates: List[Tuple[float, float]],
    processing_config: ProcessingConfig,
    bounds: List[float]
) -> List[Tuple[float, float]]:
    """
    Filter and process a line according to processing configuration.
    
    Args:
        coordinates: Raw line coordinates
        processing_config: Processing configuration
        bounds: Bounding box for clipping
    
    Returns:
        Processed line coordinates
    """
    if not coordinates:
        return []
    
    # Apply bounding box clipping if enabled
    if processing_config.clip_to_bounds:
        coordinates = clip_line_to_bounds(coordinates, bounds)
    
    if not coordinates:
        return []
    
    # Check minimum line length
    if len(coordinates) < 2:
        return []
    
    # Calculate total line length
    total_length = 0.0
    for i in range(1, len(coordinates)):
        dist = geodesic(
            (coordinates[i-1][1], coordinates[i-1][0]),
            (coordinates[i][1], coordinates[i][0])
        ).kilometers
        total_length += dist
    
    if total_length < processing_config.min_line_length:
        return []
    
    # Limit number of segments
    if len(coordinates) > processing_config.max_line_segments:
        # Downsample by taking every nth point
        step = len(coordinates) // processing_config.max_line_segments
        coordinates = coordinates[::max(1, step)]
    
    # Simple line simplification (Douglas-Peucker would be better)
    if processing_config.simplify_tolerance > 0 and len(coordinates) > 2:
        simplified = [coordinates[0]]  # Always keep first point
        
        for i in range(1, len(coordinates) - 1):
            # Check if point is far enough from the line between previous and next
            prev_coord = simplified[-1]
            next_coord = coordinates[i + 1]
            current_coord = coordinates[i]
            
            # Simple distance check (not true perpendicular distance)
            dist_to_prev = abs(current_coord[0] - prev_coord[0]) + abs(current_coord[1] - prev_coord[1])
            if dist_to_prev > processing_config.simplify_tolerance:
                simplified.append(current_coord)
        
        simplified.append(coordinates[-1])  # Always keep last point
        coordinates = simplified
    
    return coordinates


def generate_region_grid(
    config: RipChartsConfig,
    region_name: str
) -> GridResult:
    """
    Generate complete grid for a region.
    
    Args:
        config: RipCharts configuration
        region_name: Name of region to generate
    
    Returns:
        GridResult with lines and labels
    """
    if region_name not in config.regions:
        raise ValueError(f"Region '{region_name}' not found in configuration")
    
    region = config.regions[region_name]
    bounds = region.bounds  # [min_lon, min_lat, max_lon, max_lat]
    
    # Create coordinate grids
    resolution = config.grid_resolution
    lon_range = np.arange(bounds[0], bounds[2] + resolution, resolution)
    lat_range = np.arange(bounds[1], bounds[3] + resolution, resolution)
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
        
        # Calculate raw TD field
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
        
        # Apply unwrapping if enabled
        if region.unwrapping.enabled:
            td_grid = unwrap_td_field(
                td_grid,
                region.unwrapping.gri,
                region.unwrapping.smooth_iterations
            )
        
        # Apply calibration
        td_grid = apply_calibration(
            td_grid, lat_grid, lon_grid,
            region.calibration_anchors, pair_id
        )
        
        # Generate contour lines
        td_range = region.td_ranges[pair_id]
        td_values = np.arange(td_range.min_td, td_range.max_td + td_range.step, td_range.step)
        
        for td_value in td_values:
            raw_coordinates = generate_contour_line(
                td_grid, lat_grid, lon_grid, td_value, bounds
            )
            
            if raw_coordinates:
                # Apply processing and filtering
                processing_config = region.processing or ProcessingConfig()
                coordinates = filter_and_process_line(
                    raw_coordinates, processing_config, bounds
                )
                
                if coordinates:
                    # Create grid line
                    line = GridLine(
                        chain_id=chain_id,
                        secondary_id=secondary_id,
                        family=pair.family,
                        td_value=td_value,
                        coordinates=coordinates
                    )
                    grid_lines.append(line)
                    
                    # Generate labels if enabled
                    if region.labels.enabled:
                        label_positions = generate_labels_for_line(
                            coordinates,
                            td_value,
                            td_range.format,
                            region.labels.placement,
                            region.labels.min_line_length
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
            "resolution": resolution,
            "total_lines": len(grid_lines),
            "total_labels": len(grid_labels)
        }
    )


def grid_result_to_geojson(
    result: GridResult,
    config: RipChartsConfig
) -> Dict[str, Any]:
    """
    Convert grid result to GeoJSON FeatureCollection.
    
    Args:
        result: Grid generation result
        config: RipCharts configuration
    
    Returns:
        GeoJSON FeatureCollection
    """
    features = []
    output_config = config.output
    
    # Add line features
    for line in result.lines:
        properties = {
            "kind": "line"
        }
        
        # Add requested properties
        for prop in output_config.line_properties:
            if prop == "family":
                properties[prop] = line.family
            elif prop == "td":
                properties[prop] = line.td_value
            elif prop == "chain_id":
                properties[prop] = line.chain_id
            elif prop == "secondary_id":
                properties[prop] = line.secondary_id
        
        feature = {
            "type": "Feature",
            "properties": properties,
            "geometry": {
                "type": "LineString",
                "coordinates": [[round(coord[0], output_config.coordinate_precision),
                               round(coord[1], output_config.coordinate_precision)]
                              for coord in line.coordinates]
            }
        }
        features.append(feature)
    
    # Add label features if enabled
    if output_config.include_labels:
        for label in result.labels:
            properties = {
                "kind": "label"
            }
            
            # Add requested properties
            for prop in output_config.label_properties:
                if prop == "family":
                    properties[prop] = label.family
                elif prop == "td":
                    properties[prop] = label.td_value
                elif prop == "label":
                    properties[prop] = label.label
                elif prop == "chain_id":
                    properties[prop] = label.chain_id
                elif prop == "secondary_id":
                    properties[prop] = label.secondary_id
            
            feature = {
                "type": "Feature",
                "properties": properties,
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        round(label.longitude, output_config.coordinate_precision),
                        round(label.latitude, output_config.coordinate_precision)
                    ]
                }
            }
            features.append(feature)
    
    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": result.metadata if output_config.include_metadata else None
    }


def save_geojson(data: Dict[str, Any], output_path: str) -> None:
    """
    Save GeoJSON data to a file.
    
    Args:
        data: GeoJSON data
        output_path: Output file path
    """
    output_dir = Path(output_path).parent
    output_dir.mkdir(exist_ok=True, parents=True)
    
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
