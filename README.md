# LORAN Grid Calculator for Atlantic

A Python tool for generating LORAN grid data for the Atlantic region, commonly used by offshore fishermen.

## Setup

1. Create a virtual environment (recommended):

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Run the main script:

```bash
python loran_grid.py
```

## Project Structure

- `loran_grid.py`: Main script to generate LORAN grid
- `loran/`: Package containing LORAN calculation modules
  - `calculator.py`: Core LORAN calculation logic
  - `visualizer.py`: Grid visualization tools
  - `utils.py`: Utility functions
- `config/`: Configuration files
  - `atlantic_config.json`: Configuration for Atlantic region

## License

MIT
