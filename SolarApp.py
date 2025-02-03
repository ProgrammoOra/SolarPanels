import streamlit as st
import datetime
from pytz import timezone
import pandas as pd
import numpy as np
import pvlib
from pvlib.location import Location
from pvlib import irradiance

class Panel:
    def __init__(self, tilt, azimuth, area, efficiency):
        self.tilt = tilt
        self.azimuth = azimuth
        self.area = area
        self.efficiency = efficiency

# --- Default Values ---
timezone = timezone('CET')
current_datetime = datetime.datetime.now(timezone)
default_date = current_datetime.date()
default_time = current_datetime.time()

# --- Streamlit UI ---
st.title("☀️ Solar Position & Energy Estimation")

# User inputs
selected_date = st.date_input("📅 Choose a Date:", value=default_date)
selected_time = st.time_input("⏰ Choose a Time:", value=default_time)

# Convert to datetime
selected_datetime = datetime.datetime.combine(selected_date, selected_time)#, tzinfo = timezone)
st.write(f"**Selected DateTime:** {selected_datetime}")
selected_datetime = datetime.datetime.combine(selected_date, selected_time, tzinfo = timezone)
st.write(f"**Selected DateTime:** {selected_datetime}")
st.write(f"**timezone:** {timezone}")

# --- Define Location ---
latitude = st.number_input("🌍 Latitude", value=45.4642)
longitude = st.number_input("🌍 Longitude", value=9.1900)
altitude = st.number_input("🏔️ Altitude (m)", value=144)
location = Location(latitude, longitude, altitude=altitude, tz=timezone, name='LocationPerCalcolo')

# --- User-defined Shadow Profile ---
st.sidebar.header("🌑 Shadow Profile")
shadow_azimuths = st.sidebar.text_area(
    "Enter shadow azimuth values (comma-separated)", "0, 151.9, 152, 209.9, 210, 287.9, 288, 360"
)
shadow_elevations = st.sidebar.text_area(
    "Enter shadow elevation values (comma-separated)", "80, 80,10,10,12,12,10,10"
)

# Convert shadow profile to list
shadow_azimuths = list(map(float, shadow_azimuths.split(",")))
shadow_elevations = list(map(float, shadow_elevations.split(",")))
shadow_profile = pd.DataFrame({"Azimuth": shadow_azimuths, "Elevation": shadow_elevations})
# Sort by Azimuth
shadow_profile = shadow_profile.sort_values(by="Azimuth", ascending=True)

# --- Solar Position Calculation ---
time = pd.DatetimeIndex([selected_datetime])
solar_position = location.get_solarposition(time)

# Extract values
sun_azimuth = round(solar_position["azimuth"].iloc[0], 1)
sun_elevation = round(solar_position["apparent_elevation"].iloc[0], 1)

# --- Check if Sun is Blocked by Shadow ---
def is_shadowed(sun_az, sun_el, shadow_profile):
    """Checks if the sun position is below the shadow profile."""
    for i in range(len(shadow_profile) - 1):
        if shadow_profile["Azimuth"].iloc[i] <= sun_az <= shadow_profile["Azimuth"].iloc[i + 1]:
            # Interpolate shadow elevation
            az1, el1 = shadow_profile.iloc[i]
            az2, el2 = shadow_profile.iloc[i + 1]
            shadow_el = el1 + (el2 - el1) * (sun_az - az1) / (az2 - az1)
            return sun_el < shadow_el
    return False

# Determine if the sun is blocked
shadowed = is_shadowed(sun_azimuth, sun_elevation, shadow_profile)

# --- PV System Inputs ---
st.sidebar.header("🔋 PV System Configuration")
panel_tilt = st.sidebar.slider("Panel Tilt (°)", 0, 90, 5)
panel_azimuth = st.sidebar.slider("Panel Azimuth (°)", 0, 360, 152)
panel_area = st.sidebar.number_input("Panel Area (m²)", value=6.25)
panel_efficiency = st.sidebar.slider("Panel Efficiency (%)", 0.0, 100.0, 16.5) / 100.0
panel = Panel(tilt=panel_tilt, azimuth=panel_azimuth, area=panel_area, efficiency= panel_efficiency)

# --- Calculate Energy Production (if sun is not shadowed) ---
if not shadowed:
    clearsky = pvlib.irradiance.get_total_irradiance(
        surface_tilt=panel_tilt,
        surface_azimuth=panel_azimuth,
        dni=800,  # Direct Normal Irradiance (W/m²)
        ghi=600,  # Global Horizontal Irradiance (W/m²)
        dhi=200,  # Diffuse Horizontal Irradiance (W/m²)
        solar_zenith=90 - sun_elevation,
        solar_azimuth=sun_azimuth
    )
    poa_irradiance = clearsky["poa_global"]
    power_output = poa_irradiance * panel_area * panel_efficiency  # Power in Watts
    energy = round(power_output.sum() / 1000, 2)  # Convert to kW
else:
    energy = 0.0

# --- 

