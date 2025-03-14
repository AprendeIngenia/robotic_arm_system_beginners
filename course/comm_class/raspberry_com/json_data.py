import json
import time
import serial
import logging as log
from threading import Thread, Event

log.basicConfig(level=log.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class SerialCommunication:
    def __init__(self):
        self.message_end = b'\n'

        self.com = None
        self.is_connected = False
        self._read_thread = None

        self.buffer = bytearray()
        self._stop_event = Event()

    def connect(self) -> bool:
        """serial connection"""
        if self.is_connected:
            return True

        try:
            self.com = serial.Serial("COM7", 115200, write_timeout=10)
            self.is_connected = True

            # read loop
            self._stop_event.clear()
            self._read_thread = Thread(target=self._read_loop)
            self._read_thread.daemon = True
            self._read_thread.start()
            return True

        except Exception as e:
            log.error(f'Error connecting to serial port: {str(e)}')
            return False

    def writing_data(self, message_type: str, data: dict):
        message = {
            'type': message_type,
            'data': data,
        }
        encoded_message = json.dumps(message).encode() + self.message_end
        log.info(f'send message: {encoded_message}')
        self.com.write(encoded_message)

    def _read_loop(self):
        """Thread loop for read messages from VEX"""
        while not self._stop_event.is_set():
            if self.com and self.com.in_waiting:
                try:
                    char = self.com.read()
                    if char == self.message_end:
                        message = self.buffer.decode()
                        self.buffer = bytearray()
                        try:
                            data = json.loads(message)
                            self._process_message(data)
                        except json.JSONDecodeError:
                            log.error(f'error message decode: {message}')
                    else:
                        self.buffer.extend(char)
                except Exception as e:
                    log.error(f'error read serial port: {e}')
            time.sleep(0.01)

    def _process_message(self, message: dict):
        """process message from VEX"""
        try:
            msg_type = message.get('type', '').lower()
            data = message.get('data', {})

            if msg_type == 'test_service':
                state = data.get('state')
                log.info(f'{msg_type} status:\nstate: {state}')

        except Exception as e:
            log.error(f'error process message: {e}')

    def close(self):
        """"close serial connection"""
        self._stop_event.set()
        if self._read_thread:
            self._read_thread.join(timeout=1.0)
        if self.com and self.com.is_open:
            self.com.close()
            self.is_connected = False
            log.info('Serial connection closed')


if __name__ == "__main__":
    serial_manager = SerialCommunication()
    try:
        if serial_manager.connect():
            log.info("Connected to VEX Brain")

            # write
            message_type = 'test_service'
            data = {'state': 'successfully'}
            serial_manager.writing_data(message_type, data)

            # read
            while True:
                time.sleep(1)

    except KeyboardInterrupt:
        log.info("End program")
    finally:
        serial_manager.close()




