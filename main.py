# import streamlit as st

from ui import get_selected_datetime, get_selected_location, get_shadow_profile, get_solar_panel, render_ui
from weather_checker import get_weather_data
from solar_calculation import get_sun_position, calculate_if_times_are_shadowed_with_shadow_profile, calculate_clearsky_power_output

import pandas as pd
import datetime

from config import STANDARD_STEP

# from src.calculations import compute_solar_power

#from config import xxx

def main():
    #st.set_page_config(page_title="Solar Panel Monitoring", layout="wide")
    
    # --- Streamlit UI Input ---

    selected_datetime = get_selected_datetime()
    selected_date = selected_datetime.date()
    
    selected_location = get_selected_location()

    shadow_profile = get_shadow_profile()

    selected_panel = get_solar_panel()

    
    # Define the daily time series with a frequency equal to step

    step = STANDARD_STEP
    times = pd.date_range(start=selected_date, end=selected_date + datetime.timedelta(days=1), freq=step, tz=selected_location.tz)
    
    # --- Fetch real-time weather data ---

    weather_data = get_weather_data(times,
                                    lat = selected_location.latitude, lon = selected_location.longitude,
                                    freq= step,                  # Added interpolation parameter
                                    std_timezone = selected_location.tz)
    
    # --- Compute solar data ---

    sun_position = get_sun_position(selected_datetime, selected_location)
    
    selected_datetime_shadowed = calculate_if_times_are_shadowed_with_shadow_profile(
        times=selected_datetime, 
        location=selected_location,
        shadow_profile=shadow_profile
    )['shadowed'].loc[selected_datetime]

    power_energy_data_clearsky = calculate_clearsky_power_output(times, selected_location, selected_panel, shadow_profile, weather_data)
    #solar_data = compute_solar_data(times, selected_location, shadow_profile, weather_data)
    
    # Render UI
    render_ui(selected_datetime, weather_data, sun_position, selected_datetime_shadowed, power_energy_data_clearsky) 

if __name__ == "__main__":
    main()