def calculate_sun_times_for_date_with_shadow_profile(date, location, shadow_profile, step='1min'):
    """
    Calcola i momenti di irraggiamento solare in base a un profilo d'ombra definito da una serie di punti (azimuth, elevation).

    Args:
        date (datetime.date): Data per la quale calcolare i tempi.
        Location:
            latitude (float): Latitudine della location.
            longitude (float): Longitudine della location.
            time_zone (str): Fuso orario della location (default 'CET')
        shadow_profile (list[tuple]): Lista di tuple (azimuth, elevation) ordinate.
        step (str): Frequenza del campionamento temporale (default '1min').

    Returns:
        dict: Dizionario contenente la data, i momenti di irraggiamento solare (beginning_times)
              e le ore totali di irraggiamento calcolate come somma dei minuti.
    """
    
    # Funzione per interpolare l'elevation in base all'azimuth.
    def interpolate_elevation(azimuth):
        for i in range(len(shadow_profile) - 1):            
            az1, el1 = shadow_profile.iloc[i]
            az2, el2 = shadow_profile.iloc[i + 1]
            if az1 <= azimuth <= az2:                
                return el1 + (el2 - el1) * (azimuth - az1) / (az2 - az1)        
        return 0  # Default (non dovrebbe mai accadere se il profilo è corretto)

    # Crea una serie temporale per il giorno specifico.
    times = pd.date_range(start=date, end=date + datetime.timedelta(days=1), freq=step, tz=location.tz)

    # Calcola la posizione solare.
    solar_position = location.get_solarposition(times)

    # Filtra i momenti in cui il sole è sopra l'orizzonte e oltre il profilo d'ombra.
    solar_position['shadow_elevation'] = solar_position['azimuth'].apply(interpolate_elevation)
    condition = solar_position['elevation'] > solar_position['shadow_elevation']
    visible_times = solar_position[condition].index

    # Calcola le ore totali di sole come somma dei minuti.
    step_duration_minutes = pd.Timedelta(step).total_seconds() / 60
    total_solar_hours = round(len(visible_times) * step_duration_minutes / 60, 2)


    # Restituisce i risultati.
    return {
        'Date': date.strftime('%Y-%m-%d'),
        'Solar Times': visible_times,
        'Solar Hours': total_solar_hours
    }

def calculate_daily_energy_with_shadow_profile(date, location, panel, shadow_profile, step='1min'):
    """
    Calcola l'energia prodotta in un giorno specifico considerando un profilo d'ombra.
    
    Args:
        date: Data del giorno per cui calcolare l'energia.
        latitude (float): Latitudine della location.
        longitude (float): Longitudine della location.
        panel (object): Oggetto che rappresenta il pannello (con attributi tilt, azimuth, area, efficiency).
        shadow_profile (pd.DataFrame): Profilo d'ombra definito come serie di punti (azimuth, elevation).
        step (str): Frequenza temporale (esempio: '1min', '5min').
        time_zone: Fuso orario della location.
    
    Returns:
        float: Energia prodotta in kWh.
    """
    # Ottieni la serie temporale in cui il sole è visibile
    sun_times = calculate_sun_times_for_date_with_shadow_profile(
        date=date, 
        location=location,
        shadow_profile=shadow_profile, 
        step=step
    )

    # Estrai la serie temporale degli intervalli soleggiati
    solar_times = sun_times['Solar Times']
    if solar_times.empty:
        return 0.0  # Nessuna energia prodotta se non c'è irraggiamento attivo

    # Calcola le posizioni solari e i dati di irraggiamento per gli intervalli soleggiati
    solar_pos = location.get_solarposition(solar_times)
    clearsky = location.get_clearsky(solar_times)
    ghi = clearsky['ghi']
    dni = clearsky['dni']
    dhi = clearsky['dhi']

    # Irraggiamento totale sul piano del modulo
    total_irradiance = irradiance.get_total_irradiance(
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
    
    # Calcola l'energia totale prodotta in kWh, tenendo conto dello step
    step_minutes = pd.Timedelta(step).total_seconds() / 60  # Step in minuti
    total_energy = round(power_output.sum() * (step_minutes / 60 / 1000), 1)  # kWh

#    return total_energy
    return round(power_output, 1), total_energy

date_power_output, total_energy = calculate_daily_energy_with_shadow_profile(selected_date, location, panel, shadow_profile, step='1min')

# --- Display time Results ---
st.write("## ⏰ Time Solar Results ⏰")

st.write("### ☀️ Solar Position")
st.write(f"**Azimuth:** {sun_azimuth}° . . . . . . **Elevation:** {sun_elevation}")
#st.write(f"**Elevation:** {sun_elevation}°")

st.write("### 🌑 Shadow Analysis")
st.write(f"**Is the sun blocked by shadows?** {'✅ No' if not shadowed else '❌ Yes'}")

st.write("### 🔋 Energy Estimation")
st.write(f"**Power Output:** {energy} kW")


#  ---- Display Date Results   ----
st.write("## 📅  Day Solar Results")

st.write(f"**{selected_date} available energy:** {total_energy}kWh")
# --- Visualization ---
st.write("### 🔋 Power available ")
chart_power = date_power_output
chart_power.index = chart_power.index.strftime("%H:%M")
st.line_chart(chart_power)#[["azimuth", "apparent_elevation"]])
st.write("🔄 *Modify inputs to see real-time results!*")
