
import os
import sys

# Mimic worker.py behavior (no load_dotenv originally)
print(f"Current CWD: {os.getcwd()}")
print("Checking env vars BEFORE load_dotenv:")
print(f"TEST_VAR: {os.getenv('TEST_VAR')}")

# Now attempt to load
from dotenv import load_dotenv
load_dotenv()

print("\nChecking env vars AFTER load_dotenv:")
print(f"TEST_VAR: {os.getenv('TEST_VAR')}")
