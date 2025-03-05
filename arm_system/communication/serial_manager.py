import os
import sys
import json
import time
import serial
import logging as log
from typing import Dict, Any, Optional
from threading import Thread, Event

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from perception.vision.camera.main import CameraManager
from perception.vision.image_processing import ImageProcessor

log.basicConfig(level=log.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class CommunicationManager:
    def __init__(self, port: str='/dev/ttyACM1', baudrate: int = 115200, camera_index: int = 0):
        """
        :param port: serial port
        :param baudrate: baudrate
        :param camera_index: camera index
        """
        self.port = port
        self.baudrate = baudrate
        self.message_end = b'\n'
        
        self.serial_port: Optional[serial.Serial] = None
        self.is_connected = False
        
        # threads / events
        self._read_thread = None
        self._stop_event = Event()
        self.scan_complete_event = Event()
        self.movement_event = Event()
        self.angles_event = Event()
        
        # buffer
        self.buffer = bytearray()
        
        # callbacks
        self.callbacks = {}
        
        # states
        self.movement_status: Dict[str, Dict[str, Any]] = {}
        self.current_angles: Dict[str, float] = {}
        self.safety_status: Dict[str, Any] = {}
        self.scan_data = None
        
        self.camera = CameraManager(camera_index=camera_index)
        self.object_detect_model = ImageProcessor(confidence_threshold=0.45)
                
    def connect(self) -> bool:
        """serial connection"""
        if self.is_connected:
            return True
        
        try:
            self.serial_port = serial.Serial(
                port=self.port, 
                baudrate=self.baudrate,
                timeout=10,
                write_timeout=10
            )
            self.is_connected = True
            
            # read loop
            self._stop_event.clear()
            self._read_thread = Thread(target=self._read_loop, daemon=True)
            self._read_thread.start()
            return True
            
        except Exception as e:
            log.error(f'Error connecting to serial port: {str(e)}')
            return False
        
    def close(self):
        """"close serial connection"""
        self._stop_event.set()
        if self._read_thread:
            self._read_thread.join(timeout=1.0)
            
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            self.is_connected = False
            log.info('Serial connection closed')
            
    def send_message(self, message_type: str, data: dict) -> bool:
        """
        send json message to robot
        :param message_type: 'check_service', 'safety_service', etc.
        :param data: message data
        """
        if not self.is_connected or not self.serial_port:
            log.error("Error: serial port not initialized")
            return False
        
        try:
            message = {
                'type': message_type,
                'data': data,
            }
            encoded_message = json.dumps(message).encode() + self.message_end
            self.serial_port.write(encoded_message)
            return True
        except Exception as e:
            print(f"Error enviando mensaje: {e}")
            return False
            
    def register_callback(self, message_type: str, callback: callable):
        self.callbacks[message_type] = callback
        
    def _read_loop(self):
        """Thread loop for read messages from VEX"""
        while not self._stop_event.is_set():
            if self.serial_port and self.serial_port.in_waiting:
                try:
                    char = self.serial_port.read()
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

            if msg_type == 'check_service':
                state = data.get('state')
                log.info(f'{msg_type} status:\nstate: {state}')

            elif msg_type == 'safety_service':
                self.safety_status = message.get('data', {})
                state = data.get('state')
                time_taken = data.get('time')
                log.info(f"{msg_type} status: \nstate: {state}, \ntime: {time_taken}s")
                if state == 'error':
                    log.error(f"Safety Service Error: {data.get('error_msg', 'Unknown error')}")

            elif msg_type == 'scan_service':
                state = data.get('state')
                if state == 'detected':
                    Thread(target=self._handle_object_detection, args=(data,)).start()
                    log.info(f"Scan Data - Object Detected: "
                            f"Angle:    {data['angle']}° "
                            f"Distance: {data['distance']}mm")

                elif state == 'complete':
                    self.scan_complete_event.set()
                    log.info("¡scan completed!")
            
            elif msg_type in ('pick_service', 'place_service'):
                joint = data.get('joint')
                self.movement_status[joint] = data
                self.movement_event.set()
                
            elif msg_type == 'current_angles':
                self.current_angles = message.get('data', {})
                self.angles_event.set()
                
        except Exception as e:
            log.error(f'error process message: {e}')
            
    def _handle_object_detection(self, data: dict):
        """object detect in real time"""
        try:
            # 1. capture image
            img_path = self.camera.capture_image()
            if not img_path:
                log.error("camera could not be captured")
                return
            
            # 2. YOLO detection
            image, yolo_result = self.object_detect_model.read_image_path(img_path, draw_results=True, save_drawn_img=True)
            if yolo_result is None:
                log.info("no detections.")
                return
            
            # 3. update data
            data.update({
                'class': yolo_result['class'],
                'confidence': yolo_result['confidence'],
                'timestamp': time.time(),
                'image_path': img_path
            })
            
            # 4. notify the central system
            if self.callbacks.get('scan_service'):
                self.callbacks['scan_service'](data)
                
        except Exception as e:
            log.error(f"error in object detection: {str(e)}")
            
    def get_scan_data(self, timeout: float = 30.0) -> list:
        if self.scan_complete_event.wait(timeout):
            self.scan_complete_event.clear()
            return self.scan_data
        return []
    
    def wait_for_confirmation(self, joint:str, timeout: float = 30.0) -> bool:
        """wait for movement confirmed"""
        start_time = time.time()
        self.movement_event.clear()
        
        while (time.time() - start_time) < timeout:
            if self.movement_status.get(joint, {}).get('state') == 'completed':
                return True
            if self.movement_status.get(joint, {}).get('state') == 'error':
                log.error(f'error in movement')
                return False
            self.movement_event.wait(0.1)
        
        log.warning(f"timeout, waiting movement of: {joint}")
        return False
    
    def wait_for_angles_response(self, timeout: float = 5.0) -> bool:
        self.angles_event.clear()
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            if self.current_angles:
                return True
            self.angles_event.wait(0.1)
            
        return False
