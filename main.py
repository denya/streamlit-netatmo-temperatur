import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import requests
import os

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
    params = {
        'access_token': access_token,
        'get_favorites': False
    }
    response = requests.get(DATA_URL, params=params)
    return response.json()

def prepare_data():
    access_token = get_access_token()
    response_data = fetch_data(access_token)
    devices = response_data['body']['devices']
    
    data_list = []
    for device in devices:
        device_name = device['station_name']
        device_type = device['type']
        modules = device.get('modules', [])

        # Check for temperature in the main device
        if 'Temperature' in device['dashboard_data']:
            data_list.append({
                'Time': datetime.fromtimestamp(device['dashboard_data']['time_utc']),
                'Temperature': device['dashboard_data']['Temperature'],
                'Device': device_name + ' (Main Unit)'
            })

        # Check for temperature in additional modules
        for module in modules:
            if 'Temperature' in module['dashboard_data']:
                data_list.append({
                    'Time': datetime.fromtimestamp(module['dashboard_data']['time_utc']),
                    'Temperature': module['dashboard_data']['Temperature'],
                    'Device': device_name + ' (' + module['module_name'] + ')'
                })

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

if __name__ == '__main__':
    main()
