import streamlit as st
import datetime
from pytz import timezone
import pandas as pd
import numpy as np
import pvlib
from pvlib.location import Location
from pvlib import irradiance
import plotly.express as px
import requests

om_api_key = st.secrets['om_api_key']


class Panel:
    def __init__(self, tilt, azimuth, area, efficiency):
        self.tilt = tilt
        self.azimuth = azimuth
        self.area = area
        self.efficiency = efficiency

# --- Default Values ---
timezone = timezone('Europe/Rome') # 'Europe/Rome' gestisce il cambio fuso orario diversamente da 'CET' 
current_datetime = datetime.datetime.now(timezone)
#default_date = current_datetime.date()
#default_time = current_datetime.time()


# --- Streamlit UI ---
st.title("☀️ Sun & Panels")

# Inizializzazione della sessione
if "selected_datetime" not in st.session_state:
    st.session_state.selected_datetime = current_datetime

#------- Input dell'utente

# Create two columns for side-by-side layout
col1, col2 = st.columns(2)

# Input for date in the first column
with col1:
    selected_date = st.date_input("📅 Choose a Date:", value=st.session_state.selected_datetime.date())

# Input for time in the second column
with col2:
    selected_time = st.time_input("⏰ Choose a Time:", value=st.session_state.selected_datetime.time().replace(microsecond=0))


# Aggiorna `st.session_state` se l'utente cambia data o ora
new_datetime = timezone.localize(datetime.datetime.combine(selected_date, selected_time))
if new_datetime != st.session_state.selected_datetime:
    st.session_state.selected_datetime = new_datetime
    st.rerun()  # Ensures immediate UI update

st.write(f"**Selected DateTime:** {st.session_state.selected_datetime}")

# --- Define Location ---
latitude = st.sidebar.number_input("🌍 Latitude", value=45.5)
longitude = st.sidebar.number_input("🌍 Longitude", value=9.1900)
altitude = st.sidebar.number_input("🏔️ Altitude (m)", value=144)
location = Location(latitude, longitude, altitude=altitude, tz=timezone, name='LocationPerCalcolo')

