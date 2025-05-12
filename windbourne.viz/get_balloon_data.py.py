import requests
import json
import math
from datetime import datetime, timedelta, timezone
import time # For adding delays if needed for API rate limits

# --- Configuration ---
# !!! REPLACE WITH YOUR ACTUAL OpenWeatherMap API KEY !!!
OPENWEATHERMAP_API_KEY = "4c07bb69ea5fd41e220c4bdcc86d54d2"
# To avoid too many API calls during testing, limit how many points get weather data
# Set to a large number (or len(processed_balloon_points)) to process all.
# For initial testing, a small number like 5-10 is good.
MAX_WEATHER_CALLS = 10 # Example: Process weather for the first 10 points.
# If you want to process more but avoid hitting rate limits too fast, add a small delay:
SECONDS_DELAY_BETWEEN_API_CALLS = 1 # e.g., 1 second delay


# Part 1: Fetching Windborne API Data
# ====================================
BASE_URL = "https://a.windbornesystems.com/treasure/"
HOURS_TO_FETCH = 24 # Fetches 00.json up to 23.json

def replace_nan_with_none(obj):
    """
    Recursively traverses a Python object (typically from JSON)
    and replaces float('nan') with None.
    """
    if isinstance(obj, dict):
        # If it's a dictionary, iterate through its items
        # and apply the replacement to its values.
        return {k: replace_nan_with_none(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        # If it's a list, apply the replacement to each element.
        return [replace_nan_with_none(elem) for elem in obj]
    elif isinstance(obj, float) and math.isnan(obj):
        # If it's a float and is NaN, replace it with None.
        return None
    # Otherwise, return the object as is.
    return obj

def fetch_windborne_data():
    all_flight_data = []
    successful_fetches = 0
    failed_fetches = 0
    print(f"Attempting to fetch data for the last {HOURS_TO_FETCH} hours...")

    for i in range(HOURS_TO_FETCH):
        hour_str = f"{i:02d}"
        data_url = f"{BASE_URL}{hour_str}.json"
        # print(f"\nFetching data from: {data_url}") # Make it less verbose

        try:
            response = requests.get(data_url, timeout=15)
            if response.status_code == 200:
                try:
                    # Attempt to parse the JSON response
                    data = response.json()
                    
                    # Replace NaN values with None in the parsed data
                    data_cleaned = replace_nan_with_none(data)
                    
                    all_flight_data.append({"source_hour_file": f"{hour_str}.json", "data": data_cleaned})
                    successful_fetches += 1
                    # print(f"Successfully parsed JSON from {hour_str}.json") # Less verbose
                except json.JSONDecodeError:
                    print(f"Warning: Could not decode JSON from {data_url}. Content might be corrupted or not valid JSON.")
                    failed_fetches += 1
                except Exception as e:
                    print(f"Warning: Unexpected error processing data from {data_url}: {e}")
                    failed_fetches += 1
            else:
                print(f"Warning: Received non-200 status code {response.status_code} from {data_url}")
                failed_fetches += 1
        except requests.exceptions.Timeout:
            print(f"Warning: Request timed out for {data_url}")
            failed_fetches += 1
        except requests.exceptions.RequestException as e:
            print(f"Warning: Network request failed for {data_url}. Error: {e}")
            failed_fetches += 1
        except Exception as e:
            # Catch any other unexpected errors during the request process
            print(f"Warning: An unexpected error occurred for {data_url}: {e}")
            failed_fetches += 1
            
    print(f"\n--- Fetch Summary ---")
    print(f"Successfully fetched and parsed files: {successful_fetches}")
    print(f"Failed attempts/files with issues: {failed_fetches}")
    print(f"Total data entries collected (hourly files): {len(all_flight_data)}")
    
    return all_flight_data

# Part 2: Processing Fetched Balloon Data
# =======================================
def haversine(lat1, lon1, lat2, lon2):
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371
    return c * r

def calculate_bearing(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lat2])
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (math.sin(lat1) * math.cos(lat2) * math.cos(dlon))
    initial_bearing = math.atan2(x, y)
    initial_bearing = math.degrees(initial_bearing)
    compass_bearing = (initial_bearing + 360) % 360
    return compass_bearing

def process_balloon_data(flight_data_archive):
    processed_points = []
    current_utc_time = datetime.now(timezone.utc)
    # print(f"Processing relative to current UTC time: {current_utc_time.isoformat()}") # Verbose
    try:
        flight_data_archive.sort(key=lambda x: int(x['source_hour_file'].replace('.json', '')), reverse=True)
    except (ValueError, TypeError) as e:
        print(f"Info: Could not sort flight_data_archive by hour file name ({e}). Processing in received order.")

    for hourly_data_entry in flight_data_archive:
        source_file = hourly_data_entry['source_hour_file']
        raw_points_in_file = hourly_data_entry['data']
        if not isinstance(raw_points_in_file, list) or not raw_points_in_file:
            continue
        try:
            hour_offset = int(source_file.replace('.json', ''))
        except ValueError:
            print(f"Warning: Could not parse hour offset from {source_file}, skipping.")
            continue
        
        hour_end_timestamp_utc = current_utc_time - timedelta(hours=hour_offset)
        hour_start_timestamp_utc = hour_end_timestamp_utc - timedelta(hours=1)
        num_points_in_hour_file = len(raw_points_in_file)
        time_increment_per_point_s = 3600.0 / num_points_in_hour_file if num_points_in_hour_file > 1 else 0
        previous_point_data = None

        for i, point_coords in enumerate(raw_points_in_file):
            if not (isinstance(point_coords, list) and len(point_coords) == 3):
                continue
            try:
                lat, lon, alt = float(point_coords[0]), float(point_coords[1]), float(point_coords[2])
            except (ValueError, TypeError):
                continue
            
            point_timestamp_utc = hour_start_timestamp_utc + timedelta(seconds=i * time_increment_per_point_s) if num_points_in_hour_file > 1 else hour_start_timestamp_utc
            
            current_point_processed = {
                "latitude": lat, "longitude": lon, "altitude": alt,
                "timestamp_utc": point_timestamp_utc.isoformat(), "source_file": source_file,
                "ground_speed_kmh": None, "bearing_deg": None
            }

            if previous_point_data and time_increment_per_point_s > 0:
                prev_lat, prev_lon = previous_point_data["latitude"], previous_point_data["longitude"]
                distance_km = haversine(prev_lat, prev_lon, lat, lon)
                time_delta_hours = time_increment_per_point_s / 3600.0
                if time_delta_hours > 1e-9:
                    current_point_processed["ground_speed_kmh"] = round(distance_km / time_delta_hours, 2)
                if distance_km > 0.001:
                    current_point_processed["bearing_deg"] = round(calculate_bearing(prev_lat, prev_lon, lat, lon), 2)
                elif previous_point_data.get("bearing_deg") is not None:
                     current_point_processed["bearing_deg"] = previous_point_data.get("bearing_deg")
            
            processed_points.append(current_point_processed)
            previous_point_data = current_point_processed
    return processed_points

# Part 3: Fetching Weather Data
# =============================
def get_weather_for_point(latitude, longitude, timestamp_utc_iso, api_key):
    if not api_key or api_key == "YOUR_ACTUAL_API_KEY_HERE":
        print("Error: OpenWeatherMap API key not set. Skipping weather fetch.")
        return None
    weather_url = f"http://api.openweathermap.org/data/2.5/forecast?lat={latitude}&lon={longitude}&appid={api_key}&units=metric"
    try:
        response = requests.get(weather_url, timeout=10)
        response.raise_for_status()
        weather_data_full = response.json()
        if str(weather_data_full.get("cod")) != "200": # API returns "cod" as string "200"
            print(f"Weather API Error for ({latitude},{longitude}): {weather_data_full.get('message')}")
            return None
        
        target_dt = datetime.fromisoformat(timestamp_utc_iso)
        closest_forecast, min_time_diff = None, float('inf')

        for forecast_entry in weather_data_full.get("list", []):
            forecast_dt_unix = forecast_entry.get("dt")
            if forecast_dt_unix:
                forecast_dt = datetime.fromtimestamp(forecast_dt_unix, timezone.utc)
                time_diff = abs((target_dt - forecast_dt).total_seconds())
                if time_diff < min_time_diff:
                    min_time_diff = time_diff
                    closest_forecast = forecast_entry
        
        if closest_forecast:
            wind_info = closest_forecast.get("wind", {})
            main_info = closest_forecast.get("main", {})
            weather_desc_list = closest_forecast.get("weather", [{}])
            return {
                "wind_speed_mps": wind_info.get("speed"),
                "wind_direction_deg": wind_info.get("deg"),
                "wind_gust_mps": wind_info.get("gust"),
                "weather_description": weather_desc_list[0].get("description") if weather_desc_list else None,
                "temperature_celsius": main_info.get("temp"),
                "pressure_hpa": main_info.get("pressure"),
                "data_timestamp_utc": datetime.fromtimestamp(closest_forecast.get("dt"), timezone.utc).isoformat(),
                "time_diff_to_actual_seconds": round(min_time_diff)
            }
        else: # Should not happen if API returns list but good to have
            # print(f"No suitable forecast found in OpenWeatherMap response for {timestamp_utc_iso} at ({latitude},{longitude})")
            return None
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error fetching weather for ({latitude},{longitude}): {http_err}")
    except requests.exceptions.RequestException as req_err:
        print(f"Request error fetching weather for ({latitude},{longitude}): {req_err}")
    except Exception as e:
        print(f"General error fetching/processing weather for ({latitude},{longitude}): {e}")
    return None

# Part 4: Main Execution Block
# ============================
if __name__ == "__main__":
    print("--- Windborne Systems Balloon Data Fetcher, Processor & Weather Integrator ---")

    # 1. Fetch raw Windborne data
    flight_data_archive = fetch_windborne_data()

    if not flight_data_archive:
        print("No data fetched from Windborne API. Exiting.")
    else:
        # (Optional: Save raw data)
        # with open("windborne_flight_data_archive.json", "w") as f:
        #     json.dump(flight_data_archive, f, indent=2)
        # print("\nRaw fetched data (flight_data_archive) saved to windborne_flight_data_archive.json")

        # 2. Process fetched Windborne data
        print("\n--- Starting Windborne Data Processing ---")
        processed_balloon_points = process_balloon_data(flight_data_archive)
        print(f"Successfully processed {len(processed_balloon_points)} individual balloon data points.")

        if not processed_balloon_points:
            print("No balloon points were processed successfully. Exiting.")
        else:
            # (Optional: Save processed Windborne data before weather integration)
            # with open("windborne_processed_flight_data_only.json", "w") as f:
            #     json.dump(processed_balloon_points, f, indent=2)
            # print("\nProcessed Windborne data (processed_balloon_points) saved to windborne_processed_flight_data_only.json")

            # 3. Integrate Weather Data (for a sample of points)
            print("\n--- Starting Weather Data Integration ---")
            if not OPENWEATHERMAP_API_KEY or OPENWEATHERMAP_API_KEY == "YOUR_ACTUAL_API_KEY_HERE":
                print("OpenWeatherMap API Key is not set. Skipping weather integration.")
                print("Please set the OPENWEATHERMAP_API_KEY variable at the top of the script.")
                points_with_weather = processed_balloon_points # No weather data added
            else:
                points_with_weather = []
                # Sort points by timestamp to process chronologically, if desired, though not strictly necessary here
                # processed_balloon_points.sort(key=lambda p: p['timestamp_utc']) 
                
                # We will add weather data to a *copy* of the points, or augment in place.
                # Let's augment in place for points up to MAX_WEATHER_CALLS
                
                calls_made = 0
                for i, point_data in enumerate(processed_balloon_points):
                    if calls_made < MAX_WEATHER_CALLS:
                        print(f"Fetching weather for point {i+1}/{len(processed_balloon_points)} (lat: {point_data['latitude']:.2f}, lon: {point_data['longitude']:.2f}, time: {point_data['timestamp_utc']})")
                        weather_info = get_weather_for_point(
                            point_data['latitude'],
                            point_data['longitude'],
                            point_data['timestamp_utc'],
                            OPENWEATHERMAP_API_KEY
                        )
                        point_data['weather'] = weather_info # Add weather info to the dictionary
                        calls_made += 1
                        if weather_info:
                            print(f"  -> Wind: {weather_info.get('wind_speed_mps')} m/s at {weather_info.get('wind_direction_deg')} deg. (Data for: {weather_info.get('data_timestamp_utc')})")
                        else:
                            print(f"  -> No weather data retrieved for this point.")
                        
                        if calls_made < MAX_WEATHER_CALLS and SECONDS_DELAY_BETWEEN_API_CALLS > 0:
                            # print(f"Waiting for {SECONDS_DELAY_BETWEEN_API_CALLS}s before next API call...")
                            time.sleep(SECONDS_DELAY_BETWEEN_API_CALLS)
                    else:
                        point_data['weather'] = None # For points beyond the limit

                points_with_weather = processed_balloon_points # The list now contains points, some augmented with weather

                print(f"\nWeather data integration attempted for {calls_made} points.")

            print("\n--- Sample of First 5 Processed Data Points (with weather if fetched) ---")
            for k in range(min(5, len(points_with_weather))):
                print(json.dumps(points_with_weather[k], indent=2,ensure_ascii=False))

            # Save the final augmented data
            output_filename = "windborne_data_with_weather.json"
            with open(output_filename, "w") as f:
                json.dump(points_with_weather, f, indent=2)
            print(f"\nAll processed data with weather information saved to {output_filename}")

    print("\n--- Script Finished ---")