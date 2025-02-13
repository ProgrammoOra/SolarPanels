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
tz = timezone(ITALY_TIMEZONE)  
current_datetime = datetime.datetime.now(tz)


#### ---- Get Date and Time (spostati nella Sidebar) ----------------------------------------------------

def get_selected_datetime():
    # Inizializzazione della sessione
    if "selected_datetime" not in st.session_state:
        st.session_state.selected_datetime = datetime.datetime.now(tz).replace(second=0, microsecond=0) # Initialize to now

    # Inserimento di Data e Ora nella sidebar (in cima)
    
    st.sidebar.header("⏰ Data e Ora")
    
    selected_date = st.sidebar.date_input("📅 Data:", value=st.session_state.selected_datetime.date())
    selected_time = st.sidebar.time_input("⏰ Orario:", value=st.session_state.selected_datetime.time())

    new_datetime = tz.localize(datetime.datetime.combine(selected_date, selected_time))

    if new_datetime != st.session_state.selected_datetime:
        st.session_state.selected_datetime = new_datetime.replace(second=0, microsecond=0)
        st.rerun()  # Aggiornamento immediato della UI

    return st.session_state.selected_datetime



#### ---- Get Location ----------------------------------------------------
def get_selected_location(std_latitude=STANDARD_LOCATION_LATITUDE, 
                          std_longitude=STANDARD_LOCATION_LONGITUDE, 
                          std_altitude=STANDARD_LOCATION_ALTITUDE):
    st.sidebar.header("🌍 Posizione")

    col1s, col2s = st.sidebar.columns([1, 1]) #create 2 columns for better layout
    
    latitude = col1s.number_input("Latitudine", value=std_latitude)
    longitude = col2s.number_input("Longitudine", value=std_longitude)
    altitude = st.sidebar.number_input("Altitudine (m)", value=std_altitude)
    location = Location(latitude, longitude, altitude=altitude, tz=tz, name='LocationPerCalcolo')
    return location

#### ---- Get Shadow Profile ----------------------------------------------------
def get_shadow_profile(std_shadow_azimuths=STANDARD_SHADOW_AZIMUTHS,
                       std_shadow_elevations=STANDARD_SHADOWS_ELEVATIONS):
    st.sidebar.header("🌑 Profilo Ombra")
    shadow_azimuths = st.sidebar.text_area(
        "Inserisci valori di azimut (separati da virgola):", std_shadow_azimuths
    )
    shadow_elevations = st.sidebar.text_area(
        "Inserisci valori di elevazione (separati da virgola):", std_shadow_elevations
    )

    try:
        shadow_azimuths = list(map(float, shadow_azimuths.split(",")))
        shadow_elevations = list(map(float, shadow_elevations.split(",")))
        shadow_profile = pd.DataFrame({"Azimuth": shadow_azimuths, "Elevation": shadow_elevations}).sort_values(by="Azimuth")
    except ValueError:
        st.error("Errore: inserire valori numerici validi per il profilo ombra.")
        st.stop()

    st.sidebar.line_chart(shadow_profile.set_index("Azimuth")[["Elevation"]])
    return shadow_profile

#### ---- Get Solar Panel Data ----------------------------------------------------
def get_solar_panel(std_panel_tilt=STANDARD_PANEL_TILT,
                    std_panel_azimuth=STANDARD_PANEL_AZIMUTH,
                    std_panel_area=STANDARD_PANEL_AREA,
                    std_panel_efficiency=STANDARD_PANEL_EFFICIENCY):
    st.sidebar.header("🔋 Configurazione PV")
    panel = {
        'tilt': st.sidebar.slider("Inclinazione del pannello (°)", 0, 90, 5),
        'azimuth': st.sidebar.slider("Azimut del pannello (°)", 0, 360, 152),
        'area': st.sidebar.number_input("Area del pannello (m²)", value=6.25),
        'efficiency': st.sidebar.slider("Efficienza del pannello (%)", 0.0, 100.0, 14.2) / 100.0
    }
    return panel

