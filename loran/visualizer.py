"""
LORAN Grid Visualizer.

This module provides functions for visualizing LORAN grids.
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap


def plot_loran_grid(grid_data, config, output_path=None):
    """
    Create a visualization of LORAN grid for the Atlantic region.
    
    Parameters
    ----------
    grid_data : pandas.DataFrame
        DataFrame containing grid points with lat, lon, and LORAN values
    config : dict
        Configuration dictionary with visualization parameters
    output_path : str or pathlib.Path, optional
        Path to save the plot. If None, the plot is displayed but not saved.
    
    Returns
    -------
    matplotlib.figure.Figure
        The created figure
    """
    # Extract relevant data
    lats = grid_data['latitude'].values
    lons = grid_data['longitude'].values
    
    # Determine which LORAN values to plot
    # Find TD columns (those not latitude/longitude)
    td_columns = [col for col in grid_data.columns 
                 if col not in ['latitude', 'longitude']]
    
    if not td_columns:
        print("No TD columns found in grid data.")
        return None
    
    # Create visualization
    fig, ax = plt.subplots(figsize=(12, 10))
    
    # Get geographic bounds
    bounds = config.get('bounds', [25.0, -82.0, 47.0, -67.0])
    min_lat, min_lon, max_lat, max_lon = bounds
    
    # Plot TD lines for each chain and secondary
    colors = {
        '9960_W': 'blue',
        '9960_X': 'red',
        '9960_Y': 'green',
        '9960_Z': 'purple',
        '7980_W': 'orange',
        '7980_X': 'cyan',
        '7980_Y': 'magenta',
        '7980_Z': 'brown'
    }
    
    # Reshape data for contour plotting
    for col in td_columns:
        if col not in colors:
            print(f"Warning: No color defined for TD column {col}")
            continue
        
        color = colors[col]
        
        try:
            # Create a triangulation or grid for contour plotting
            # This is a simple approach - better methods exist for irregular grids
            from scipy.interpolate import griddata
            
            # Create a regular grid
            grid_x, grid_y = np.mgrid[min_lon:max_lon:500j, min_lat:max_lat:500j]
            
            # Interpolate TD values onto the regular grid
            grid_z = griddata((lons, lats), grid_data[col], (grid_x, grid_y), method='cubic')
            
            # Calculate contour levels
            # Get the min/max TD values and create evenly spaced levels
            z_min = np.nanmin(grid_z)
            z_max = np.nanmax(grid_z)
            
            # Use the grid spacing from config, or default to 100μs
            contour_interval = config.get('visualization', {}).get('contour_intervals', 100)
            
            # Create levels at intervals of contour_interval, spanning the range of TD values
            levels = np.arange(
                np.floor(z_min / contour_interval) * contour_interval,
                np.ceil(z_max / contour_interval) * contour_interval + 1,
                contour_interval
            )
            
            # Plot contour lines
            contour = ax.contour(grid_x, grid_y, grid_z, levels=levels, 
                                colors=color, alpha=0.8, linewidths=0.8)
            
            # Add labels to the contour lines
            # Skip some labels if there are too many
            label_spacing = config.get('visualization', {}).get('label_spacing', 5)
            if label_spacing > 0:
                # Label every label_spacing'th level
                fmt = {}
                for i, level in enumerate(contour.levels):
                    if i % label_spacing == 0:
                        fmt[level] = int(level)
                    else:
                        fmt[level] = ''
                        
                ax.clabel(contour, inline=True, fontsize=8, fmt=fmt)
        
        except Exception as e:
            print(f"Could not plot contours for {col}: {e}")
    
    # Set plot boundaries
    ax.set_xlim(min_lon, max_lon)
    ax.set_ylim(min_lat, max_lat)
    
    # Add coastline if available
    if config.get('visualization', {}).get('include_coastline', True):
        try:
            # This would normally use a coastline dataset
            # For simplicity, we're not implementing this here
            pass
        except Exception as e:
            print(f"Could not add coastline: {e}")
    
    # Add labels and title
    ax.set_xlabel('Longitude')
    ax.set_ylabel('Latitude')
    ax.set_title('LORAN Grid - Atlantic Region')
    
    # Add legend
    for col, color in colors.items():
        if col in td_columns:
            # Parse the column name to get a readable label
            chain_id, secondary_id = col.split('_')
            ax.plot([], [], color=color, label=f'Chain {chain_id}, Secondary {secondary_id}')
    
    ax.legend(loc='upper right')
    
    # Add grid
    ax.grid(True, linestyle='--', alpha=0.6)
    
    # Save figure if output path is provided
    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
    
    return fig


def plot_td_intersections(grid_data, config, td_values, output_path=None):
    """
    Plot intersection points of specific TD values.
    
    Parameters
    ----------
    grid_data : pandas.DataFrame
        DataFrame with lat/lon and TD values
    config : dict
        Configuration dictionary
    td_values : dict
        Dictionary of TD values to plot intersections for
    output_path : str or pathlib.Path, optional
        Path to save the plot
        
    Returns
    -------
    matplotlib.figure.Figure
        The created figure
    """
    # This function would find and plot the intersection points of TD lines
    # For simplicity, we're only implementing a placeholder
    
    fig, ax = plt.subplots(figsize=(12, 10))
    
    bounds = config.get('bounds', [25.0, -82.0, 47.0, -67.0])
    min_lat, min_lon, max_lat, max_lon = bounds
    
    ax.set_xlim(min_lon, max_lon)
    ax.set_ylim(min_lat, max_lat)
    
    ax.set_xlabel('Longitude')
    ax.set_ylabel('Latitude')
    ax.set_title('LORAN Grid TD Intersections - Atlantic Region')
    
    ax.text(0.5, 0.5, "TD Intersections - To Be Implemented", 
            ha='center', va='center', fontsize=14, transform=ax.transAxes)
    
    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
    
    return fig


def create_navigation_chart(grid_data, background_map=None, output_path=None):
    """
    Create a navigation chart with LORAN grid overlay.
    This is a placeholder for future implementation.
    
    Parameters
    ----------
    grid_data : pandas.DataFrame
        DataFrame containing grid points with lat, lon, and LORAN values
    background_map : str, optional
        Path to background map image
    output_path : str or pathlib.Path, optional
        Path to save the chart
    
    Returns
    -------
    matplotlib.figure.Figure
        The created figure
    """
    # This is a placeholder function for future implementation
    fig, ax = plt.subplots(figsize=(12, 10))
    ax.text(0.5, 0.5, "Navigation Chart - To Be Implemented", 
            ha='center', va='center', fontsize=14)
    
    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
    
    return fig 