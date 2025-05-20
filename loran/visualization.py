"""
LORAN-C Grid Visualization

Functions for visualizing LORAN-C grid lines.
"""

from typing import List, Dict, Any, Optional, Tuple
import json
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.collections import LineCollection
import numpy as np
from pathlib import Path

from .schemas import LORConfig, GridLine


def create_figure(
    config: LORConfig,
    figsize: Tuple[int, int] = (12, 10),
    title: str = "LORAN-C Grid",
) -> Tuple[plt.Figure, plt.Axes]:
    """
    Create a figure for plotting the LORAN-C grid.
    
    Args:
        config: LORAN-C configuration
        figsize: Figure size as (width, height) in inches
        title: Figure title
        
    Returns:
        Tuple of (Figure, Axes)
    """
    fig, ax = plt.subplots(figsize=figsize)
    
    # Set up the plot
    bbox = config.get_bounding_box()
    ax.set_xlim(bbox.min_lon, bbox.max_lon)
    ax.set_ylim(bbox.min_lat, bbox.max_lat)
    
    # Add title and labels
    ax.set_title(title, fontsize=16)
    ax.set_xlabel('Longitude', fontsize=12)
    ax.set_ylabel('Latitude', fontsize=12)
    
    # Add grid
    ax.grid(True, alpha=0.3)
    
    return fig, ax


def plot_grid_lines(
    ax: plt.Axes,
    grid_lines: List[GridLine],
    line_color: str = 'black',
    line_width: float = 1.0,
    alpha: float = 0.7,
    show_labels: bool = True,
    label_fontsize: int = 8,
    label_spacing: int = 5,  # Label every Nth line
) -> None:
    """
    Plot LORAN-C grid lines on the axes.
    
    Args:
        ax: Matplotlib axes
        grid_lines: List of GridLine objects
        line_color: Line color
        line_width: Line width
        alpha: Line transparency
        show_labels: Whether to show TD values as labels
        label_fontsize: Font size for labels
        label_spacing: Label every Nth line
    """
    # Group lines by chain and secondary
    grouped_lines = {}
    for line in grid_lines:
        key = f"{line.chain_id}_{line.secondary_id}"
        if key not in grouped_lines:
            grouped_lines[key] = []
        grouped_lines[key].append(line)
    
    # Plot each group with different colors
    colors = ['blue', 'red', 'green', 'purple', 'orange', 'brown', 'pink']
    for i, (group_key, lines) in enumerate(grouped_lines.items()):
        color = colors[i % len(colors)]
        
        # Sort lines by TD value
        lines.sort(key=lambda x: x.td_value)
        
        # Plot lines
        for j, line in enumerate(lines):
            coords = np.array(line.coordinates)
            ax.plot(
                coords[:, 0],  # Longitude
                coords[:, 1],  # Latitude
                color=color,
                linewidth=line_width,
                alpha=alpha,
            )
            
            # Add label (every Nth line)
            if show_labels and j % label_spacing == 0:
                # Place label at the middle of the line
                mid_idx = len(coords) // 2
                
                if mid_idx < len(coords):
                    ax.text(
                        coords[mid_idx, 0],
                        coords[mid_idx, 1],
                        f"{int(line.td_value)}",
                        color=color,
                        fontsize=label_fontsize,
                        ha='center',
                        va='center',
                        bbox=dict(
                            facecolor='white',
                            alpha=0.7,
                            edgecolor='none',
                            boxstyle='round,pad=0.2'
                        ),
                        path_effects=[
                            pe.withStroke(linewidth=2, foreground='white')
                        ],
                    )


def plot_stations(
    ax: plt.Axes,
    config: LORConfig,
    master_marker: str = 'o',
    secondary_marker: str = '^',
    master_color: str = 'red',
    secondary_color: str = 'blue',
    marker_size: int = 80,
    show_labels: bool = True,
) -> None:
    """
    Plot LORAN-C stations on the axes.
    
    Args:
        ax: Matplotlib axes
        config: LORAN-C configuration
        master_marker: Marker style for master stations
        secondary_marker: Marker style for secondary stations
        master_color: Color for master stations
        secondary_color: Color for secondary stations
        marker_size: Marker size
        show_labels: Whether to show station labels
    """
    # Plot each chain's stations
    for chain_id, chain in config.chains.items():
        # Plot master station
        ax.scatter(
            chain.master.longitude,
            chain.master.latitude,
            s=marker_size,
            c=master_color,
            marker=master_marker,
            edgecolor='black',
            zorder=10,
            label=f"Master {chain_id}"
        )
        
        if show_labels:
            ax.text(
                chain.master.longitude,
                chain.master.latitude + 0.2,
                f"M-{chain_id}",
                fontsize=10,
                ha='center',
                va='bottom',
                bbox=dict(
                    facecolor='white',
                    alpha=0.7,
                    edgecolor='none',
                    boxstyle='round,pad=0.2'
                ),
            )
        
        # Plot secondary stations
        for sec_id, secondary in chain.secondaries.items():
            # Check if this secondary is used in any station pair
            is_used = any(
                pair.chain_id == chain_id and pair.secondary_id == sec_id
                for pair in config.station_pairs
            )
            
            alpha = 1.0 if is_used else 0.5  # Fade out unused secondaries
            
            ax.scatter(
                secondary.longitude,
                secondary.latitude,
                s=marker_size,
                c=secondary_color,
                marker=secondary_marker,
                edgecolor='black',
                alpha=alpha,
                zorder=10,
            )
            
            if show_labels:
                ax.text(
                    secondary.longitude,
                    secondary.latitude + 0.2,
                    f"{sec_id}-{chain_id}",
                    fontsize=10,
                    ha='center',
                    va='bottom',
                    alpha=alpha,
                    bbox=dict(
                        facecolor='white',
                        alpha=0.7,
                        edgecolor='none',
                        boxstyle='round,pad=0.2'
                    ),
                )


