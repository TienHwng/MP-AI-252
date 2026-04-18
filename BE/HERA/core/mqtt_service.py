"""
MQTT Service
=============
Re-export MQTTManager from MQTT_Broker as MQTTService for backward compatibility.
"""

import os
import sys

# Add parent directory to path so we can import from MQTT_Broker
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from MQTT_Broker.mqtt_manager import MQTTManager

# Alias for backward compatibility with existing code
MQTTService = MQTTManager
