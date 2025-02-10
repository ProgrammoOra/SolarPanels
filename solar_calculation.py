from pvlib.location import Location
from pvlib import irradiance

import pandas as pd
import numpy as np

def get_sun_position(selected_datetime, selected_location):
    
    solar_position = selected_location.get_solarposition(selected_datetime)
    sun_azimuth = round(solar_position["azimuth"].iloc[0], 1)
    sun_elevation = round(solar_position["apparent_elevation"].iloc[0], 1)

    sun_position = {'azimuth': sun_azimuth,
                    'elevation': sun_elevation}

    return sun_position

def calculate_if_times_are_shadowed_with_shadow_profile(times, location, shadow_profile):
    """
    Calcola i momenti di irraggiamento solare in base a un profilo d'ombra definito da una serie di punti (azimuth, elevation).

    Args:
        times (datetime): momenti per la quale calcolare i tempi.
        location (object): Oggetto con metodi per ottenere posizione solare.
        shadow_profile (pd.DataFrame): DataFrame con colonne ['azimuth', 'elevation'].

    Returns:
        pd.DataFrame: 
            - 'shadowed' (pd.Series): Maschera booleana che indica quando il sole è bloccato.
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
        'shadowed': shadow_mask.values  # Converti in array per evitare problemi con l'indice
    })
    shadowed_df = shadowed_df.set_index('datetime')

    return shadowed_df

# --- Calculate power output for give times, shadow profile and weather data

def adjust_irradiance_for_clouds_and_shadow(times, location, clearsky, cloud_cover, solar_zenith, shadow_profile):
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
    
    dni_adjusted = clearsky['dni'] * ((1 - 1.1 * cloud_fraction)) # ['cloud_cover'])) 
    dni_adjusted = np.clip(dni_adjusted, 0, None)  # Ensure DNI is not negative
    
    # Applica il profilo d'ombra ai dati di irraggiamento
    dni_adjusted[shadow_times['shadowed']] = 0  
    
    # Adjust GHI based on empirical attenuation model
    ghi_adjusted = clearsky['ghi'] * (1.0 - 0.75 * cloud_fraction) ##### modificato 1 - 0.75.. in 1.05 -0.75... per aumentare l'impatto del GHI

    # Compute DHI from adjusted GHI and DNI
    dhi_adjusted = ghi_adjusted - dni_adjusted * np.cos(np.radians(solar_zenith))
    dhi_adjusted = np.clip(dhi_adjusted, 0, None)

    return dni_adjusted, ghi_adjusted, dhi_adjusted


def calculate_power_output(times, selected_location, selected_panel, shadow_profile, weather_data):
    """
    Calculates solar panel power output considering cloud cover.
    
    - times: Pandas DatetimeIndex
    - selected_location: 
    - selected_panel: Dictionary with 'tilt', 'azimuth', 'area', 'efficiency'
    - shadow_profile
    - weather_data

    Returns: Power output series
    """

    # Get solar position
    solar_pos = selected_location.get_solarposition(times)

    # Get clear-sky irradiance
    clearsky = selected_location.get_clearsky(times)

    # check cloud cover data 
    cloud_cover = weather_data['times_cloud_cover']['cloud_cover']
    if cloud_cover is None:
        cloud_cover = 0  # Default to clear sky if API fails ########### mettere un NA e non mostrare il grafico

    # Adjust irradiance
    dni_adj, ghi_adj, dhi_adj = adjust_irradiance_for_clouds_and_shadow(
        times,
        selected_location,
        clearsky, cloud_cover, solar_pos['apparent_zenith'],
        shadow_profile
    )

    # shall we manage cases where no 8xx weather is available and calculation cannot be done?

    
    # Compute POA irradiance
    total_irradiance = irradiance.get_total_irradiance(
        surface_tilt = selected_panel['tilt'],
        surface_azimuth = selected_panel['azimuth'],
        dni=dni_adj,
        ghi=ghi_adj,
        dhi=dhi_adj,
        solar_zenith=solar_pos['apparent_zenith'],
        solar_azimuth=solar_pos['azimuth']
    )
    

    poa_irradiance = total_irradiance['poa_global']

    # Compute power output
    power_output = poa_irradiance * selected_panel['area'] * selected_panel['efficiency']  # Watts

    return power_output

def calculate_clearsky_power_output(times, selected_location, selected_panel, shadow_profile, weather_data):
    """
    Calculates solar panel power output considering clearsky (cloud cover = 0).
    
    - times: Pandas DatetimeIndex
    - selected_location: 
    - selected_panel: Dictionary with 'tilt', 'azimuth', 'area', 'efficiency'
    - shadow_profile
    - weather_data

    Returns: Power output series
    """

    #  ------ modifies the weater data using times series ans settin cloud cover to 0 ------

    clearsky_weather_data = weather_data.copy()
    clearsky_weather_data['times_cloud_cover'] = clearsky_weather_data['times_cloud_cover'].reindex(times)
    clearsky_weather_data['times_cloud_cover']['cloud_cover'] = 0
    
    
    # calculated the powe with adjusted weather data
    
    clearsky_power_output = calculate_power_output(times, selected_location, selected_panel, shadow_profile, clearsky_weather_data)
    
    return clearsky_power_output