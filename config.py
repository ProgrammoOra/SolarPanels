from streamlit import secrets

# OpenWeather API
OPENWEATHER_API_KEY = secrets['om_api_key']

# Shelly API
SHELLY_API_KEY = secrets['shelly_api_key']
SHELLY_DEVICE_ID = secrets['shelly_device_id']

# Timezone
ITALY_TIMEZONE = 'Europe/Rome' # 'Europe/Rome' gestisce il cambio fuso orario diversamente da 'CET'

# Location
STANDARD_LOCATION_LATITUDE = 45.5
STANDARD_LOCATION_LONGITUDE = 9.19
STANDARD_LOCATION_ALTITUDE = 144

# Shadow Profile
STANDARD_SHADOW_AZIMUTHS = "0, 151.9, 152, 209.9, 210, 287.9, 288, 360"
STANDARD_SHADOWS_ELEVATIONS = "80, 80, 10, 10, 14, 14, 10, 10"

# Panel configuration
STANDARD_PANEL_TILT = 5
STANDARD_PANEL_AZIMUTH = 152
STANDARD_PANEL_AREA = 6.25
STANDARD_PANEL_EFFICIENCY = 14.2

# Frequency for daily time serie
STANDARD_STEP = '1min'
