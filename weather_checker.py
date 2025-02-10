import datetime
from pytz import timezone
import pandas as pd
#import numpy as np

import requests

from config import OPENWEATHER_API_KEY
from config import ITALY_TIMEZONE, STANDARD_LOCATION_LATITUDE, STANDARD_LOCATION_LONGITUDE, STANDARD_LOCATION_ALTITUDE

def get_weather_data(times,
                     lat = STANDARD_LOCATION_LATITUDE, lon = STANDARD_LOCATION_LONGITUDE,
                     openweather_api_key = OPENWEATHER_API_KEY,
                     freq="1min",                  # Added interpolation parameter
                     std_timezone = ITALY_TIMEZONE): 
    """
    Fetches cloud cover for today with specified frequency:
    - 100% cloudiness for all times before now
    - Forecast data from OpenWeather until end of day (handling 3-hour intervals)
    times = series of one day times
    """

    # Verify if the time zone input is not in the timezone format
    if type(std_timezone) == str:
        std_timezone = timezone(std_timezone)
        
    now = datetime.datetime.now(std_timezone)
    
    if times.empty:
        return False

    # limit times to the cloud available data: now + 5 days
    weather_data_times = times[(times >= now.replace(second=0, microsecond=0)) & (times<= now + datetime.timedelta(days=5)) ]
    
    #   full_day_times = times        
    full_day_df = pd.DataFrame(index=weather_data_times)

    # Get Actual Weather
    openweather_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={openweather_api_key}&units=metric"
    response = requests.get(openweather_url).json()

    actual_data = []
    actual_time = now.replace(second=0, microsecond=0)
    actual_data.append({'datetime': actual_time,
                        'cloud_cover': response['clouds']['all'],
                        'weather_code' : response['weather'][0]['id'],
                        'weather_description': response['weather'][0]['description'],
                        'weather_icon' : response['weather'][0]['icon']
                       })

    actual_df = pd.DataFrame(actual_data)
    actual_df.set_index('datetime', inplace=True)
    full_day_df = full_day_df.combine_first(actual_df)
    
    # --------  Get forecast
    
    openweather_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={openweather_api_key}&units=metric"
    response = requests.get(openweather_url).json()

    forecast_data = []
    for entry in response['list']:
        forecast_time = datetime.datetime.utcfromtimestamp(entry['dt']).replace(tzinfo=datetime.timezone.utc)
        forecast_time = forecast_time.astimezone(std_timezone)
        forecast_data.append({'datetime': forecast_time, 
                              'cloud_cover': entry['clouds']['all'],
                              'weather_code' : entry['weather'][0]['id'],
                              'weather_description': entry['weather'][0]['description'], 
                              'weather_icon' : entry['weather'][0]['icon']
                             })

    forecast_df = pd.DataFrame(forecast_data)
    forecast_df.set_index('datetime', inplace=True)
    
    full_day_df = full_day_df.combine_first(forecast_df)
    
    full_day_df['cloud_cover'] = full_day_df['cloud_cover'].interpolate(method='linear', limit_direction='both')
    full_day_df['weather_code'] = full_day_df['weather_code'].ffill()  # Forward fill strings
    full_day_df['weather_description'] = full_day_df['weather_description'].ffill()  # Forward fill strings
    full_day_df['weather_icon'] = full_day_df['weather_icon'].ffill()  # Forward fill strings
    
    full_day_df = full_day_df.reindex(weather_data_times)

    return {
        'times_cloud_cover': full_day_df,
        'actual_weather': actual_data
    }



#### Main function to test module  ############

def main():
    #sss
    print('here we are')

if __name__ == "__main__":
    main()