import json
import math
import pyproj
from shapely.geometry import LineString, MultiLineString, box
from shapely.ops import transform as shapely_transform
import shapely.geometry

# Constants
C_PROPAGATION = 299.792458  # meters per microsecond (m/µs)
GEOD = pyproj.Geod(ellps='WGS84')

def load_config(filepath):
    """Loads a JSON configuration file."""
    with open(filepath, 'r') as f:
        return json.load(f)

def get_station_details(station_id, master_details, secondaries_details):
    """Retrieves station details (lat, lon, emission_delay, coding_delay)."""
    if station_id == master_details['id']: # Master
        return {
            "name": master_details['name'],
            "latitude": master_details['latitude'],
            "longitude": master_details['longitude'],
            "emission_delay": 0, # Master reference
            "coding_delay": 0    # Master reference
        }
    elif station_id in secondaries_details:
        s_data = secondaries_details[station_id]
        return {
            "name": s_data['name'],
            "latitude": s_data['latitude'],
            "longitude": s_data['longitude'],
            "emission_delay": s_data['emission_delay'],
            "coding_delay": s_data['coding_delay']
        }
    else:
        raise ValueError(f"Station ID {station_id} not found in master or secondaries.")

def generate_hyperbola_points(m_station, s_station, k_target_meters, bbox_coords, num_points=300, t_range_val=6.0):
    """
    Generates points for a hyperbola given Master, Secondary, K (distance diff in meters), and bounding box.
    k_target_meters = d(P,S) - d(P,M)
    """
    m_lon, m_lat = m_station['longitude'], m_station['latitude']
    s_lon, s_lat = s_station['longitude'], s_station['latitude']

    # Calculate distance between foci (Master-Secondary)
    _, _, d_ms_meters = GEOD.inv(m_lon, m_lat, s_lon, s_lat)

    if d_ms_meters == 0: # Should not happen for distinct M and S
        return None

    # Hyperbola parameters in local Cartesian coordinates (origin at midpoint of M-S, x-axis along M-S)
    # c_foci is half the distance between foci
    c_foci = d_ms_meters / 2.0
    # a_param is half the constant difference of distances
    # k_target_meters = d(P,S) - d(P,M)
    # For hyperbola equation x^2/a^2 - y^2/b^2 = 1, 'a' is related to |k_target_meters|
    # If k_target_meters > 0, points are closer to M. Branch opens towards M.
    # If k_target_meters < 0, points are closer to S. Branch opens towards S.
    
    a_param = abs(k_target_meters) / 2.0

    if a_param > c_foci: # No solution if |K| > d_MS
        return None
    
    if a_param == c_foci: # Degenerate case: rays along the M-S line
        # If k_target_meters > 0 (closer to M), ray from M outwards (away from S)
        # If k_target_meters < 0 (closer to S), ray from S outwards (away from M)
        # This can be tricky to implement as a long line; for now, we skip precise ray generation
        # as the standard parameterization might handle b=0 if careful.
        b_sq = 0.0
    else:
        b_sq = c_foci**2 - a_param**2
    
    if b_sq < 0: # Should be caught by a_param > c_foci, but as a safeguard
        return None
    b_param = math.sqrt(b_sq)

    points_geo = []
    
    # Midpoint and azimuth for transforming local coords to geographic
    # GEOD.npts returns a list of (lon, lat) tuples. We need the first (and only) one.
    mid_lon, mid_lat = GEOD.npts(m_lon, m_lat, s_lon, s_lat, 1)[0]
    az_ms, _, _ = GEOD.inv(m_lon, m_lat, s_lon, s_lat) # Azimuth from M to S

    # Parameter t for cosh/sinh
    t_values = [i * (t_range_val / (num_points // 2)) for i in range(-num_points // 2, num_points // 2 + 1)]
    if not t_values: t_values = [0] # Ensure at least one point for very small num_points

    for t in t_values:
        # Local Cartesian coordinates (x, y)
        # The branch depends on the sign of k_target_meters
        # If k_target_meters > 0 (d(P,S) > d(P,M), so P is closer to M), hyperbola branch is around M.
        # If M is at (-c_foci, 0) and S at (c_foci, 0) in local system,
        # then for points closer to M, x_local = -a_param * cosh(t)
        # If k_target_meters < 0 (d(P,S) < d(P,M), so P is closer to S), hyperbola branch is around S.
        # For points closer to S, x_local = a_param * cosh(t)

        try:
            cosh_t = math.cosh(t)
            sinh_t = math.sinh(t)
        except OverflowError:
            continue # t value too large

        if k_target_meters == 0: # Perpendicular bisector
             # x_local is 0. y_local covers the range.
            x_local = 0
            # Use sinh_t to scale y_local. The scale factor b_param here is c_foci.
            # The equation for perp. bisector is x=0. We need to parameterize the y-axis.
            # Let's simplify: y_local = c_foci * t (using t as a linear scaler for y)
            # This ensures y goes through a wide range. t_range_val might need adjustment for this case.
            # For this simple case, let's generate two far points.
            if not points_geo: # only do this once for the bisector
                # Use a very large distance to ensure the bisector spans the globe if needed, clipping will handle it.
                dist_far = GEOD.a * math.pi # Approx half Earth's circumference
                p1_lon, p1_lat, _ = GEOD.fwd(mid_lon, mid_lat, az_ms + 90, dist_far)
                p2_lon, p2_lat, _ = GEOD.fwd(mid_lon, mid_lat, az_ms - 90, dist_far)
                points_geo = [(p1_lon, p1_lat), (p2_lon, p2_lat)]
            break # Bisector is a straight line, two points are enough

        elif k_target_meters > 0: # Closer to M
            x_local = -a_param * cosh_t
        else: # k_target_meters < 0, closer to S
            x_local = a_param * cosh_t
        
        y_local = b_param * sinh_t
        
        # Transform (x_local, y_local) to geographic
        # Distance from local origin (midpoint of M-S)
        dist_from_mid = math.sqrt(x_local**2 + y_local**2)
        # Angle in local system (atan2 for correct quadrant)
        angle_in_local_rad = math.atan2(y_local, x_local)
        angle_in_local_deg = math.degrees(angle_in_local_rad)
        
        # True azimuth from midpoint: azimuth of M-S line + local angle
        true_azimuth_deg = az_ms + angle_in_local_deg
        
        p_lon, p_lat, _ = GEOD.fwd(mid_lon, mid_lat, true_azimuth_deg, dist_from_mid)
        points_geo.append((p_lon, p_lat))

    if len(points_geo) < 2:
        return None

    line = LineString(points_geo)
    
    # Define bounding box for clipping
    # bbox_coords = [min_lat, min_lon, max_lat, max_lon]
    clipper_box = box(bbox_coords[1], bbox_coords[0], bbox_coords[3], bbox_coords[2])
    
    try:
        clipped_geom = clipper_box.intersection(line)
    except Exception: # Broad exception for shapely errors
        return None

    if clipped_geom.is_empty:
        return None
    
    # Ensure consistent geometry type (LineString or MultiLineString)
    if isinstance(clipped_geom, (LineString, MultiLineString)):
        return clipped_geom
    else: # May return GeometryCollection etc.
        return None


def main():
    """Main function to generate LORAN hyperbolas."""
    atlantic_config_path = 'config/atlantic_config.json'
    loran_config_path = 'config/loran_config.json'
    output_geojson_path = 'loran_hyperbolas.geojson'

    atlantic_config = load_config(atlantic_config_path)
    loran_config = load_config(loran_config_path)

    atlantic_bounds = atlantic_config['bounds']  # [min_lat, min_lon, max_lat, max_lon]
    grid_spacing_td = atlantic_config['grid_spacing'] # µs, e.g. 100

    all_chains_data = atlantic_config['chains']
    regions_to_process = loran_config['regions']

    features = []

    for region_code, region_details in regions_to_process.items():
        print(f"Processing region: {region_details['name']} ({region_code})")
        for pair_info in region_details['pairs']:
            chain_id = pair_info['chain_id']
            secondary_id = pair_info['secondary_id']

            if chain_id not in all_chains_data:
                print(f"  Chain {chain_id} not found in atlantic_config. Skipping pair M-{secondary_id}.")
                continue
            
            chain_data = all_chains_data[chain_id]
            master_details_cfg = chain_data['master']
            
            if secondary_id not in chain_data['secondaries']:
                print(f"  Secondary {secondary_id} for chain {chain_id} not found in atlantic_config. Skipping.")
                continue

            m_station = get_station_details(master_details_cfg['id'], master_details_cfg, chain_data['secondaries'])
            s_station = get_station_details(secondary_id, master_details_cfg, chain_data['secondaries'])

            print(f"  Pair: Chain {chain_id}, M: {m_station['name']}, S: {s_station['name']} ({secondary_id})")

            delay_difference_s = s_station['emission_delay'] - s_station['coding_delay']

            # Determine TD_label range
            # This is an estimation. Lines outside bbox will be clipped.
            # TD_labels are typically around the secondary's coding_delay.
            # Let's try a range around the coding delay. Max plausible d_MS/c is ~10000us for large separations.
            # A TD range of coding_delay +/- 10000µs should be ample, clipped later.
            # Or use the theoretic range: DelayDifference_S +/- d_MS/c
            
            _, _, d_ms_meters_pair = GEOD.inv(m_station['longitude'], m_station['latitude'],
                                              s_station['longitude'], s_station['latitude'])
            baseline_delay_on_c = d_ms_meters_pair / C_PROPAGATION # in µs

            td_label_min_theoretic = delay_difference_s - baseline_delay_on_c
            td_label_max_theoretic = delay_difference_s + baseline_delay_on_c
            
            # Align to grid_spacing_td
            td_start = math.floor(td_label_min_theoretic / grid_spacing_td) * grid_spacing_td
            td_end = math.ceil(td_label_max_theoretic / grid_spacing_td) * grid_spacing_td
            
            # Clamp TD range to be sensible, e.g. not excessively far from coding delay if d_MS is huge
            # Heuristic: Ensure range covers typical values around coding delay
            # This is a wide range; clipping is key.
            # Example: ensure we cover at least coding_delay_S +/- 5000 us, within the theoretic bounds
            min_td_heuristic = s_station['coding_delay'] - 5000
            max_td_heuristic = s_station['coding_delay'] + 5000

            td_loop_start = min(td_start, min_td_heuristic if s_station['coding_delay'] !=0 else td_start)
            td_loop_end = max(td_end, max_td_heuristic if s_station['coding_delay'] !=0 else td_end)

            # For 7980Z (Carolina Beach), CD=0, ED=0, DelayDiff=0.
            # td_label_min/max_theoretic will be -/+ baseline_delay_on_c.
            # This range is correct. The heuristic above using coding_delay might not apply well if CD=0.

            current_td = td_loop_start
            while current_td <= td_loop_end:
                td_label = current_td
                
                # K = c_prop * (TD_label - (Emission_Delay_S - Coding_Delay_S))
                k_meters = C_PROPAGATION * (td_label - delay_difference_s)

                generated_geom = generate_hyperbola_points(m_station, s_station, k_meters, atlantic_bounds)

                if generated_geom:
                    properties = {
                        "chain_id": chain_id,
                        "master_name": m_station['name'],
                        "secondary_name": s_station['name'],
                        "secondary_id": secondary_id,
                        "td_label": td_label,
                        "K_meters": k_meters,
                        "delay_difference_s": delay_difference_s
                    }
                    if isinstance(generated_geom, LineString):
                        features.append({
                            "type": "Feature",
                            "geometry": shapely.geometry.mapping(generated_geom),
                            "properties": properties
                        })
                    elif isinstance(generated_geom, MultiLineString):
                        for linestring in generated_geom.geoms:
                             features.append({
                                "type": "Feature",
                                "geometry": shapely.geometry.mapping(linestring),
                                "properties": properties
                            })
                current_td += grid_spacing_td
    
    geojson_output = {
        "type": "FeatureCollection",
        "features": features
    }

    with open(output_geojson_path, 'w') as f:
        json.dump(geojson_output, f, indent=2)
    
    print(f"Generated {len(features)} LORAN LOPs.")
    print(f"Output saved to {output_geojson_path}")

if __name__ == "__main__":
    main() 