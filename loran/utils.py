"""
Utility functions for LORAN grid calculations.

This module provides helper functions and utilities for
LORAN grid generation and management.
"""

import json
import os
import math
from pathlib import Path


def create_sample_config(config_path):
    """
    Create a sample configuration file for LORAN grid generation.
    
    Parameters
    ----------
    config_path : str or pathlib.Path
        Path where the configuration file should be saved
    """
    config_path = Path(config_path)
    
    # Create parent directory if it doesn't exist
    config_path.parent.mkdir(exist_ok=True, parents=True)
    
    # Sample configuration for Atlantic region
    sample_config = {
        # Geographic bounds [min_lat, min_lon, max_lat, max_lon]
        # This covers the Atlantic region from Florida to Maine
        "bounds": [25.0, -82.0, 47.0, -67.0],
        
        # Grid spacing in microseconds
        "grid_spacing": 100,
        
        # LORAN chains data
        "chains": {
            "9960": {
                "name": "Northeast U.S.",
                "gri": 9960,
                "master": {
                    "id": "M",
                    "name": "Seneca, NY",
                    "latitude": 42.714088,
                    "longitude": -76.825919,
                    "emission_delay": 0,
                    "coding_delay": 0
                },
                "secondaries": {
                    "W": {
                        "name": "Caribou, ME",
                        "latitude": 46.807585,
                        "longitude": -67.926989,
                        "emission_delay": 13797.20,
                        "coding_delay": 11000,
                        "asf": 0
                    },
                    "X": {
                        "name": "Nantucket, MA",
                        "latitude": 41.253346,
                        "longitude": -69.977371,
                        "emission_delay": 26969.93,
                        "coding_delay": 25000,
                        "asf": 0
                    },
                    "Y": {
                        "name": "Carolina Beach, NC",
                        "latitude": 34.062836,
                        "longitude": -77.912806,
                        "emission_delay": 42221.64,
                        "coding_delay": 39000,
                        "asf": 0
                    }
                }
            },
            "7980": {
                "name": "Southeast U.S.",
                "gri": 7980,
                "master": {
                    "id": "M",
                    "name": "Malone, FL",
                    "latitude": 30.994094,
                    "longitude": -85.169251,
                    "emission_delay": 0,
                    "coding_delay": 0
                },
                "secondaries": {
                    "W": {
                        "name": "Grangeville, LA",
                        "latitude": 30.726394,
                        "longitude": -90.828778,
                        "emission_delay": 27443.38,
                        "coding_delay": 23000,
                        "asf": 0
                    },
                    "Y": {
                        "name": "Jupiter, FL",
                        "latitude": 27.032887,
                        "longitude": -80.114841,
                        "emission_delay": 61542.72,
                        "coding_delay": 59000,
                        "asf": 0
                    }
                }
            }
        },
        
        # Visualization settings
        "visualization": {
            "include_coastline": True,
            "contour_intervals": 100,
            "label_spacing": 5
        }
    }
    
    # Write configuration to file
    with open(config_path, 'w') as f:
        json.dump(sample_config, f, indent=2)
    
    print(f"Created sample configuration file at {config_path}")


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees).
    
    Parameters
    ----------
    lat1, lon1 : float
        Latitude and longitude of point 1 in decimal degrees
    lat2, lon2 : float
        Latitude and longitude of point 2 in decimal degrees
    
    Returns
    -------
    float
        Distance in kilometers
    """
    # Convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    
    # Haversine formula
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a)) 
    r = 6371  # Radius of earth in kilometers
    
    return c * r


def convert_miles_to_degrees(miles, latitude):
    """
    Convert distance in miles to approximate degrees of latitude/longitude.
    
    Parameters
    ----------
    miles : float
        Distance in miles
    latitude : float
        Reference latitude for longitude conversion
    
    Returns
    -------
    tuple
        (degrees_latitude, degrees_longitude)
    """
    # Approximate conversion (varies with latitude)
    kilometers = miles * 1.60934
    
    # 1 degree of latitude is approximately 111 km
    degrees_latitude = kilometers / 111.0
    
    # 1 degree of longitude varies with latitude
    # At the equator it's about 111 km, at the poles it's 0
    degrees_longitude = kilometers / (111.0 * math.cos(math.radians(latitude)))
    
    return degrees_latitude, degrees_longitude


def generate_td_values(td_range):
    """
    Generate TD values based on a range and step.
    
    Parameters
    ----------
    td_range : dict
        Dictionary with min, max, and step values
    
    Returns
    -------
    list
        List of TD values in the range
    """
    min_td = td_range.get('min', 0)
    max_td = td_range.get('max', 0)
    step = td_range.get('step', 100)
    
    if min_td >= max_td:
        return []
    
    values = []
    current_td = math.ceil(min_td / step) * step  # Round up to nearest step
    
    while current_td <= max_td:
        values.append(current_td)
        current_td += step
    
    return values


def calculate_asf_correction(lat, lon, master_lat, master_lon, secondary_lat, secondary_lon):
    """
    Calculate an approximate Additional Secondary Factor (ASF) correction.
    
    This is a simplified placeholder. In a real implementation, this would
    be based on actual ASF data from NOAA/NGA tables.
    
    Parameters
    ----------
    lat, lon : float
        Latitude and longitude of the point
    master_lat, master_lon : float
        Latitude and longitude of the master station
    secondary_lat, secondary_lon : float
        Latitude and longitude of the secondary station
    
    Returns
    -------
    float
        Approximate ASF correction in microseconds
    """
    # This is a placeholder for demonstration.
    # In reality, ASF corrections would come from lookup tables
    # or more complex models.
    
    # Simple distance-based approximation
    dist_to_master = haversine_distance(lat, lon, master_lat, master_lon)
    dist_to_secondary = haversine_distance(lat, lon, secondary_lat, secondary_lon)
    
    # Simplified ASF model - increases with distance
    # This is NOT accurate and should be replaced with real ASF data
    asf = (dist_to_master + dist_to_secondary) * 0.01
    
    return asf 