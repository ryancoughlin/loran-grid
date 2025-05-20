# LORAN-C Grid Generator

A Python tool for generating LORAN-C grid data for offshore navigation in the Western Atlantic region (Maine to Florida), outputting to GeoJSON and MBTiles formats for use with Mapbox.

## Features

- Generates hyperbolic LORAN-C grid lines based on standard TD (Time Difference) values
- Supports the 9960 (Northeast US) and 7980 (Southeast US) chains
- Outputs to GeoJSON and MBTiles formats for use with Mapbox
- Simple HTML preview for validating GeoJSON output before uploading
- Designed for reproduction of standard LORAN grids found on older navigation charts

## Requirements

- Python 3.8 or higher
- [Tippecanoe](https://github.com/mapbox/tippecanoe) for MBTiles generation

## Installation

1. Clone this repository:

```bash
git clone https://github.com/yourusername/loran-grid.git
cd loran-grid
```

2. Create a virtual environment (recommended):

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Install Tippecanoe (for MBTiles generation):

On macOS:

```bash
brew install tippecanoe
```

On Linux:

```bash
git clone https://github.com/mapbox/tippecanoe.git
cd tippecanoe
make -j
make install
```

## Usage

Generate a LORAN-C grid and output to GeoJSON:

```bash
python loran_cli.py
```

Generate a grid and create MBTiles for Mapbox upload:

```bash
python loran_cli.py --mbtiles
```

Generate a grid for a specific region:

```bash
python loran_cli.py --region 9960wy --mbtiles
```

Create an HTML preview for validation:

```bash
python loran_cli.py --html-preview
```

Customize zoom levels for MBTiles:

```bash
python loran_cli.py --mbtiles --min-zoom 3 --max-zoom 12
```

For more options:

```bash
python loran_cli.py --help
```

## HTML Preview

The HTML preview embeds the GeoJSON data directly in the HTML file to avoid CORS issues when opening locally. For very large GeoJSON files, you may want to run a local server instead:

```bash
# From the project root directory
python -m http.server 8000
```

Then open http://localhost:8000/output/loran_grid_preview.html in your browser.

## Project Structure

- `loran_cli.py`: Command-line interface for the grid generator
- `loran/`: Module containing core functionality
  - `physics.py`: LORAN-C physics calculations and hyperbola generation
  - `schemas.py`: Data models for LORAN-C configuration
  - `generator.py`: Grid line generation and GeoJSON output
  - `visualization.py`: HTML preview for validation
- `config/`: Configuration files
  - `loran_config.json`: Station data and grid parameters
- `output/`: Default directory for generated files

## Uploading to Mapbox

After generating your MBTiles file:

1. Log in to your Mapbox account
2. Navigate to Tilesets
3. Upload the generated .mbtiles file
4. Use the tileset ID in your Mapbox GL JS applications

## Credits

- LORAN-C station data from USCG LORAN-C User Handbook
- Physics calculations based on standard LORAN-C navigation principles

## License

MIT