def visualize_grid(
    config: LORConfig,
    grid_lines: List[GridLine],
    output_path: Optional[str] = None,
    show_plot: bool = False,
    title: str = "LORAN-C Grid",
) -> None:
    """
    Visualize LORAN-C grid and save to file.
    
    Args:
        config: LORAN-C configuration
        grid_lines: List of GridLine objects
        output_path: Path to save the visualization (if None, won't save)
        show_plot: Whether to display the plot
        title: Plot title
    """
    # Create figure
    fig, ax = create_figure(config, title=title)
    
    # Plot grid lines
    plot_grid_lines(ax, grid_lines)
    
    # Plot stations
    plot_stations(ax, config)
    
    # Add legend
    ax.legend()
    
    # Save if output path provided
    if output_path:
        # Ensure output directory exists
        output_dir = Path(output_path).parent
        output_dir.mkdir(exist_ok=True, parents=True)
        
        # Save the figure
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Visualization saved to {output_path}")
    
    # Show if requested
    if show_plot:
        plt.show()
    
    # Close the figure
    plt.close(fig)


def create_html_viewer(
    geojson_path: str,
    output_path: str,
    center: List[float] = [-75, 36],
    zoom: int = 5,
) -> None:
    """
    Create a simple HTML viewer for the GeoJSON grid.
    
    Args:
        geojson_path: Path to the GeoJSON file
        output_path: Path to save the HTML file
        center: Map center as [longitude, latitude]
        zoom: Initial zoom level
    """
    # Load the GeoJSON file directly
    with open(geojson_path, 'r') as f:
        geojson_data = json.load(f)
    
    # Serialize the GeoJSON data to a JSON string for embedding
    geojson_str = json.dumps(geojson_data)
    
    # Create the HTML content with embedded GeoJSON
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <title>LORAN-C Grid Viewer</title>
    <meta name="viewport" content="initial-scale=1,maximum-scale=1,user-scalable=no" />
    <script src="https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.js"></script>
    <link href="https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.css" rel="stylesheet" />
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ position: absolute; top: 0; bottom: 0; width: 100%; }}
        .map-overlay {{
            position: absolute;
            bottom: 0;
            right: 0;
            background: rgba(255, 255, 255, 0.8);
            margin-right: 20px;
            font-family: Arial, sans-serif;
            overflow: auto;
            border-radius: 3px;
            padding: 10px;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="map-overlay">
        <h3>LORAN-C Grid Preview</h3>
        <p>TD values in microseconds</p>
    </div>

    <script>
        // Mapbox access token
        mapboxgl.accessToken = 'pk.eyJ1Ijoic25vd2Nhc3QiLCJhIjoiY2plYXNjdTRoMDhsbDJ4bGFjOWN0YjdzeCJ9.fM2s4NZq_LUiTXJxsl2HbQ';
        
        // Embedded GeoJSON data to avoid CORS issues
        const geojsonData = {geojson_str};
        
        const map = new mapboxgl.Map({{
            container: 'map',
            style: 'mapbox://styles/mapbox/light-v11',
            center: {center},
            zoom: {zoom}
        }});

        map.on('load', () => {{
            // Add GeoJSON source with embedded data
            map.addSource('loran-grid', {{
                type: 'geojson',
                data: geojsonData
            }});

            // Add line layer
            map.addLayer({{
                id: 'grid-lines',
                type: 'line',
                source: 'loran-grid',
                layout: {{
                    'line-join': 'round',
                    'line-cap': 'round'
                }},
                paint: {{
                    'line-color': '#000000',  // Black lines
                    'line-width': 1
                }}
            }});

            // Add text labels
            map.addLayer({{
                id: 'grid-labels',
                type: 'symbol',
                source: 'loran-grid',
                layout: {{
                    'text-field': ['get', 'label'],
                    'text-size': 10,
                    'symbol-placement': 'line',
                    'text-justify': 'center',
                    'text-allow-overlap': false,
                    'text-max-angle': 30
                }},
                paint: {{
                    'text-color': '#000000',
                    'text-halo-color': '#FFFFFF',
                    'text-halo-width': 2
                }}
            }});
        }});
    </script>
</body>
</html>
"""
    
    # Save the HTML file
    with open(output_path, 'w') as f:
        f.write(html_content)
    
    print(f"HTML viewer saved to {output_path}")
    print("Note: HTML preview is ready to open directly in your browser") 