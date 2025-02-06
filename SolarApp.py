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

# --- Controllo ombra con interpolazione veloce ---
def is_shadowed(sun_az, sun_el, shadow_profile):
    shadow_el = np.interp(sun_az, shadow_profile["Azimuth"], shadow_profile["Elevation"])
    return sun_el < shadow_el

shadowed = is_shadowed(sun_azimuth, sun_elevation, shadow_profile)
st.write("shadowed: ", shadowed)

# --- Configurazione pannello solare ---
st.sidebar.header("🔋 PV System Configuration")
panel = Panel(
    tilt=st.sidebar.slider("Panel Tilt (°)", 0, 90, 5),
    azimuth=st.sidebar.slider("Panel Azimuth (°)", 0, 360, 152),
    area=st.sidebar.number_input("Panel Area (m²)", value=6.25),
    efficiency=st.sidebar.slider("Panel Efficiency (%)", 0.0, 100.0, 14.2) / 100.0
)

# --- Calcolo produzione energetica ---
if not shadowed:
    clearsky = location.get_clearsky(time)
    poa_irradiance = pvlib.irradiance.get_total_irradiance(
        surface_tilt=panel.tilt,
        surface_azimuth=panel.azimuth,
        dni=clearsky['dni'],
        ghi=clearsky['ghi'],
        dhi=clearsky['dhi'],
        solar_zenith=90 - sun_elevation,
        solar_azimuth=sun_azimuth
    )["poa_global"]
    
    power_output = poa_irradiance.sum() * panel.area * panel.efficiency
else:
    power_output = 0.0

st.write(f"**Power Output:** {power_output:.2f} W")


# --- 



def calculate_sun_times_for_date_with_shadow_profile(date, location, shadow_profile, step='1min'):
    """
    Calcola i momenti di irraggiamento solare in base a un profilo d'ombra definito da una serie di punti (azimuth, elevation).

    Args:
        date (datetime.date): Data per la quale calcolare i tempi.
        location (object): Oggetto con metodi per ottenere posizione solare.
        shadow_profile (pd.DataFrame): DataFrame con colonne ['azimuth', 'elevation'].
        step (str): Frequenza del campionamento temporale (default '1min').

    Returns:
        pd.DataFrame: 
            - 'Shadowed' (pd.Series): Maschera booleana che indica quando il sole è bloccato.
    """

    # Funzione per interpolare l'elevazione in base all'azimuth
    def interpolate_elevation(azimuth_values):
        return np.interp(azimuth_values, shadow_profile['Azimuth'], shadow_profile['Elevation'], left=0, right=0)

    # Crea una serie temporale per il giorno specifico
    times = pd.date_range(start=date, end=date + datetime.timedelta(days=1), freq=step, tz=location.tz)
    
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


def calculate_daily_energy_with_shadow_profile(date, location, panel, shadow_profile, step='1min'):
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
    shadow_times = calculate_sun_times_for_date_with_shadow_profile(
        date=date, 
        location=location,
        shadow_profile=shadow_profile, 
        step=step
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

    return power_output.round(1), total_energy




date_power_output, total_energy = calculate_daily_energy_with_shadow_profile(selected_date, location, panel, shadow_profile, step='1min')

#####  ------- Weather data --------

def get_cloud_cover(latitude, longitude, api_key):
    """
    Fetches real-time cloud cover data from OpenWeatherMap API.
    
    Parameters:
    - latitude: float
    - longitude: float
    - api_key: str (Your OpenWeatherMap API key)
    
    Returns:
    - cloud_cover: int (Cloud cover percentage 0-100)
    """
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={latitude}&lon={longitude}&appid={om_api_key}&units=metric"
    
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        cloud_cover = data['clouds']['all']  # Cloud cover percentage
        #print(f"Cloud Cover: {cloud_cover}% ({data['weather'][0]['description']})")
        return cloud_cover
    else:
        print("Error fetching weather data:", response.status_code, response.text)
        return None

import numpy as np

def adjust_irradiance_for_clouds(clearsky, cloud_cover, solar_zenith, shadowed=False):
    """
    Adjusts DNI, GHI, and DHI based on cloud cover and shadowing conditions.
    
    - clearsky: Dictionary with 'dni', 'ghi', 'dhi'
    - cloud_cover: Cloud cover percentage (0-100)
    - solar_zenith: Solar zenith angle (degrees)
    - shadowed: Boolean flag indicating whether the location is shadowed
    
    Returns adjusted DNI, GHI, and DHI.
    """
    cloud_fraction = cloud_cover / 100.0

    if shadowed:
        dni_adjusted = 0  # Direct normal irradiance is blocked
        ghi_adjusted = clearsky['ghi'] * (1 - 0.75 * cloud_fraction)  # Keep cloud effect
        dhi_adjusted = ghi_adjusted  # Assume all GHI is diffuse under shadowed conditions
    else:
        # Adjust DNI based on cloud cover
        dni_adjusted = clearsky['dni'] * (1 - 1.1 * cloud_fraction)
        dni_adjusted = np.clip(dni_adjusted, 0, None)  # Ensure DNI is not negative

        # Adjust GHI based on empirical attenuation model
        ghi_adjusted = clearsky['ghi'] * (1 - 0.75 * cloud_fraction)

        # Compute DHI from adjusted GHI and DNI
        dhi_adjusted = ghi_adjusted - dni_adjusted * np.cos(np.radians(solar_zenith))
        dhi_adjusted = np.clip(dhi_adjusted, 0, None)

    return dni_adjusted, ghi_adjusted, dhi_adjusted


def calculate_power_output(location, times, panel, api_key, shadowed=False):
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
    cloud_cover = get_cloud_cover(location.latitude, location.longitude, api_key)
    if cloud_cover is None:
        cloud_cover = 0  # Default to clear sky if API fails

    # Adjust irradiance
    dni_adj, ghi_adj, dhi_adj = adjust_irradiance_for_clouds(
        clearsky, cloud_cover, solar_pos['apparent_zenith'],
        shadowed
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

power_output_weather = calculate_power_output(location, time, panel, om_api_key, shadowed)
power_output_w = power_output_weather[0]



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
    st.write(f"#### 🌑 Sun in shadows?     {'✅ No' if not shadowed else '❌ Yes'}")
    st.write(get_cloud_cover(location.latitude, location.longitude, om_api_key)/100) ### qui solo per testare output
with col2:
    st.write(f"#### 🔋 **Panel Output:** {round(power_output,0)}")
    st.write(f"#### 🔋 **Panel Output W:** {round(power_output_w,0)}")


#  ---- Display Date Results   ----
st.write(f"## 📅  Day Results for: {selected_date}")

st.write(f"#### Total available energy: {total_energy}kWh")

# --- Visualization ---
st.write("### 🔋 Power available ")

# Create the chart
fig = px.scatter(
    date_power_output, x=date_power_output.index, y='poa_global',
    labels={'x': 'Day Time', 'poa_global': 'W'},
    color_discrete_sequence=['green'],  # Optional: change dot color
    size_max=10  # Optional: control dot size
)

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
