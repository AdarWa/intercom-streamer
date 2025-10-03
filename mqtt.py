import logging
import threading
import paho.mqtt.client as mqtt

class MQTT:
    def __init__(self, address: str, port=1883, username=None, password=None, timeout=5):
        self.client = mqtt.Client()
        self.client.username_pw_set(username, password)
        self.client.on_message = self.on_msg
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.subscribers = {}
        self._connected = threading.Event()
        self._address = address
        self._port = port
        self._connect_timeout = timeout

        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.client.connect_async(address, port, keepalive=60)
        self.client.loop_start()

        if not self._connected.wait(timeout=self._connect_timeout):
            logging.warning("Timeout while connecting to MQTT at %s:%s", address, port)

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            logging.info("Connected to MQTT broker at %s:%s", self._address, self._port)
            self._connected.set()
        else:
            logging.warning("MQTT connection failed with code %s", reason_code)

    def _on_disconnect(self, client, userdata, reason_code, properties=None):
        if reason_code != 0:
            logging.warning("MQTT disconnected unexpectedly (code %s)", reason_code)
        self._connected.clear()

    def stop(self):
        try:
            self.client.disconnect()
        finally:
            self.client.loop_stop()

    def on_msg(self,client, userdata, msg):
        logging.debug(f"Got message on topic {msg.topic}, {msg.payload}")
        if msg.topic in self.subscribers.keys():
            callback, model_type = self.subscribers[msg.topic]
            logging.debug("Calling callback...")
            if model_type is None:
                callback(msg.payload)
            
    
    def subscribe(self,topic, callback):
        logging.debug(f"Client subscribed on topic {topic}")
        self.client.subscribe(topic)
        self.subscribers[topic] = (callback, None)
        
    def publish(self, topic: str, payload: str):
        if not self._connected.is_set():
            logging.warning("MQTT client not connected; dropping payload for topic %s", topic)
            return
        logging.debug(f"client published on topic {topic}")
        self.client.publish(topic, payload)
