"""
RipCharts-compatible LORAN-C data models using Pydantic.

These models define the structure for RipCharts-exact LORAN-C configuration,
including calibration anchors, unwrapping parameters, and label formatting.
"""

from typing import Dict, List, Literal, Optional, Tuple, Union, Any
from pydantic import BaseModel, Field, ConfigDict
import yaml


class Station(BaseModel):
    """A LORAN-C station (Master or Secondary)."""
    
    id: str = Field(..., description="Station identifier")
    name: str = Field(..., description="Station name")
    latitude: float = Field(..., description="Latitude in decimal degrees")
    longitude: float = Field(..., description="Longitude in decimal degrees")
    emission_delay: float = Field(0.0, description="Emission delay in microseconds")
    coding_delay: float = Field(0.0, description="Coding delay in microseconds")


class Secondary(Station):
    """A LORAN-C secondary station with ASF correction."""
    
    asf: float = Field(0.0, description="Additional Secondary Factor correction")


class Chain(BaseModel):
    """A LORAN-C chain with master and secondary stations."""
    
    name: str = Field(..., description="Chain name")
    gri: int = Field(..., description="Group Repetition Interval")
    master: Station = Field(..., description="Master station")
    secondaries: Dict[str, Secondary] = Field(..., description="Secondary stations")


class StationPair(BaseModel):
    """A pair of master and secondary stations for grid generation."""
    
    chain_id: str = Field(..., description="Chain identifier (e.g., '9960')")
    secondary_id: str = Field(..., description="Secondary station identifier")
    family: str = Field(..., description="Family identifier (W, X, Y, Z)")
    orientation: Literal["vertical", "horizontal"] = Field(
        ..., description="Line orientation"
    )


class TDRange(BaseModel):
    """Range of Time Difference values for grid generation."""
    
    min_td: float = Field(..., description="Minimum TD value in microseconds")
    max_td: float = Field(..., description="Maximum TD value in microseconds")
    step: float = Field(50.0, description="Step size in microseconds")
    format: str = Field("{:05.0f}", description="Format string for labels")


class CalibrationAnchor(BaseModel):
    """Calibration anchor point for TD field alignment."""
    
    latitude: float = Field(..., description="Anchor latitude")
    longitude: float = Field(..., description="Anchor longitude")
    td_values: Dict[str, float] = Field(
        ..., description="Expected TD values for each pair at this location"
    )


class UnwrappingConfig(BaseModel):
    """Configuration for TD field unwrapping."""
    
    enabled: bool = Field(True, description="Enable unwrapping")
    gri: float = Field(..., description="GRI value for unwrapping")
    smooth_iterations: int = Field(3, description="Smoothing iterations")


class LabelConfig(BaseModel):
    """Configuration for label placement and formatting."""
    
    enabled: bool = Field(True, description="Enable labels")
    placement: List[Literal["start", "middle", "end"]] = Field(
        ["start", "middle", "end"], description="Label placement positions"
    )
    min_line_length: float = Field(5.0, description="Minimum line length for labeling (km)")
    format_trailing_zeros: bool = Field(True, description="Preserve trailing zeros")


class ProcessingConfig(BaseModel):
    """Configuration for grid processing and clipping."""
    
    clip_to_bounds: bool = Field(True, description="Clip all lines to bounding box")
    min_line_length: float = Field(2.0, description="Minimum line length to keep (km)")
    max_line_segments: int = Field(1000, description="Maximum segments per line")
    simplify_tolerance: float = Field(0.001, description="Degrees tolerance for line simplification")


class OutputConfig(BaseModel):
    """Output format configuration."""
    
    format: Literal["geojson"] = Field("geojson", description="Output format")
    coordinate_precision: int = Field(6, description="Coordinate decimal places")
    include_labels: bool = Field(True, description="Include label features")
    include_metadata: bool = Field(True, description="Include metadata properties")
    line_properties: List[str] = Field(
        ["family", "kind", "td", "chain_id", "secondary_id"],
        description="Properties to include for line features"
    )
    label_properties: List[str] = Field(
        ["family", "kind", "td", "label", "chain_id", "secondary_id"],
        description="Properties to include for label features"
    )


class RegionConfig(BaseModel):
    """Configuration for a specific region."""
    
    name: str = Field(..., description="Region name")
    display_name: str = Field(..., description="Display name")
    description: str = Field(..., description="Region description")
    bounds: List[float] = Field(..., description="[min_lon, min_lat, max_lon, max_lat]")
    pairs: List[StationPair] = Field(..., description="Station pairs to generate")
    td_ranges: Dict[str, TDRange] = Field(..., description="TD ranges for each pair")
    calibration_anchors: List[CalibrationAnchor] = Field(
        ..., description="Calibration anchor points"
    )
    unwrapping: UnwrappingConfig = Field(..., description="Unwrapping configuration")
    labels: LabelConfig = Field(..., description="Label configuration")
    processing: Optional[ProcessingConfig] = Field(
        default_factory=ProcessingConfig, description="Processing configuration"
    )


class RipChartsConfig(BaseModel):
    """Complete RipCharts-compatible LORAN-C configuration."""
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    grid_resolution: float = Field(0.027, description="Grid resolution in degrees")
    speed_of_light: float = Field(0.299792458, description="Speed of light in km/μs")
    chains: Dict[str, Chain] = Field(..., description="LORAN-C chains")
    regions: Dict[str, RegionConfig] = Field(..., description="Regional configurations")
    output: OutputConfig = Field(..., description="Output configuration")
    
    @classmethod
    def from_yaml(cls, yaml_path: str) -> "RipChartsConfig":
        """Load configuration from YAML file."""
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
        return cls(**data)


class GridLine(BaseModel):
    """A hyperbolic grid line with constant TD value."""
    
    chain_id: str = Field(..., description="Chain identifier")
    secondary_id: str = Field(..., description="Secondary station identifier")
    family: str = Field(..., description="Family identifier")
    td_value: float = Field(..., description="Time Difference value in microseconds")
    coordinates: List[Tuple[float, float]] = Field(
        ..., description="Line coordinates as (longitude, latitude) pairs"
    )


class GridLabel(BaseModel):
    """A label for a grid line."""
    
    chain_id: str = Field(..., description="Chain identifier")
    secondary_id: str = Field(..., description="Secondary station identifier")
    family: str = Field(..., description="Family identifier")
    td_value: float = Field(..., description="Time Difference value in microseconds")
    label: str = Field(..., description="Formatted label text")
    latitude: float = Field(..., description="Label latitude")
    longitude: float = Field(..., description="Label longitude")


class GridResult(BaseModel):
    """Complete grid generation result."""
    
    region_name: str = Field(..., description="Region name")
    lines: List[GridLine] = Field(..., description="Grid lines")
    labels: List[GridLabel] = Field(..., description="Grid labels")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
