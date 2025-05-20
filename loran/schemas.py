"""
LORAN-C data models using Pydantic.

These models define the structure for LORAN-C configuration,
station coordinates, and grid parameters.
"""

from typing import Dict, List, Literal, Optional, Tuple, Union
from pydantic import BaseModel, Field, ConfigDict


class Station(BaseModel):
    """A LORAN-C station (Master or Secondary)."""
    
    id: Optional[str] = Field(None, description="Station identifier")
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


class BoundingBox(BaseModel):
    """Geographic bounding box."""
    
    min_lat: float = Field(..., description="Minimum latitude")
    min_lon: float = Field(..., description="Minimum longitude")
    max_lat: float = Field(..., description="Maximum latitude")
    max_lon: float = Field(..., description="Maximum longitude")
    
    @classmethod
    def from_list(cls, bounds: List[float]) -> "BoundingBox":
        """Create BoundingBox from [min_lat, min_lon, max_lat, max_lon]."""
        return cls(
            min_lat=bounds[0],
            min_lon=bounds[1],
            max_lat=bounds[2],
            max_lon=bounds[3]
        )
    
    def to_list(self) -> List[float]:
        """Convert to [min_lat, min_lon, max_lat, max_lon] list."""
        return [self.min_lat, self.min_lon, self.max_lat, self.max_lon]


class StationPair(BaseModel):
    """A pair of master and secondary stations for grid generation."""
    
    chain_id: str = Field(..., description="Chain identifier (e.g., '9960')")
    secondary_id: str = Field(..., description="Secondary station identifier")


class TDRange(BaseModel):
    """Range of Time Difference values for grid generation."""
    
    min_td: float = Field(..., description="Minimum TD value in microseconds")
    max_td: float = Field(..., description="Maximum TD value in microseconds")
    step: float = Field(100.0, description="Step size in microseconds")


class LORConfig(BaseModel):
    """Complete LORAN-C configuration."""
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    bounds: Union[List[float], BoundingBox] = Field(
        ..., description="Geographic bounds [min_lat, min_lon, max_lat, max_lon]"
    )
    grid_spacing: float = Field(100.0, description="Grid spacing in microseconds")
    chains: Dict[str, Chain] = Field(..., description="LORAN-C chains")
    station_pairs: List[StationPair] = Field(
        ..., description="Station pairs to generate grid lines for"
    )
    
    def get_bounding_box(self) -> BoundingBox:
        """Get the geographic bounding box."""
        if isinstance(self.bounds, list):
            return BoundingBox.from_list(self.bounds)
        return self.bounds


class GridLine(BaseModel):
    """A hyperbolic grid line with constant TD value."""
    
    chain_id: str = Field(..., description="Chain identifier")
    secondary_id: str = Field(..., description="Secondary station identifier")
    td_value: float = Field(..., description="Time Difference value in microseconds")
    coordinates: List[Tuple[float, float]] = Field(
        ..., description="Line coordinates as (longitude, latitude) pairs"
    ) 