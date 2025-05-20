"""
LORAN Grid Calculator for Atlantic region.

This module contains functions for calculating LORAN grid
positions based on configuration parameters.
"""

import pandas as pd
import numpy as np
from pyproj import Geod
from geopy.distance import geodesic


# Speed of light in km/μs
SPEED_OF_LIGHT = 0.299792458  # km/μs


def calculate_loran_grid(config):
    """
    Calculate LORAN grid for Atlantic region based on configuration.
    
    Parameters
    ----------
    config : dict
        Configuration dictionary containing LORAN parameters:
        - bounds: Geographic bounds [min_lat, min_lon, max_lat, max_lon]
        - grid_spacing: Grid resolution in microseconds
        - chains: LORAN chains data (9960 and 7980)
    
    Returns
    -------
    pandas.DataFrame
        DataFrame containing grid points with lat, lon, and 
        LORAN time differences for each station pair
    """
    bounds = config.get('bounds', [25.0, -82.0, 47.0, -67.0])
    grid_spacing = config.get('grid_spacing', 100)  # microseconds
    chains = config.get('chains', {})
    
    min_lat, min_lon, max_lat, max_lon = bounds
    
    # Create grid of points for our calculation area
    lat_steps = np.linspace(min_lat, max_lat, 50)
    lon_steps = np.linspace(min_lon, max_lon, 50)
    
    # Create grid points
    grid_points = []
    
    # Use pyproj's Geod for accurate distance calculations on an ellipsoid
    geod = Geod(ellps='WGS84')
    
    for lat in lat_steps:
        for lon in lon_steps:
            point_data = {
                'latitude': lat,
                'longitude': lon
            }
            
            # Calculate LORAN TDs for each chain and station pair
            for chain_id, chain_data in chains.items():
                # Get master station coordinates
                master = chain_data.get('master', {})
                master_lat = master.get('latitude')
                master_lon = master.get('longitude')
                
                if not master_lat or not master_lon:
                    continue
                
                # Calculate distance from point to master station
                _, _, master_distance = geod.inv(
                    lon, lat, master_lon, master_lat
                )
                master_distance /= 1000  # Convert to km
                
                # Calculate TDs for each secondary station
                secondaries = chain_data.get('secondaries', [])
                for secondary_id, secondary in secondaries.items():
                    sec_lat = secondary.get('latitude')
                    sec_lon = secondary.get('longitude')
                    emission_delay = secondary.get('emission_delay', 0)
                    asf = secondary.get('asf', 0)  # Additional Secondary Factor
                    
                    if not sec_lat or not sec_lon:
                        continue
                    
                    # Calculate distance from point to secondary station
                    _, _, secondary_distance = geod.inv(
                        lon, lat, sec_lon, sec_lat
                    )
                    secondary_distance /= 1000  # Convert to km
                    
                    # Calculate time difference
                    # TD = emission_delay + (distance_difference / speed_of_light) + ASF
                    distance_diff = secondary_distance - master_distance
                    propagation_delay = distance_diff / SPEED_OF_LIGHT
                    
                    # Calculate TD value
                    td_value = emission_delay + propagation_delay + asf
                    
                    # Add TD to point data
                    point_data[f"{chain_id}_{secondary_id}"] = td_value
            
            grid_points.append(point_data)
    
    # Create DataFrame from calculated grid points
    return pd.DataFrame(grid_points)


