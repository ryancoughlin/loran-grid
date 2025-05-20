"""
LORAN-C Physics module.

This module contains the core physics constants and calculations for LORAN-C grids.
All functions are pure and stateless.
"""

from typing import List, Tuple, Dict
import math
import numpy as np
from pyproj import Geod

# Physical constants for LORAN-C calculations
SPEED_OF_LIGHT = 299792458.0  # m/s
SPEED_OF_LIGHT_MICROSEC = 299.792458  # km/μs (in vacuum)
PROPAGATION_FACTOR = 1.0003  # Refractive index adjustment for atmosphere


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate great-circle distance between two points in kilometers.
    
    Args:
        lat1: Latitude of first point in decimal degrees
        lon1: Longitude of first point in decimal degrees
        lat2: Latitude of second point in decimal degrees
        lon2: Longitude of second point in decimal degrees
        
    Returns:
        Distance in kilometers
    """
    geod = Geod(ellps="WGS84")
    _, _, distance = geod.inv(lon1, lat1, lon2, lat2)
    return distance / 1000.0  # Convert meters to kilometers


def calculate_time_difference(
    master_lat: float,
    master_lon: float,
    secondary_lat: float,
    secondary_lon: float,
    point_lat: float,
    point_lon: float,
    emission_delay: float,
    asf: float = 0.0,
) -> float:
    """
    Calculate the Time Difference (TD) for a point relative to a master-secondary pair.
    
    Args:
        master_lat: Master station latitude
        master_lon: Master station longitude
        secondary_lat: Secondary station latitude
        secondary_lon: Secondary station longitude
        point_lat: Point latitude
        point_lon: Point longitude
        emission_delay: Secondary emission delay in microseconds
        asf: Additional Secondary Factor correction
        
    Returns:
        Time Difference (TD) in microseconds
    """
    # Calculate distances from point to each station
    dist_to_master = calculate_distance(
        point_lat, point_lon, master_lat, master_lon
    )
    dist_to_secondary = calculate_distance(
        point_lat, point_lon, secondary_lat, secondary_lon
    )
    
    # Convert distances to propagation times
    # Use PROPAGATION_FACTOR to account for atmospheric effects
    time_to_master = (dist_to_master / SPEED_OF_LIGHT_MICROSEC) * PROPAGATION_FACTOR
    time_to_secondary = (dist_to_secondary / SPEED_OF_LIGHT_MICROSEC) * PROPAGATION_FACTOR
    
    # Calculate TD including the emission delay and ASF correction
    td = (time_to_secondary - time_to_master) + emission_delay + asf
    
    return td


def calculate_td_range(
    master_lat: float,
    master_lon: float,
    secondary_lat: float,
    secondary_lon: float,
    bbox: Tuple[float, float, float, float],
    emission_delay: float,
    buffer: float = 2000.0,
) -> Tuple[float, float]:
    """
    Calculate the range of TD values that cover a bounding box.
    
    Args:
        master_lat: Master station latitude
        master_lon: Master station longitude
        secondary_lat: Secondary station latitude
        secondary_lon: Secondary station longitude
        bbox: Bounding box as (min_lat, min_lon, max_lat, max_lon)
        emission_delay: Secondary emission delay in microseconds
        buffer: Additional buffer in microseconds to ensure coverage
        
    Returns:
        Tuple of (min_td, max_td) in microseconds
    """
    # Get corner points of the bounding box
    corners = [
        (bbox[0], bbox[1]),  # SW corner
        (bbox[0], bbox[3]),  # SE corner
        (bbox[2], bbox[1]),  # NW corner
        (bbox[2], bbox[3]),  # NE corner
    ]
    
    # Calculate TD values at each corner
    td_values = []
    for corner_lat, corner_lon in corners:
        td = calculate_time_difference(
            master_lat,
            master_lon,
            secondary_lat,
            secondary_lon,
            corner_lat,
            corner_lon,
            emission_delay,
        )
        td_values.append(td)
    
    # Add buffer to ensure coverage
    min_td = min(td_values) - buffer
    max_td = max(td_values) + buffer
    
    return min_td, max_td


def generate_td_values(min_td: float, max_td: float, step: float = 100.0) -> List[float]:
    """
    Generate a list of TD values at the specified interval.
    
    Args:
        min_td: Minimum TD value in microseconds
        max_td: Maximum TD value in microseconds
        step: Step size in microseconds
        
    Returns:
        List of TD values
    """
    # Standard TD values that should always be included
    standard_tds = [0.0, 13800.0]  # Add common TD values from your example
    
    # Round to nearest step multiple
    min_td_rounded = math.ceil(min_td / step) * step
    max_td_rounded = math.floor(max_td / step) * step
    
    # Generate the values
    values = np.arange(min_td_rounded, max_td_rounded + step, step).tolist()
    
    # Add standard values if they're in the range
    for td in standard_tds:
        if min_td <= td <= max_td and td not in values:
            values.append(td)
    
    # Sort the values
    values.sort()
    
    return values


def sample_hyperbola(
    master_lat: float,
    master_lon: float,
    secondary_lat: float,
    secondary_lon: float,
    td_value: float,
    emission_delay: float,
    asf: float,
    bbox: Tuple[float, float, float, float],
    num_points: int = 100,
) -> List[Tuple[float, float]]:
    """
    Sample points along a hyperbolic curve with constant TD.
    
    This function samples points along a hyperbolic line where the
    Time Difference between master and secondary stations is constant.
    
    Args:
        master_lat: Master station latitude
        master_lon: Master station longitude
        secondary_lat: Secondary station latitude
        secondary_lon: Secondary station longitude
        td_value: The constant TD value in microseconds
        emission_delay: Secondary emission delay in microseconds
        asf: Additional Secondary Factor correction
        bbox: Bounding box as (min_lat, min_lon, max_lat, max_lon)
        num_points: Number of sample points
        
    Returns:
        List of (longitude, latitude) points along the hyperbola
    """
    min_lat, min_lon, max_lat, max_lon = bbox
    
    # Generate evenly spaced points across the grid
    grid_size = int(math.sqrt(num_points * 10))
    lat_steps = np.linspace(min_lat, max_lat, grid_size)
    lon_steps = np.linspace(min_lon, max_lon, grid_size)
    
    # For each point, calculate the TD value
    points = []
    for lat in lat_steps:
        for lon in lon_steps:
            actual_td = calculate_time_difference(
                master_lat, master_lon,
                secondary_lat, secondary_lon,
                lat, lon, emission_delay, asf,
            )
            # If this point is close to our target TD value, keep it
            if abs(actual_td - td_value) < 2.0:  # 2 microsecond tolerance
                points.append((lon, lat))
    
    # If we don't have enough points, return empty list
    if len(points) < 3:
        return []
    
    # Group points that are close to each other into branches
    branches = []
    visited = set()
    
    # Adjust this threshold to control branch separation
    branch_threshold = 0.8  # degrees
    
    # Find branches (independent curve segments)
    for i, point in enumerate(points):
        if i in visited:
            continue
            
        # Start a new branch
        branch = [point]
        visited.add(i)
        
        # Find nearby points for this branch
        change_made = True
        while change_made:
            change_made = False
            for j, other_point in enumerate(points):
                if j in visited:
                    continue
                    
                # Check if this point is close to any point in the current branch
                for branch_point in branch:
                    dist = math.sqrt(
                        (other_point[0] - branch_point[0])**2 + 
                        (other_point[1] - branch_point[1])**2
                    )
                    if dist < branch_threshold:
                        branch.append(other_point)
                        visited.add(j)
                        change_made = True
                        break
        
        if len(branch) >= 3:  # Only keep branches with enough points
            branches.append(branch)
    
    # If we have branches, sort them by number of points and take the largest
    if branches:
        branches.sort(key=len, reverse=True)
        largest_branch = branches[0]
        
        # Sort points in the branch to form a continuous line
        # We'll sort by using a simple nearest-neighbor approach
        ordered_points = [largest_branch[0]]
        remaining_points = largest_branch[1:]
        
        while remaining_points:
            last_point = ordered_points[-1]
            
            # Find the closest remaining point
            closest_idx = 0
            closest_dist = float('inf')
            for i, point in enumerate(remaining_points):
                dist = math.sqrt(
                    (point[0] - last_point[0])**2 + 
                    (point[1] - last_point[1])**2
                )
                if dist < closest_dist:
                    closest_dist = dist
                    closest_idx = i
            
            # If the closest point is too far, we have a gap
            # In this case, we'll just add it and continue
            ordered_points.append(remaining_points.pop(closest_idx))
        
        return ordered_points
    
    return [] 