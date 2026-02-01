import os
from dotenv import load_dotenv

load_dotenv()

# IBM Cloud
IBM_CLOUD_API_KEY = os.getenv("IBM_CLOUD_API_KEY")
IBM_WATSONX_URL = os.getenv("IBM_WATSONX_URL")
IBM_WATSONX_PROJECT_ID = os.getenv("IBM_WATSONX_PROJECT_ID")

# Weather
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

# Price
ENTSOE_API_TOKEN = os.getenv("ENTSOE_API_TOKEN")
