import streamlit as st
import datetime
from pytz import timezone
from pvlib.location import Location

import pandas as pd
import plotly.express as px

from config import ITALY_TIMEZONE, STANDARD_LOCATION_LATITUDE, STANDARD_LOCATION_LONGITUDE, STANDARD_LOCATION_ALTITUDE
from config import STANDARD_SHADOW_AZIMUTHS, STANDARD_SHADOWS_ELEVATIONS
from config import STANDARD_PANEL_TILT, STANDARD_PANEL_AZIMUTH, STANDARD_PANEL_AREA, STANDARD_PANEL_EFFICIENCY

### ---- Default Values ----------------------------------------------------

timezone = timezone(ITALY_TIMEZONE)  
current_datetime = datetime.datetime.now(timezone)

#### ---- Get Date and time ----------------------------------------------------

def get_selected_datetime():

    # Inizializzazione della sessione
    if "selected_datetime" not in st.session_state:
        st.session_state.selected_datetime = current_datetime
    
    # ------- UI Title, verify if it shoud be moved somewhere else (not in this function)
    
    st.title("☀️ Sun & Panels")

    # ------- Input dell'utente -----------

    # Create two columns for side-by-side layout
    col1, col2 = st.columns(2)

    # Input for date in the first column
    with col1:
        selected_date = st.date_input("📅 Choose a Date:", value=st.session_state.selected_datetime.date())

    # Input for time in the second column
    with col2:
        selected_time = st.time_input("⏰ Choose a Time:", value=st.session_state.selected_datetime.time().replace(second=0, microsecond=0))


    # Aggiorna `st.session_state` se l'utente cambia data o ora
    new_datetime = timezone.localize(datetime.datetime.combine(selected_date, selected_time))
    if new_datetime != st.session_state.selected_datetime:
        st.session_state.selected_datetime = new_datetime.replace(second=0, microsecond=0)
        st.rerun()  # Ensures immediate UI update

    #st.write(f"**Selected DateTime:** {st.session_state.selected_datetime}")

    return st.session_state.selected_datetime

#### ---- Get location ----------------------------------------------------

def get_selected_location(std_latitude = STANDARD_LOCATION_LATITUDE, 
                          std_longitude = STANDARD_LOCATION_LONGITUDE, 
                          std_altitude = STANDARD_LOCATION_ALTITUDE):
    
    # --- Define Location ---
    latitude = st.sidebar.number_input("🌍 Latitude", value= std_latitude)
    longitude = st.sidebar.number_input("🌍 Longitude", value= std_longitude)
    altitude = st.sidebar.number_input("🏔️ Altitude (m)", value= std_altitude)
    location = Location(latitude, longitude, altitude=altitude, tz=timezone, name='LocationPerCalcolo')

    return location

#### ---- Get shadow profile ----------------------------------------------------

def get_shadow_profile(std_shadow_azimuths = STANDARD_SHADOW_AZIMUTHS,
                       std_shadow_elevations = STANDARD_SHADOWS_ELEVATIONS):
    
    # --- User-defined Shadow Profile ---
    st.sidebar.header("🌑 Shadow Profile")
    shadow_azimuths = st.sidebar.text_area(
        "Enter shadow azimuth values (comma-separated)", std_shadow_azimuths
    )
    shadow_elevations = st.sidebar.text_area(
        "Enter shadow elevation values (comma-separated)", std_shadow_elevations
    )

    # Conversione degli input
    try:
        shadow_azimuths = list(map(float, shadow_azimuths.split(",")))
        shadow_elevations = list(map(float, shadow_elevations.split(",")))
        shadow_profile = pd.DataFrame({"Azimuth": shadow_azimuths, "Elevation": shadow_elevations}).sort_values(by="Azimuth")
    except ValueError:
        st.error("Error: Please enter valid numerical values for the shadow profile.")
        st.stop()

    st.sidebar.line_chart(shadow_profile.set_index("Azimuth")[["Elevation"]])

    return shadow_profile

#### ---- Get panel data ----------------------------------------------------

def get_solar_panel(std_panel_tilt = STANDARD_PANEL_TILT,
                   std_panel_azimuth = STANDARD_PANEL_AZIMUTH,
                   std_panel_area = STANDARD_PANEL_AREA,
                   std_panel_efficiency= STANDARD_PANEL_EFFICIENCY
                   ):
    
    st.sidebar.header("🔋 PV System Configuration")
    panel = {
        'tilt' : st.sidebar.slider("Panel Tilt (°)", 0, 90, 5),
        'azimuth' : st.sidebar.slider("Panel Azimuth (°)", 0, 360, 152),
        'area' : st.sidebar.number_input("Panel Area (m²)", value=6.25),
        'efficiency' : st.sidebar.slider("Panel Efficiency (%)", 0.0, 100.0, 14.2) / 100.0
    }

    return panel

#### ---- Get weather results for selected date ----------------------------------------------------

def get_weather_results(selected_datetime, weather_data):

    selected_time_weather = weather_data['times_cloud_cover'].loc[selected_datetime]