# --- User-defined Shadow Profile ---
st.sidebar.header("🌑 Shadow Profile")
shadow_azimuths = st.sidebar.text_area(
    "Enter shadow azimuth values (comma-separated)", "0, 151.9, 152, 209.9, 210, 287.9, 288, 360"
)
shadow_elevations = st.sidebar.text_area(
    "Enter shadow elevation values (comma-separated)", "80, 80, 10, 10, 14, 14, 10, 10"
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

# --- Calcolo della posizione solare ---
time = pd.DatetimeIndex([st.session_state.selected_datetime])
solar_position = location.get_solarposition(time)
sun_azimuth = round(solar_position["azimuth"].iloc[0], 1)
sun_elevation = round(solar_position["apparent_elevation"].iloc[0], 1)


# --- Configurazione pannello solare ---
st.sidebar.header("🔋 PV System Configuration")
panel = Panel(
    tilt=st.sidebar.slider("Panel Tilt (°)", 0, 90, 5),
    azimuth=st.sidebar.slider("Panel Azimuth (°)", 0, 360, 152),
    area=st.sidebar.number_input("Panel Area (m²)", value=6.25),
    efficiency=st.sidebar.slider("Panel Efficiency (%)", 0.0, 100.0, 14.2) / 100.0
)



# --- 



def calculate_if_times_are_shadowed_with_shadow_profile(times, location, shadow_profile):
    """
    Calcola i momenti di irraggiamento solare in base a un profilo d'ombra definito da una serie di punti (azimuth, elevation).

    Args:
        times (datetime): momenti per la quale calcolare i tempi.
        location (object): Oggetto con metodi per ottenere posizione solare.
        shadow_profile (pd.DataFrame): DataFrame con colonne ['azimuth', 'elevation'].

    Returns:
        pd.DataFrame: 
            - 'Shadowed' (pd.Series): Maschera booleana che indica quando il sole è bloccato.
    """

    # Funzione per interpolare l'elevazione in base all'azimuth
    def interpolate_elevation(azimuth_values):
        return np.interp(azimuth_values, shadow_profile['Azimuth'], shadow_profile['Elevation'], left=0, right=0)

    # Crea una serie temporale per il giorno specifico
    # times = pd.date_range(start=date, end=date + datetime.timedelta(days=1), freq=step, tz=location.tz)
    
    # Calcola la posizione solare
    solar_position = location.get_solarposition(times)

    # Interpola l'elevazione d'ombra corrispondente all'azimuth del sole
    solar_position['shadow_elevation'] = interpolate_elevation(solar_position['azimuth'])

    # Condizione per cui il sole è sopra l'orizzonte e non coperto dall'ombra
    shadow_mask = solar_position['elevation'] < solar_position['shadow_elevation']

    # Crea il DataFrame di output
    shadowed_df = pd.DataFrame({
        'datetime': times,
        'Shadowed': shadow_mask.values  # Converti in array per evitare problemi con l'indice
    })
    shadowed_df = shadowed_df.set_index('datetime')

    return shadowed_df


def calculate_times_power_and_energy_with_shadow_profile(times, location, panel, shadow_profile, step='1min'):
    """
    Calcola l'energia prodotta in un giorno specifico considerando un profilo d'ombra.
    
    Args:
        date (datetime): Data del giorno per cui calcolare l'energia.
        location (object): Oggetto con metodi per ottenere posizione solare e dati di irraggiamento.
        panel (object): Oggetto che rappresenta il pannello (con attributi tilt, azimuth, area, efficiency).
        shadow_profile (pd.DataFrame): Profilo d'ombra definito come serie di punti (azimuth, elevation).
        step (str): Frequenza temporale (esempio: '1min', '5min').
    
    Returns:
        tuple: (array di potenza istantanea in W, energia totale prodotta in kWh).
    """
        
    # Ottieni la serie temporale con info sulla visibilità del sole
    shadow_times = calculate_if_times_are_shadowed_with_shadow_profile(
        times=times, 
        location=location,
        shadow_profile=shadow_profile
    )

    # Se non ci sono dati di ombra, nessuna energia prodotta
    if shadow_times.empty:
        return np.array([]), 0.0

    # Ottieni posizione solare e dati di irraggiamento
    solar_pos = location.get_solarposition(shadow_times.index)
    clearsky = location.get_clearsky(shadow_times.index)

    # Estrai le componenti dell'irraggiamento
    dni = clearsky['dni'].copy()
    ghi = clearsky['ghi'].copy()
    dhi = clearsky['dhi'].copy()

    # Applica il profilo d'ombra ai dati di irraggiamento
    dni[shadow_times['Shadowed']] = 0  

    # Calcola l'irraggiamento totale sul piano del modulo
    total_irradiance = pvlib.irradiance.get_total_irradiance(
        surface_tilt=panel.tilt,
        surface_azimuth=panel.azimuth,
        dni=dni,
        ghi=ghi,
        dhi=dhi,
        solar_zenith=solar_pos['apparent_zenith'],
        solar_azimuth=solar_pos['azimuth']
    )

    poa_irradiance = total_irradiance['poa_global']
    power_output = poa_irradiance * panel.area * panel.efficiency  # Potenza istantanea in W

    # Calcola l'energia totale in kWh
    step_minutes = pd.Timedelta(step).total_seconds() / 60  # Step in minuti
    total_energy = round(power_output.sum() * (step_minutes / 60 / 1000), 1)  # kWh

    return power_output.round(0), total_energy

# Calcola power output per l'ora specifica
step = '1min'
time = pd.DatetimeIndex([st.session_state.selected_datetime])
actual_power_output, total_energy = calculate_times_power_and_energy_with_shadow_profile(time, location, panel, shadow_profile, step=step)


# Crea una serie temporale per il giorno specifico con una frequenza pari a step
step = '1min'
times = pd.date_range(start=selected_date, end=selected_date + datetime.timedelta(days=1), freq=step, tz=location.tz)

# calcola potenza per ogni step e energia totale
date_power_output, total_energy = calculate_times_power_and_energy_with_shadow_profile(times, location, panel, shadow_profile, step=step)

# calculate_power_output(location, times, panel, api_key, shadowed

#####  ------- Weather data --------

def get_cloud_cover(times, lat, lon, openweather_api_key, freq="1min", timezone = 'Europe/Rome'): # Added interpolation parameter
    """
    Fetches cloud cover for today with specified frequency:
    - 100% cloudiness for all times before now
    - Forecast data from OpenWeather until end of day (handling 3-hour intervals)
    times = series of one day times
    """

    now = datetime.datetime.now(timezone)
    # limit times to the cloud available data: now + 5 days
    times = times[(times >= now.replace(second=0, microsecond=0)) & (times<= now + datetime.timedelta(days=5)) ]
    
    if times.empty:
        return False

    full_day_times = times        
    full_day_df = pd.DataFrame(index=full_day_times)

    print(f"\n full_day_df pre actual data troncato?:\n {full_day_df})") #############
    print()
    
    ##### rimosse perchè ora partiamo minimo da times
    # before_now_times = full_day_times[full_day_times < now] ######## <= end_of_day] ########now]
    #full_day_df.loc[before_now_times, 'cloud_cover'] = np.nan

    # Get Actual Weather
    openweather_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={openweather_api_key}&units=metric"
    response = requests.get(openweather_url).json()

    actual_data = []
    actual_time = now
    actual_data.append({'datetime': actual_time, 'cloud_cover': response['clouds']['all']})

    actual_df = pd.DataFrame(actual_data)
    actual_df.set_index('datetime', inplace=True)
    full_day_df = full_day_df.combine_first(actual_df)
    
    # --------  Get forecast
    
    openweather_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={openweather_api_key}&units=metric"
    response = requests.get(openweather_url).json()

    forecast_data = []
    for entry in response['list']:
        forecast_time = datetime.datetime.utcfromtimestamp(entry['dt']).replace(tzinfo=datetime.timezone.utc)
        forecast_time = forecast_time.astimezone(timezone)
        forecast_data.append({'datetime': forecast_time, 'cloud_cover': entry['clouds']['all']})

    forecast_df = pd.DataFrame(forecast_data)
    forecast_df.set_index('datetime', inplace=True)
    
    full_day_df = full_day_df.combine_first(forecast_df)
    
    full_day_df['cloud_cover'] = full_day_df['cloud_cover'].interpolate(method='linear', limit_direction='both')
    full_day_df = full_day_df.reindex(full_day_times)

    return full_day_df


        


def adjust_irradiance_for_clouds_and_shadow(times, clearsky, cloud_cover, solar_zenith, shadow_profile):
    """
    Adjusts DNI, GHI, and DHI based on cloud cover and shadowing conditions.
    
    - clearsky: Dictionary with 'dni', 'ghi', 'dhi'
    - cloud_cover: Cloud cover percentage (0-100)
    - solar_zenith: Solar zenith angle (degrees)
    - shadowed: Boolean flag indicating whether the location is shadowed
    
    Returns adjusted DNI, GHI, and DHI.
    """
    cloud_fraction = cloud_cover / 100.0

# Ottieni la serie temporale con info sulla visibilità del sole
    shadow_times = calculate_if_times_are_shadowed_with_shadow_profile(
        times=times, 
        location=location,
        shadow_profile=shadow_profile
    )

    # Se non ci sono dati di ombra, nessuna energia prodotta
    if shadow_times.empty:
        return np.array([]), 0.0

    clearsky = clearsky.reindex(times)
    cloud_fraction = cloud_fraction.reindex(times)
    
    dni_adjusted = clearsky['dni'] * ((1 - 1.1 * cloud_fraction['cloud_cover'])) 
    dni_adjusted = np.clip(dni_adjusted, 0, None)  # Ensure DNI is not negative
    
    # Applica il profilo d'ombra ai dati di irraggiamento
    dni_adjusted[shadow_times['Shadowed']] = 0  
    
    # Adjust GHI based on empirical attenuation model
    ghi_adjusted = clearsky['ghi'] * (1.05 - 0.75 * cloud_fraction['cloud_cover']) ##### modificato 1 - 0.75.. in 1.05 -0.75... per aumentare l'impatto del GHI

    # Compute DHI from adjusted GHI and DNI
    dhi_adjusted = ghi_adjusted - dni_adjusted * np.cos(np.radians(solar_zenith))
    dhi_adjusted = np.clip(dhi_adjusted, 0, None)

    return dni_adjusted, ghi_adjusted, dhi_adjusted


def calculate_power_output(location, times, panel, api_key, shadow_profile):
    """
    Calculates solar panel power output considering cloud cover.
    
    - latitude, longitude: Location coordinates
    - times: Pandas DatetimeIndex
    - panel: Dictionary with 'tilt', 'azimuth', 'area', 'efficiency'
    - api_key: OpenWeatherMap API key

    Returns: Power output series
    """

    # Get solar position
    solar_pos = location.get_solarposition(times)

    # Get clear-sky irradiance
    clearsky = location.get_clearsky(times)

    # Fetch real-time cloud cover
    cloud_cover = get_cloud_cover(times, location.latitude, location.longitude, api_key, timezone = timezone)
    if cloud_cover is None:
        cloud_cover['cloud_cover'] = 0  # Default to clear sky if API fails ########### mettere un NA e non mostrare il grafico

    # Adjust irradiance
    dni_adj, ghi_adj, dhi_adj = adjust_irradiance_for_clouds_and_shadow(
        times,
        clearsky, cloud_cover, solar_pos['apparent_zenith'],
        shadow_profile
    )
    
    # Compute POA irradiance
    total_irradiance = pvlib.irradiance.get_total_irradiance(
        surface_tilt=panel.tilt,
        surface_azimuth=panel.azimuth,
        dni=dni_adj,
        ghi=ghi_adj,
        dhi=dhi_adj,
        solar_zenith=solar_pos['apparent_zenith'],
        solar_azimuth=solar_pos['azimuth']
    )

    poa_irradiance = total_irradiance['poa_global']

    # Compute power output
    power_output = poa_irradiance * panel.area * panel.efficiency  # Watts

    return power_output

power_output_weather = calculate_power_output(location, time, panel, om_api_key, shadow_profile)

power_output_w = power_output_weather[0]

time_shadowed = calculate_if_times_are_shadowed_with_shadow_profile(
        times=time, 
        location=location,
        shadow_profile=shadow_profile
    )

# calculate power output taking into account cloudiness
date_power_output_w = calculate_power_output(location, times, panel, om_api_key, shadow_profile)

# combine in a single dataframe
#date_power_output_w.index = pd.to_datetime(date_power_output_w.index) ##################
date_power_output_w = date_power_output_w.rename_axis('datetime')

# Ensure date_power_output is a DataFrame
date_power_output = date_power_output.to_frame()  # Convert Series to DataFrame if needed

# Reindex date_power_output_w to align with date_power_output index
date_power_output['poa_global_w'] = date_power_output_w


#date_power_output['poa_global_w'] = date_power_output_w

# --- Display time Results ---
st.write("## ⏰ Time Results")

# Create two columns for side-by-side layout
col1, col2 = st.columns(2)
# Input for date in the first column
with col1:
    st.write("#### ☀️ Sun Position (Az., Elev.):")
with col2:
    st.write(f"#### {sun_azimuth}° , {sun_elevation}°")

# Create two columns for side-by-side layout
col1, col2 = st.columns(2)
with col1:
    st.write(f"#### 🌑 Sun in shadows?     {'✅ No' if not time_shadowed['Shadowed'][0] else '❌ Yes'}")
    actual_cloud_cover =  get_cloud_cover(time, location.latitude, location.longitude, om_api_key, timezone = timezone).iloc[0]['cloud_cover']
    st.write(f"#### CL Clowd cover:        {int(actual_cloud_cover)}%") ### qui solo per testare output 
    ##### ottimizzabile dal calcolo del giorno?
with col2:
    st.write(f"#### 🔋 **ClearSky PV Output:** {int(actual_power_output[0])}W")
    st.write(f"#### 🔋 **Actual PV Output:** {int(round(power_output_w,0))}W")


#  ---- Display Date Results   ----
st.write(f"## 📅  Day Results for: {selected_date}")

st.write(f"#### Total available energy: {total_energy}kWh")


# --- Visualization ---
st.write("### 🔋 ClearSky and Cloudy  power available ")

fig = px.line(
    date_power_output, x=date_power_output.index, 
    y=['poa_global', 'poa_global_w'],  # Pass both columns here
    labels={'x': 'Day Time', 'poa_global': 'W', 'poa_global_w': 'W with cloud forecast'},  # Customize labels for clarity
    color_discrete_sequence=['green', 'blue']  # Different colors for the two series
)

fig.update_traces(line=dict(width=5))  # Adjust the width as needed

fig.update_xaxes(
    range=[
        pd.Timestamp(f"{selected_date} 06:00"),  # Start at 6 AM
        pd.Timestamp(f"{selected_date} 22:00")   # End at 10 PM
    ],
    tickformat='%H:%M',  # Format labels as HH:MM (e.g., "06:00", "08:00")
    dtick=3600 * 2 * 1000  # Show a tick every 2 hours
)

# Display the chart in Streamlit
st.plotly_chart(fig)