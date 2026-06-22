import asyncio
import json
import logging
from typing import Optional, Callable
import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class MQTTService:
    def __init__(
        self,
        broker_host: str,
        broker_port: int,
        username: str = "",
        password: str = "",
        keepalive: int = 60,
    ):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.keepalive = keepalive

        self.client = mqtt.Client()
        self._connected = False

        # Message queue for async processing
        self.message_queue = asyncio.Queue()

        # Save event loop reference for thread-safe callbacks
        self._loop = asyncio.get_event_loop()

        # Callback for status messages
        self.on_status_message: Optional[Callable] = None
        self.on_lwt_message: Optional[Callable] = None

        # Setup credentials if provided
        if username:
            self.client.username_pw_set(username, password)

        # Setup callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc):
        """Callback for when the client connects to the broker"""
        if rc == 0:
            logger.info("Connected to MQTT broker")
            self._connected = True
        else:
            logger.error(f"Failed to connect to MQTT broker, return code {rc}")
            self._connected = False

    def _on_disconnect(self, client, userdata, rc):
        """Callback for when the client disconnects from the broker"""
        logger.warning(f"Disconnected from MQTT broker, return code {rc}")
        self._connected = False

    def _on_message(self, client, userdata, msg):
        """Callback for when a message is received"""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())

            logger.debug(f"Received MQTT message: {topic} - {payload}")

            # Queue message for async processing
            asyncio.run_coroutine_threadsafe(
                self.message_queue.put((topic, payload)),
                self._loop
            )

            # Route to appropriate handler
            if "/status" in topic:
                if self.on_status_message:
                    asyncio.run_coroutine_threadsafe(
                        self.on_status_message(topic, payload),
                        self._loop
                    )
            elif "/lwt" in topic:
                if self.on_lwt_message:
                    asyncio.run_coroutine_threadsafe(
                        self.on_lwt_message(topic, payload),
                        self._loop
                    )

        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")

    async def connect(self):
        """Connect to MQTT broker"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self.client.connect(self.broker_host, self.broker_port, self.keepalive)
        )
        # Start the loop in a separate thread
        self.client.loop_start()
        logger.info(f"Connecting to MQTT broker at {self.broker_host}:{self.broker_port}")

    async def disconnect(self):
        """Disconnect from MQTT broker"""
        self.client.loop_stop()
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.client.disconnect)
        logger.info("Disconnected from MQTT broker")

    async def publish_command(
        self,
        device_id: str,
        relay: str,
        action: str,
    ):
        """Publish a command to a device"""
        if not self._connected:
            logger.warning("Not connected to MQTT broker, cannot publish command")
            return

        topic = f"elbot/{device_id}/cmd"
        payload = {
            "relay": relay,
            "state": action.upper(),
        }

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self.client.publish(topic, json.dumps(payload), qos=1)
        )

        logger.info(f"Published command to {topic}: {payload}")

    async def publish_raw(self, topic: str, payload: str, qos: int = 1):
        """Publish raw payload to a topic (for OTA and other custom messages)"""
        if not self._connected:
            logger.warning("Not connected to MQTT broker, cannot publish raw message")
            return

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self.client.publish(topic, payload, qos=qos)
        )

        logger.info(f"Published raw to {topic}: {payload[:100]}...")

    async def subscribe_status(self):
        """Subscribe to status updates from all devices"""
        if not self._connected:
            logger.warning("Not connected to MQTT broker, cannot subscribe")
            return

        topic = "elbot/+/status"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self.client.subscribe(topic))
        logger.info(f"Subscribed to {topic}")

    async def subscribe_lwt(self):
        """Subscribe to LWT (online/offline) messages from all devices"""
        if not self._connected:
            logger.warning("Not connected to MQTT broker, cannot subscribe")
            return

        topic = "elbot/+/lwt"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self.client.subscribe(topic))
        logger.info(f"Subscribed to {topic}")

    def is_connected(self) -> bool:
        """Check if connected to broker"""
        return self._connected