#### ---- Render output data ----------------------------------------------------

def render_ui (selected_datetime, weather_data, sun_position, selected_datetime_shadowed, clearsky_power_energy_data):
    
    # --- Display time Results ---
    
    st.write("## ⏰ Time Results")

    # -- Provide sun position --

    # Create two columns for side-by-side layout
    col1, col2 = st.columns(2)
    # Input for date in the first column
    with col1:
        st.write("#### ☀️ Sun Position (Az., Elev.):")
    with col2:
        st.write(f"#### {sun_position['azimuth']}° , {sun_position['elevation']}°") ###### remove ","

    # -- Provide weather output --
    
    # Create two columns for side-by-side layout
    col1, col2 = st.columns(2)
    # Input for date in the first column

    max_forecast_datetime = weather_data['actual_weather'][0]['datetime']+ datetime.timedelta(days=5)
    max_forecast_available = f"Forecast available only until {max_forecast_datetime.date()} at {max_forecast_datetime.time()}"
    
    with col1:
        st.write("#### ☀️☁️🌧️ Weather Condition:")
    with col2:
        
        if weather_data['times_cloud_cover'].empty:  # the selected datetime does not have forecast or historical data
            
            if selected_datetime < weather_data['actual_weather'][0]['datetime']:  
                
                # the selected datetime does not have historical data
                st.write(f"### ❌")
                st.write("No historical weather data available")
                
            else:     # the selected datetime does not have forecast data
                st.write(f"### ❌")
                st.write(f"{max_forecast_available}")
            
        else:         # the selected date has forecast data
            if selected_datetime < weather_data['times_cloud_cover'].iloc[0].name:

                # the selected datetime is before the time with forecast data                
                st.write(f"### ❌")
                st.write("No historical weather data available")
                
            else:    # forecast data is available!

                if selected_datetime > weather_data['times_cloud_cover'].iloc[-1].name:

                    # the selected datetime is after the time with forecast data                
                    st.write(f"### ❌")
                    st.write(f"{max_forecast_available}")

                else:

                    selected_time_weather = weather_data['times_cloud_cover'].loc[selected_datetime]
        
                    # Weather icon
                    icon_url = f"https://openweathermap.org/img/wn/{selected_time_weather['weather_icon']}@2x.png"
                    st.markdown(f"### !['wheather icon']({icon_url}) {selected_time_weather['weather_description']}")
        
                    if int(selected_time_weather['weather_code']/100) == 8:
                    
                        st.write(f"""
                        <div style="text-align: center;">🌥️ Clowd cover:        {int(selected_time_weather['cloud_cover'])}%</div>
                        """,
                                 unsafe_allow_html=True)

    
    # -- Provide power output for the selected time --
    
    # Create two columns for side-by-side layout
    col1, col2 = st.columns(2)
    
    with col1:
        st.write(f"#### 🏘️ Shadowed Sun?     {'✅ No' if not selected_datetime_shadowed else '❌ Yes'}")    
        
    with col2:

        selected_time_clearsky_power = int(round(clearsky_power_energy_data.loc[selected_datetime],0))
        #selected_time_weather_power = int(round(weather_power_energy_data.loc[selected_datetime],0))
        
        
        st.write(f"#### 🔋 **ClearSky PV Output:** {selected_time_clearsky_power}W")
        st.write(f"#### 🔋 **Actual PV Output:**"," {selected_time_weather_power}W")   ###### remove ","


    #  ---- Display Date Results   ----
    st.write(f"## 📅  Day Results for: {selected_datetime.date()}")

    st.write(f"#### Total available energy: ","{total_energy}kWh")     ###### remove ","

    
    # --- Visualization ---
    st.write("### 🔋 ClearSky and Cloudy  power available ")

    date_power_output = clearsky_power_energy_data
    
    fig = px.line(
        date_power_output, x=date_power_output.index, 
        y=['poa_global'],     # 'poa_global_w'],  # Pass both columns here
        labels={'x': 'Day Time', 'ClearSky Power': 'W'},   # 'poa_global_w': 'W with cloud forecast'},  # Customize labels for clarity
        color_discrete_sequence=['green']      #, 'blue']  # Different colors for the two series
    )

    fig.update_traces(line=dict(width=5))  # Adjust the width as needed

    fig.update_xaxes(
        range=[
            pd.Timestamp(f"{selected_datetime.date()} 06:00"),  # Start at 6 AM
            pd.Timestamp(f"{selected_datetime.date()} 22:00")   # End at 10 PM
        ],
        tickformat='%H:%M',  # Format labels as HH:MM (e.g., "06:00", "08:00")
        dtick=3600 * 2 * 1000  # Show a tick every 2 hours
    )

    # Display the chart in Streamlit
    st.plotly_chart(fig)





#### Main function to test module  ############

def main():
    # --- Streamlit UI ---

    selected_datetime = get_selected_datetime()
    
    selected_location = get_selected_location()

    shadow_profile = get_shadow_profile()

if __name__ == "__main__":
    main()
    