def calculate_hyperbolic_contours(config, td_values):
    """
    Calculate hyperbolic contour lines for specific TD values.
    
    Parameters
    ----------
    config : dict
        Configuration dictionary with station data
    td_values : dict
        Dictionary of TD values to calculate contours for,
        keyed by chain_id and secondary_id
    
    Returns
    -------
    dict
        Dictionary of contour lines for each TD value
    """
    bounds = config.get('bounds', [25.0, -82.0, 47.0, -67.0])
    chains = config.get('chains', {})
    min_lat, min_lon, max_lat, max_lon = bounds
    
    # Use higher resolution for contour calculation
    lat_steps = np.linspace(min_lat, max_lat, 200)
    lon_steps = np.linspace(min_lon, max_lon, 200)
    
    # Create meshgrid for contour calculation
    lon_grid, lat_grid = np.meshgrid(lon_steps, lat_steps)
    
    contours = {}
    geod = Geod(ellps='WGS84')
    
    # Calculate TD grid for each chain and secondary
    for chain_id, chain_data in chains.items():
        master = chain_data.get('master', {})
        master_lat = master.get('latitude')
        master_lon = master.get('longitude')
        
        if not master_lat or not master_lon:
            continue
        
        secondaries = chain_data.get('secondaries', {})
        
        for secondary_id, secondary in secondaries.items():
            sec_lat = secondary.get('latitude')
            sec_lon = secondary.get('longitude')
            emission_delay = secondary.get('emission_delay', 0)
            asf = secondary.get('asf', 0)
            
            if not sec_lat or not sec_lon:
                continue
                
            # Calculate TD grid for this master-secondary pair
            td_grid = np.zeros_like(lon_grid)
            
            for i in range(len(lat_steps)):
                for j in range(len(lon_steps)):
                    lat = lat_grid[i, j]
                    lon = lon_grid[i, j]
                    
                    # Calculate distances
                    _, _, master_distance = geod.inv(
                        lon, lat, master_lon, master_lat
                    )
                    master_distance /= 1000  # Convert to km
                    
                    _, _, secondary_distance = geod.inv(
                        lon, lat, sec_lon, sec_lat
                    )
                    secondary_distance /= 1000  # Convert to km
                    
                    # Calculate TD
                    distance_diff = secondary_distance - master_distance
                    propagation_delay = distance_diff / SPEED_OF_LIGHT
                    td_grid[i, j] = emission_delay + propagation_delay + asf
            
            # Get the specific TD values to contour for this chain-secondary pair
            pair_key = f"{chain_id}_{secondary_id}"
            pair_td_values = td_values.get(pair_key, [])
            
            if not pair_td_values:
                continue
                
            # Extract contours for the requested TD values
            pair_contours = {}
            for td_value in pair_td_values:
                # Find all points approximately equal to td_value
                # This is a simple approach - a real implementation would use
                # a proper contour finding algorithm
                threshold = 0.05  # μs
                mask = np.abs(td_grid - td_value) < threshold
                contour_points = []
                
                for i in range(len(lat_steps)):
                    for j in range(len(lon_steps)):
                        if mask[i, j]:
                            contour_points.append((lon_grid[i, j], lat_grid[i, j]))
                
                if contour_points:
                    pair_contours[td_value] = contour_points
            
            contours[pair_key] = pair_contours
    
    return contours


def calculate_td_range(config):
    """
    Calculate appropriate TD range for each chain and station pair.
    
    Parameters
    ----------
    config : dict
        Configuration dictionary with station data
        
    Returns
    -------
    dict
        Dictionary of TD ranges for each chain and station pair
    """
    bounds = config.get('bounds', [25.0, -82.0, 47.0, -67.0])
    chains = config.get('chains', {})
    min_lat, min_lon, max_lat, max_lon = bounds
    
    # Calculate the maximum distance within the bounds (diagonal)
    max_distance = geodesic((min_lat, min_lon), (max_lat, max_lon)).kilometers
    
    # Estimate the maximum time difference due to distance
    max_time_diff = max_distance / SPEED_OF_LIGHT
    
    td_ranges = {}
    
    for chain_id, chain_data in chains.items():
        master = chain_data.get('master', {})
        master_lat = master.get('latitude')
        master_lon = master.get('longitude')
        
        if not master_lat or not master_lon:
            continue
        
        secondaries = chain_data.get('secondaries', {})
        
        for secondary_id, secondary in secondaries.items():
            sec_lat = secondary.get('latitude')
            sec_lon = secondary.get('longitude')
            emission_delay = secondary.get('emission_delay', 0)
            
            if not sec_lat or not sec_lon:
                continue
            
            # Calculate rough range
            min_td = emission_delay - max_time_diff
            max_td = emission_delay + max_time_diff
            
            # Set step size based on grid spacing
            step = config.get('grid_spacing', 100)  # μs
            
            # Store the range
            td_ranges[f"{chain_id}_{secondary_id}"] = {
                'min': min_td,
                'max': max_td,
                'step': step
            }
    
    return td_ranges 