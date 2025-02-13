# import streamlit as st

from ui import get_selected_datetime, get_selected_location, get_shadow_profile, get_solar_panel, render_ui_modern_with_tabs
from weather_checker import get_weather_data
from solar_calculation import get_sun_position, calculate_if_times_are_shadowed_with_shadow_profile
from solar_calculation import calculate_clearsky_power_output, calculate_weather_power_output, calculate_energy_for_times
from home_power_usage_checker import get_actual_home_power

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

    clearsky_power_data = calculate_clearsky_power_output(times, selected_location, selected_panel, shadow_profile, weather_data)
    weather_power_data = calculate_weather_power_output(times, selected_location, selected_panel, shadow_profile, weather_data)

    times_clearsky_energy = calculate_energy_for_times(times, step, clearsky_power_data)
    times_weather_energy = calculate_energy_for_times(times, step, weather_power_data)

    # --- Fetch real-time home usage data ---

    home_pv_power, network_pv_power = get_actual_home_power()
    
    # Render UI
    #render_ui(selected_datetime, weather_data, 
    #         sun_position, selected_datetime_shadowed,
    #        clearsky_power_data, weather_power_data,
    #       times_clearsky_energy, times_weather_energy,
    #      home_pv_power, network_pv_power) 
    

    render_ui_modern_with_tabs(selected_datetime, 
                     weather_data, 
                     sun_position, 
                     selected_datetime_shadowed, 
                     clearsky_power_data, weather_power_data,
                     times_clearsky_energy, 
                     times_weather_energy,
                     home_pv_power, 
                     network_pv_power,
                     pd.DataFrame(), pd.DataFrame())

if __name__ == "__main__":
    main()