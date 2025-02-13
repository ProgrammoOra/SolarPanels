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



#### ---- Render output data ---------------------------------------------------


def render_ui_modern_with_tabs(selected_datetime, 
                               weather_data, 
                               sun_position, 
                               selected_datetime_shadowed, 
                               clearsky_power_energy_data, 
                               weather_power_energy_data,
                               times_clearsky_energy, 
                               times_weather_energy,
                               home_pv_power, 
                               network_pv_power,
                               forecast_data,      # DataFrame contenente le previsioni per i prossimi 4 giorni
                               monthly_data):      # DataFrame contenente i dati aggregati dei 12 mesi

    # --- Sidebar e Header ---
    st.sidebar.title("Navigazione")
    st.sidebar.write("Seleziona la data per visualizzare i dettagli:")
    # (Eventuali widget per la selezione della data possono essere inseriti qui) ########spostare negli input ########
    
    st.title("☀️ Solar & Weather Dashboard")
    # st.subheader(f"Dati per: {selected_datetime.strftime('%Y-%m-%d %H:%M')}") #########
    
    # --- Creazione dei 4 Tabs ---
    tabs = st.tabs(["Dati Istantanei", "Dati Giornalieri", "Previsioni a 4 Giorni", "Dati 12 Mesi"])
    
    # ==========================
    # Tab 1: Dati Istantanei
    # ==========================
    with tabs[0]:
        st.markdown("## Dati Istantanei")

        # --- Data e Ora selezionati
        col1, col2 = st.columns(2)
        with col1:
            st.metric(label="Data", value=f"{selected_datetime.strftime('%Y-%m-%d')}")
        with col2:
            st.metric(label="Ora", value=f"{selected_datetime.strftime('%H:%M')}")
        
        # --- Posizione del Sole ---
        st.markdown("### Posizione del Sole")
        col1, col2 = st.columns(2)
        with col1:
            st.metric(label="Azimut", value=f"{sun_position['azimuth']}°")
        with col2:
            st.metric(label="Elevazione", value=f"{sun_position['elevation']}°")
        
        # --- Condizioni Meteo ---
        st.markdown("### Condizioni Meteo")
        if weather_data['times_cloud_cover'].empty:
            if selected_datetime < weather_data['actual_weather'][0]['datetime']:
                st.error("❌ Nessun dato storico disponibile per il meteo")
            else:
                max_forecast_datetime = weather_data['actual_weather'][0]['datetime'] + datetime.timedelta(days=5)
                st.error(f"❌ Dati di forecast disponibili solo fino al {max_forecast_datetime.date()} alle {max_forecast_datetime.time()}")
        else:
            if selected_datetime < weather_data['times_cloud_cover'].iloc[0].name:
                st.error("❌ Nessun dato storico disponibile per il meteo")
            elif selected_datetime > weather_data['times_cloud_cover'].iloc[-1].name:
                max_forecast_datetime = weather_data['actual_weather'][0]['datetime'] + datetime.timedelta(days=5)
                st.error(f"❌ Dati di forecast disponibili solo fino al {max_forecast_datetime.date()} alle {max_forecast_datetime.time()}")
            else:
                selected_time_weather = weather_data['times_cloud_cover'].loc[selected_datetime]
                icon_url = f"https://openweathermap.org/img/wn/{selected_time_weather['weather_icon']}@2x.png"
                col_icon, col_desc = st.columns([1, 3])
                with col_icon:
                    st.image(icon_url, width=60)
                with col_desc:
                    st.metric(label="Condizione", value=selected_time_weather['weather_description'])
                    if int(selected_time_weather['weather_code'] / 100) == 8:
                        st.info(f"☁️ Copertura Nuvolosa: {int(selected_time_weather['cloud_cover'])}%")
        
        # --- Output Fotovoltaico ---
        st.markdown("### Output Fotovoltaico")
        col_shadow, col_power = st.columns(2)
        with col_shadow:
            shadow_text = "✅ No" if not selected_datetime_shadowed else "❌ Yes"
            st.metric(label="Ombreggiato?", value=shadow_text)
        with col_power:
            selected_time_clearsky_power = int(round(clearsky_power_energy_data.loc[selected_datetime], 0))
            if pd.isna(weather_power_energy_data.loc[selected_datetime]):
                selected_time_weather_power = "Dati meteo non disponibili"
            else:
                selected_time_weather_power = f"{int(round(weather_power_energy_data.loc[selected_datetime], 0))} W"
            st.metric(label="ClearSky PV Output", value=f"{selected_time_clearsky_power} W")
            st.metric(label="Actual PV Output", value=selected_time_weather_power)
        
        # --- Dati di Consumo / Rete ---
        st.markdown("### Dati di Consumo / Rete")
        if not home_pv_power:
            st.warning("💡 Nessun dato sull’uso domestico disponibile")
        else:
            col_home, col_detail = st.columns(2)
            home_usage = int(home_pv_power if (network_pv_power < 0) else (home_pv_power + network_pv_power))
            with col_home:
                st.metric(label="Uso Domestico", value=f"{home_usage} W")
            with col_detail:
                st.metric(label="PV Output", value=f"{int(home_pv_power)} W")
                st.metric(label="Network Output", value=f"{int(network_pv_power)} W")
    
    # ==========================
    # Tab 2: Dati Giornalieri
    # ==========================
    with tabs[1]:
        st.markdown("## Dati Giornalieri")
        
        # --- Riepilogo Energetico ---
        st.markdown(f"### Riepilogo Energetico per il {selected_datetime.date()}")
        st.write(f"**ClearSky Energy Totale:** {times_clearsky_energy} kWh")
        if weather_data['times_cloud_cover'].empty:
            st.write("**Energy Totale (Meteo Forecast):** Dati non disponibili")
        else:
            st.write(f"**Energy Totale (Meteo Forecast):** {times_weather_energy} kWh")
        
        # --- Grafico della Produzione durante il Giorno ---
        st.markdown("### Andamento dell’Output di Potenza Durante la Giornata")
        date_power_output = pd.concat([clearsky_power_energy_data, weather_power_energy_data], axis=1)
        date_power_output.columns = ['ClearSky Power', 'Weather Power']
        fig = px.line(
            date_power_output,
            x=date_power_output.index,
            y=['ClearSky Power', 'Weather Power'],
            labels={'x': 'Orario', 'value': 'Potenza (W)'},
            color_discrete_map={'ClearSky Power': 'green', 'Weather Power': 'blue'}
        )
        fig.update_traces(line=dict(width=3))
        fig.update_layout(
            legend=dict(orientation="h", y=-0.2),
            margin=dict(l=20, r=20, t=30, b=30)
        )
        fig.update_xaxes(
            range=[
                pd.Timestamp(f"{selected_datetime.date()} 06:00"),
                pd.Timestamp(f"{selected_datetime.date()} 22:00")
            ],
            tickformat='%H:%M'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # ==========================
    # Tab 3: Previsioni a 4 Giorni
    # ==========================
    with tabs[2]:
        st.markdown("## Previsioni a 4 Giorni")
        # Visualizzazione tabellare delle previsioni (si assume che forecast_data sia un DataFrame)
        st.dataframe(forecast_data)
        
        if (not forecast_data.empty) and {"datetime", "clearsky_production", "weather_production"}.issubset(forecast_data.columns):
            fig_forecast = px.line(
                forecast_data,
                x="datetime",
                y=["clearsky_production", "weather_production"],
                labels={"datetime": "Data e Ora", "value": "Produzione (W)"},
                title="Produzione Fotovoltaico - Previsioni"
            )
            fig_forecast.update_traces(line=dict(width=3))
            st.plotly_chart(fig_forecast, use_container_width=True)
        else:
            st.info("Dati di previsione non sufficienti per la visualizzazione grafica.")
    
    # ==========================
    # Tab 4: Dati 12 Mesi
    # ==========================
    with tabs[3]:
        st.markdown("## Dati 12 Mesi")
        st.dataframe(monthly_data)
        
        required_columns = {"Mese", "Ore di Sole", "Produzione Clearsky", "Produzione Storica"}
        if (not monthly_data.empty) and required_columns.issubset(monthly_data.columns):
            fig_monthly = px.bar(
                monthly_data,
                x="Mese",
                y=["Ore di Sole", "Produzione Clearsky", "Produzione Storica"],
                barmode="group",
                title="Statistiche Mensili"
            )
            st.plotly_chart(fig_monthly, use_container_width=True)
        else:
            st.info("Dati mensili non sufficienti per la visualizzazione grafica.")




#### Main function to test module  ############

def main():
    
    # --- Streamlit UI Input ---

    selected_datetime = get_selected_datetime()
    selected_date = selected_datetime.date()
    
    selected_location = get_selected_location()

    shadow_profile = get_shadow_profile()

    selected_panel = get_solar_panel()

    ##############
    # in the main module calculatins are performed to create the output with thw following rendering UI #
    ##############

    render_ui_modern_with_tabs(selected_datetime, 
                     weather_data, 
                     sun_position, 
                     selected_datetime_shadowed, 
                     clearsky_power_data, weather_power_data,
                     times_clearsky_energy, 
                     times_weather_energy,
                     home_pv_power, 
                     network_pv_power,
                     pd.DataFrame(), pd.DataFrame())   # still missing the las two data
    

if __name__ == "__main__":
    main()
    