from config import SHELLY_API_KEY, SHELLY_DEVICE_ID
import requests

#### --- Retrive shelly device actual power for PV panels and network---

def get_actual_home_power():
    
    # Replace with your actual auth_key and device_id
    auth_key = SHELLY_API_KEY
    device_id = SHELLY_DEVICE_ID

    # Construct the API URL
    api_url = f'https://shelly-50-eu.shelly.cloud/device/status?auth_key={auth_key}&id={device_id}'

    # Make the GET request
    response = requests.get(api_url)

    # Check if the request was successful
    if response.status_code == 200:
        data = response.json()
        # Navigate through the JSON response to find the power output
        # The exact path may vary depending on your device model
        power_output_f = -data.get('data', {}).get('device_status', {}).get('emeters', [{}])[0].get('power', 'N/A') # changed sign to +
        power_output_r = -data.get('data', {}).get('device_status', {}).get('emeters', [{}])[1].get('power', 'N/A') # changed sign to +
        # print(f'Current Power Output Fotovoltaico: {power_output_f} W')
        # print(f'Current Power Output Rete: {power_output_r} W')

        return power_output_f, power_output_r
        
    else:
        # print(f'Failed to retrieve data: {response.status_code}')
        return False, response.status_code  ## if data is not retrived, power_output_f = False