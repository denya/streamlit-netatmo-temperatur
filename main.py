import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import requests
import os

import logging

# Logging setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class StreamlitHandler(logging.Handler):
    def __init__(self):
        super(StreamlitHandler, self).__init__()

    def emit(self, record):
        new_log = self.format(record) + '\n'
        if 'log_data' not in st.session_state:
            st.session_state.log_data = ""
        st.session_state.log_data += new_log

# Add the Streamlit handler to the logger
streamlit_handler = StreamlitHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
streamlit_handler.setFormatter(formatter)
logger.addHandler(streamlit_handler)


# Constants
CLIENT_ID = st.secrets['client_id']
CLIENT_SECRET = st.secrets['client_secret']
REFRESH_TOKEN = st.secrets['refresh_token']

# Netatmo API URLs
TOKEN_URL = "https://api.netatmo.com/oauth2/token"
DATA_URL = "https://api.netatmo.com/api/getstationsdata"

def get_access_token():
    data = {
        'grant_type': 'refresh_token',
        'refresh_token': REFRESH_TOKEN,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET
    }
    response = requests.post(TOKEN_URL, data=data)
    return response.json()['access_token']


def fetch_data(access_token):
    logger.info("Fetching devices...")
    devices_params = {
        'access_token': access_token,
        'get_favorites': False
    }
    try:
        devices_response = requests.post(DEVICES_URL, params=devices_params)
        devices_response.raise_for_status()
        devices_data = devices_response.json()
    except requests.exceptions.HTTPError as err:
        logger.error(f'HTTP error occurred while fetching devices: {err}')
        return []
    except Exception as err:
        logger.error(f'Error occurred while fetching devices: {err}')
        return []

    all_measurements = []
    for device_data in devices_data.get('devices', []):
        device_id = device_data.get('_id')
        if not device_id:
            logger.warning(f"Skipping device due to missing '_id' key: {device_data}")
            continue

        logger.info(f"Fetching measurements for device: {device_data.get('station_name', 'Unknown')}")
        measurements_params = {
            'access_token': access_token,
            'device_id': device_id,
            'scale': '30min',
            'type': 'Temperature',
            'date_begin': int((datetime.now() - timedelta(days=7)).timestamp()),
            'date_end': int(datetime.now().timestamp()),
            'optimize': False,
            'real_time': False
        }
        try:
            measurements_response = requests.post(DATA_URL, params=measurements_params)
            measurements_response.raise_for_status()
            measurements_data = measurements_response.json()['body']
            all_measurements.extend(measurements_data)
        except requests.exceptions.HTTPError as err:
            logger.error(f'HTTP error occurred while fetching measurements for device {device["station_name"]}: {err}')
        except Exception as err:
            logger.error(f'Error occurred while fetching measurements for device {device["station_name"]}: {err}')

    logger.info("Temperature data fetched successfully.")
    return all_measurements


def prepare_data():
    access_token = get_access_token()
    response_data = fetch_data(access_token)
    devices = response_data['body']['devices']
    
    data_list = []
    device_data_counts = {}
    max_temps = {}
    for device in devices:
        device_name = device['station_name']
        device_type = device['type']
        modules = device.get('modules', [])
        device_data_counts[device_name] = 0
        max_temp = float('-inf')
        
        # Check for temperature in the main device
        if 'dashboard_data' in device and 'Temperature' in device['dashboard_data']:
            data_list.append({
                'Time': datetime.fromtimestamp(device['dashboard_data']['time_utc']),
                'Temperature': device['dashboard_data']['Temperature'],
                'Device': device_name,
                'Module': 'Main Unit'
            })
            device_data_counts[device_name] += 1
            max_temp = max(max_temp, device['dashboard_data']['Temperature'])

        # Check for temperature in additional modules
        for module in modules:
            module_name = module['module_name']
            if 'dashboard_data' in module and 'Temperature' in module['dashboard_data']:
                data_list.append({
                    'Time': datetime.fromtimestamp(module['dashboard_data']['time_utc']),
                    'Temperature': module['dashboard_data']['Temperature'],
                    'Device': device_name,
                    'Module': module_name
                })
                device_data_counts[device_name] += 1
                max_temp = max(max_temp, module['dashboard_data']['Temperature'])

        if max_temp != float('-inf'):
            max_temp_time = max([point['Time'] for point in data_list if point['Device'] == device_name])
            max_temps[device_name] = (max_temp, max_temp_time)

    for device, count in device_data_counts.items():
        logger.info(f"Number of data points for {device}: {count}")

    for device, (temp, time) in max_temps.items():
        logger.info(f"Maximum temperature for {device} on {time.date()}: {temp:.2f}°C")

    df = pd.DataFrame(data_list)
    if not df.empty:
        df.sort_values('Time', inplace=True)
    return df


def plot_temperatures(df):
    fig = px.line(df, x='Time', y='Temperature', color='Device', title='Temperature Over Time',
                  labels={'Temperature': 'Temperature (°C)', 'Device': 'Device Location'}, template='plotly_white')
    fig.update_xaxes(rangeslider_visible=True)
    st.plotly_chart(fig, use_container_width=True)

def main():
    st.title('Temperature Monitoring Across Devices')
    df = prepare_data()
    if not df.empty:
        plot_temperatures(df)
    else:
        st.write("No temperature data available.")

    # Display logs
    if 'log_data' in st.session_state:
        st.subheader('Logs')
        st.code(st.session_state.log_data)

if __name__ == '__main__':
    main()
