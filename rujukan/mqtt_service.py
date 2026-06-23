import paho.mqtt.client as mqtt
import os
import json
import logging
import threading
from datetime import datetime

logger = logging.getLogger(__name__)


class MQTTService:
    """Singleton MQTT client for ESP32 lamp control."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # MQTT broker configuration
        self.broker_host = os.getenv('MQTT_BROKER_HOST', 'localhost')
        self.broker_port = int(os.getenv('MQTT_BROKER_PORT', '1883'))
        self.broker_username = os.getenv('MQTT_BROKER_USERNAME', '')
        self.broker_password = os.getenv('MQTT_BROKER_PASSWORD', '')

        # State management
        self.client = mqtt.Client()
        self.connected = False
        self.lamp_states = {}  # {lamp_name: "on"|"off"|"unknown"}
        self.state_lock = threading.Lock()

        # Load lamp configuration
        self.lamp_config = None
        self._load_lamp_config()

        # Setup callbacks
        self._setup_callbacks()

        self._initialized = True
        logger.info(f"MQTTService initialized: {self.broker_host}:{self.broker_port}")

    def _load_lamp_config(self):
        """Load lamp configuration from lamp_config.json"""
        config_path = os.path.join(os.path.dirname(__file__), 'lamp_config.json')
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    self.lamp_config = json.load(f)
                logger.info(f"Loaded {len(self.lamp_config.get('lamps', []))} lamps from config")
            else:
                logger.warning(f"lamp_config.json not found at {config_path}")
        except Exception as e:
            logger.error(f"Failed to load lamp config: {e}")

    def _setup_callbacks(self):
        """Setup MQTT client callbacks"""
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        if self.broker_username:
            self.client.username_pw_set(self.broker_username, self.broker_password)

    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker"""
        if rc == 0:
            self.connected = True
            logger.info(f"Connected to MQTT broker at {self.broker_host}:{self.broker_port}")

            # Subscribe to all lamp status topics
            if self.lamp_config:
                for lamp in self.lamp_config.get('lamps', []):
                    if lamp.get('enabled', True):
                        status_topic = lamp['status_topic']
                        client.subscribe(status_topic)
                        logger.info(f"Subscribed to: {status_topic}")
        else:
            logger.error(f"Failed to connect to MQTT broker, return code {rc}")

    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT broker"""
        self.connected = False
        if rc != 0:
            logger.warning(f"Unexpected disconnection from MQTT broker (rc={rc})")
        else:
            logger.info("Disconnected from MQTT broker")

    def _on_message(self, client, userdata, msg):
        """Callback when message received from MQTT broker"""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            logger.debug(f"MQTT message received: {topic} = {payload}")

            # Update lamp state if this is a status message
            if self.lamp_config:
                for lamp in self.lamp_config.get('lamps', []):
                    if lamp['status_topic'] == topic:
                        lamp_name = lamp['name']
                        with self.state_lock:
                            self.lamp_states[lamp_name] = payload
                        logger.info(f"Lamp state updated: {lamp_name} = {payload}")
                        break
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")

    def connect(self):
        """Connect to MQTT broker"""
        try:
            logger.info(f"Connecting to MQTT broker at {self.broker_host}:{self.broker_port}...")
            self.client.connect(self.broker_host, self.broker_port, keepalive=60)
            self.client.loop_start()
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")

    def disconnect(self):
        """Disconnect from MQTT broker"""
        try:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("Disconnected from MQTT broker")
        except Exception as e:
            logger.error(f"Failed to disconnect from MQTT broker: {e}")

    def publish(self, topic, message):
        """Publish message to MQTT topic"""
        if not self.connected:
            logger.warning(f"Cannot publish to {topic}: not connected to MQTT broker")
            return False

        try:
            result = self.client.publish(topic, message)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"Published to {topic}: {message}")
                return True
            else:
                logger.error(f"Failed to publish to {topic}, return code {result.rc}")
                return False
        except Exception as e:
            logger.error(f"Error publishing to {topic}: {e}")
            return False

    def get_lamp_state(self, lamp_name):
        """Get cached state of a lamp"""
        with self.state_lock:
            return self.lamp_states.get(lamp_name, 'unknown')

    def get_all_states(self):
        """Get cached states of all lamps"""
        with self.state_lock:
            return self.lamp_states.copy()
