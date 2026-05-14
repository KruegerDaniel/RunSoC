import os

from dotenv import load_dotenv

load_dotenv()

class Config:
    PULP_TIMELIMIT_SECONDS = os.getenv("PULP_TIMELIMIT_SECONDS")