#### ---- Render Output Data con 4 Tabs ----------------------------------------------------
def render_ui_modern_with_tabs(selected_datetime, 
                               weather_data, 
                               sun_position, 
                               selected_datetime_shadowed, 
                               clearsky_power_energy_data, 
                               weather_power_energy_data,
                               times_clearsky_energy, 
                               times_weather_energy,
                               home_pv_power, 
                               network_power,
                               forecast_data,      # DataFrame con previsioni per i prossimi 4 giorni
                               monthly_data):      # DataFrame con dati aggregati dei 12 mesi

    # Titolo principale della dashboard
    st.title("☀️ Solar & Weather Dashboard")
    #st.subheader(f"Dati per: {selected_datetime.strftime('%Y-%m-%d %H:%M')}")

    # Creazione dei 4 Tabs
    tabs = st.tabs(["Dati Istantanei", "Dati Giornalieri", "Previsioni a 4 Giorni", "Dati 12 Mesi"])

    # ==========================
    # Tab 1: Dati Istantanei
    # ==========================
    with tabs[0]:
        col1, col2, col3 = st.columns(3)
        col1.markdown("## Dati Istantanei")
        # Visualizzazione della data e ora selezionate
        with col2:
            st.metric(label="Data", value=selected_datetime.strftime('%Y-%m-%d'))
        with col3:
            st.metric(label="Ora", value=selected_datetime.strftime('%H:%M'))
        
        # Posizione del Sole
        col1, col2, col3 = st.columns(3)
        col1.markdown("### Posizione del Sole")
        #col1, col2 = st.columns(2)
        with col2:
            st.metric(label="Azimut", value=f"{sun_position['azimuth']}°")
        with col3:
            st.metric(label="Elevazione", value=f"{sun_position['elevation']}°")
        
        # Condizioni Meteo
        col1, col2, col3 = st.columns(3)
        col1.markdown("### Condizioni Meteo")
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
                #col_icon, col_desc = st.columns([1, 3])
                with col2:
                    st.image(icon_url, width=60)
                with col3:
                    st.metric(label="Condizione", value=selected_time_weather['weather_description'])
                    if int(selected_time_weather['weather_code'] / 100) == 8:
                        st.info(f"☁️ Copertura Nuvolosa: {int(selected_time_weather['cloud_cover'])}%")

        st.divider()
        
        # Output Fotovoltaico
        st.markdown("### Stime Generazione Fotovoltaico")
        col1, col2, col3 = st.columns(3)
        with col1:
            shadow_text = "✅ No" if not selected_datetime_shadowed else "❌ Yes"
            st.metric(label="Ombreggiato?", value=shadow_text)
       
        selected_time_clearsky_power = int(round(clearsky_power_energy_data.loc[selected_datetime], 0))
        if pd.isna(weather_power_energy_data.loc[selected_datetime]):
            selected_time_weather_power = "Dati meteo non disponibili"
        else:
            selected_time_weather_power = f"{int(round(weather_power_energy_data.loc[selected_datetime], 0))} W"
        col2.metric(label="ClearSky PV Output", value=f"{selected_time_clearsky_power} W")
        col3.metric(label="ActualSky PV Output", value=selected_time_weather_power)
        
        # Dati di Consumo / Rete
        if  (st.session_state.selected_datetime == datetime.datetime.now(tz).replace(second=0, microsecond=0)):
            st.markdown("### Dati di Consumo")
            if not home_pv_power:
                st.warning("💡 Nessun dato sull’uso domestico disponibile")
            else:
                col1, col2, col3 = st.columns(3)
                home_usage = int(network_power if (home_pv_power < 0) else (home_pv_power + network_power))
                col1.metric(label="Totale", value=f"{home_usage} W")
                col2.metric(label="Network Input", value=f"{int(network_power)} W")
                col3.metric(label="PV Input", value=f"{int(home_pv_power)} W")
    
    # ==========================
    # Tab 2: Dati Giornalieri
    # ==========================
    with tabs[1]:
        st.markdown("## Dati Giornalieri")
        # Riepilogo Energetico
        st.markdown(f"### Riepilogo Energetico per il {selected_datetime.date()}")
        
        col_clearsky, col_weather = st.columns(2)

        with col_clearsky:
            st.metric(label=":green[Massima produzione (ClearSky)]", value=f"{times_clearsky_energy} kWh")


        if weather_data['times_cloud_cover'].empty:
            st.write("**Produzione attesa (Cloudy):** Dati non disponibili")
        else:
            with col_weather:
                st.metric(label=":blue[Produzione attesa (Cloudy)]", value=f"{times_weather_energy} kWh")

        
        # Grafico della Produzione durante il Giorno
        st.markdown("### Andamento dell’Output di Potenza Durante la Giornata")
        date_power_output = pd.concat([clearsky_power_energy_data, weather_power_energy_data], axis=1)
        date_power_output.columns = ['ClearSky Power', 'Weather Power']
        fig = px.line(
            date_power_output,
            x=date_power_output.index,
            y=['ClearSky Power', 'Weather Power'],
            labels={'x': 'Orario', 'value': 'Potenza (W)'},
            color_discrete_map={'ClearSky Power': 'green', 'Weather Power': 'skyblue'}
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

#### ---- Main Function ----------------------------------------------------
def main():
    # --- Sidebar: Input Generali ---
    selected_datetime = get_selected_datetime()  # Ora in cima alla sidebar
    selected_location = get_selected_location()
    shadow_profile = get_shadow_profile()
    selected_panel = get_solar_panel()

    # --- Calcoli ed Elaborazioni (omessi qui) ---
    # Ad esempio, i dati di weather_data, sun_position, etc. devono essere calcolati o caricati
    # Per questa demo, verranno passati dei DataFrame vuoti o dati fittizi per le ultime due sezioni
    # Le variabili seguenti devono essere definite nel modulo di calcolo:
    weather_data = {
        'times_cloud_cover': pd.DataFrame(), 
        'actual_weather': [ {'datetime': current_datetime} ]
    }
    sun_position = {'azimuth': 180, 'elevation': 45}
    selected_datetime_shadowed = False
    clearsky_power_data = pd.Series([1000], index=[selected_datetime])
    weather_power_data = pd.Series([900], index=[selected_datetime])
    times_clearsky_energy = 5.0
    times_weather_energy = 4.5
    home_pv_power = 300
    network_power = 50
    forecast_data = pd.DataFrame()   # DataFrame con dati di previsione a 4 giorni
    monthly_data = pd.DataFrame()    # DataFrame con dati aggregati dei 12 mesi

    render_ui_modern_with_tabs(
        selected_datetime, 
        weather_data, 
        sun_position, 
        selected_datetime_shadowed, 
        clearsky_power_data, weather_power_data,
        times_clearsky_energy, 
        times_weather_energy,
        home_pv_power, 
        network_pv_power,
        forecast_data, 
        monthly_data
    )

if __name__ == "__main__":
    main()
