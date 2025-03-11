# ---------------------------------------------------------------------------- #
#                                                                              #
# 	Module:       main.py                                                      #
# 	Author:       santi                                                        #
# 	Created:      2/21/2025, 3:46:40 PM                                        #
# 	Description:  IQ2 project                                                  #
#                                                                              #
# ---------------------------------------------------------------------------- #
# vex:disable=repl

# Library imports
from vex import *
import json
import time

# colors
LED_COLORS = {
    'ERROR': (255, 0, 0),         # Red: Error/Stop
    'WARNING': (255, 150, 0),     # Orange: Warning
    'READY': (0, 255, 0),         # Green: Ready
    'RUNNING': (0, 0, 255),       # Blue: Process Running
    'INIT': (255, 255, 255)       # White: Initialization
}

# serial communication
class CommunicationManager:
    def __init__(self):
        self.serial_port = None
        self.buffer = bytearray()
        self.message_end = b'\n'
        
    def initialize(self):
        try:
            self.serial_port = open('/dev/serial1', 'rb+')
        except:
            raise Exception('serial port error')
        
    def read_message(self):
        char = self.serial_port.read(1)
        if char == self.message_end:
            message = self.buffer.decode()
            self.buffer = bytearray()
            try:
                return json.loads(message)
            except json.JSONDecodeError:
                return None
        else:
            self.buffer.extend(char)
        return None
    
    def send_message(self, msg_type: str, data: dict):        
        message = {
            'type': msg_type,
            'data': data,
        }
            
        encoded_message = json.dumps(message).encode() + self.message_end
        self.serial_port.write(encoded_message)
        return True
    

# sensor module
class SensorModule:
    def __init__(self):
        self.brain = Brain()
        self.inertial = Inertial()
        self.gripper_distance = Distance(Ports.PORT7)
        self.touchled = Touchled(Ports.PORT8)
        self.base_distance = Distance(Ports.PORT9)
        self.bumper = Bumper(Ports.PORT10)
        
    def clear_screen(self):
        self.brain.screen.clear_screen()
        
    def print_screen(self, text:str, coordinate_x: int, coordinate_y: int):
        self.brain.screen.print_at(text, x=coordinate_x, y=coordinate_y)
    
    #def calibrate_inertial(self):
    #    self.inertial.calibrate()
        
    def get_angle(self):
        return self.inertial.heading()
    
    def get_distance(self, sensor):
        return sensor.object_distance(MM)
    
    def get_object_size(self, sensor):
        return sensor.object_rawsize()
    
    def is_bumper_pressed(self):
        return self.bumper.pressing()
    
    def set_color(self, color):
        self.touchled.set_color(*color)
        
    def check_sensors(self):
        return all([
            self.base_distance.installed(),
            self.gripper_distance.installed(),
            self.bumper.installed()
        ])
        

# perception module
class PerceptionModule:
    def __init__(self, sensor_module):
        self.sensor = sensor_module
        self.current_object_size = 0
        self.object_detected = False
        
    def process_sensor_distance(self, sensor, min_d, max_d):
        dist = self.sensor.get_distance(sensor)
        if min_d <= dist <= max_d:
            self.current_object_size = self.sensor.get_object_size(sensor)
            self.object_detected = True
            self.sensor.set_color(LED_COLORS['READY'])
        else:
            self.current_object_size = 0
            self.object_detected = False
            self.sensor.set_color(LED_COLORS['RUNNING'])
            
        return {'distance': dist, 'size': self.current_object_size, 'detected': self.object_detected}
    
    
# mapping module
class MappingModule:
    def __init__(self):
        self.objects_map = []
        self.current_object = (0.0, 0.0, 0, 0, False)  # (start, end, max_size, distance, tracking)
    
    def process_object_detection(self, angle, size, dist):
        if size > 0:
            if not self.current_object[4]:
                self.current_object = (angle, angle, size, dist, True)
            else:
                self.current_object = (
                    self.current_object[0],
                    angle,
                    max(self.current_object[2], size),
                    self.current_object[3],
                    True
                )
        elif self.current_object[4]:
            self._save_object(angle)
            
    def _save_object(self, end_angle):
        start, _, max_size, dist, _ = self.current_object
        end = end_angle
        
        # Cálculo optimizado del ángulo central
        total = end - start if end >= start else end + 360 - start
        center = (start + total/2) % 360
        
        self.objects_map.append({
            'center_angle': round(center, 1),
            'width': round(total, 1),
            'distance': dist,
            'max_size': max_size
        })
        self.current_object = (0.0, 0.0, 0, 0, False)
    
    def get_objects_map(self):
        result = self.objects_map
        self.objects_map = []
        return result
    

# control module
class ControlModule:
    def __init__(self, sensor_module:SensorModule):
        self.base_motor = Motor(Ports.PORT1, True)
        self.shoulder_motor = Motor(Ports.PORT2, True)
        self.elbow_motor = Motor(Ports.PORT3, True)
        self.gripper_motor = Motor(Ports.PORT4, True)
        self.sensor_module = sensor_module
        
        self.elbow_motor.set_max_torque(95, PERCENT)
        self.shoulder_motor.set_max_torque(95, PERCENT)
        
    def move_motor_to_angle(self, motor, target, speed):
        if motor == self.base_motor:
            current = self.sensor_module.get_angle()
            delta = (target - current + 360) % 360
            if delta > 180: delta -= 360  # Convertir a camino más corto (-180 a 180)
            
            direction = FORWARD if delta > 0 else REVERSE
            target_angle = (current + delta) % 360
            
            while abs(self.sensor_module.get_angle() - target_angle) > 2:
                motor.spin(direction, speed, RPM)
                wait(10, MSEC)
            motor.stop()
            
    def get_position(self, motor):
        return motor.position(DEGREES)
    
    def get_current(self, motor):
        return motor.current()
    
    def general_stop(self):
        for m in [self.base_motor, self.shoulder_motor, self.elbow_motor, self.gripper_motor]:
            m.stop()
    
    def check_motors(self):
        return all(m.installed() for m in [
            self.base_motor, self.shoulder_motor, 
            self.elbow_motor, self.gripper_motor
        ])
        

# safety module
class SafetyModule:    
    def __init__(self, sensor: SensorModule, control:ControlModule):
        self.sensor_module = sensor
        self.control_module = control
        self.error_count = 0
        
    # check methods
    def check_motors(self):
        return self.control_module.check_motors()
    
    def check_sensors(self):
        return self.sensor_module.check_sensors()
        
    def check_shoulder_safety(self, speed_forward: int, speed_reverse: int):
        if self.sensor_module.is_bumper_pressed():
            self.control_module.general_stop()
            self.sensor_module.set_color(LED_COLORS['ERROR'])
            self.control_module.shoulder_motor.spin(REVERSE, speed_reverse)
            wait(2, SECONDS)
            self.control_module.shoulder_motor.stop(HOLD)
            return True
        else:
            self.control_module.shoulder_motor.spin(FORWARD, speed_forward)
            self.control_module.elbow_motor.spin(REVERSE, 40)
            self.sensor_module.set_color(LED_COLORS['WARNING'])
            return False
    
    def gripper_action(self, action, service):
        self.control_module.shoulder_motor.stop( BRAKE)
        self.control_module.elbow_motor.stop(BRAKE)
        threshold = 0.5 if service == 'pick' else 0.3
        self.control_module.gripper_motor.spin(FORWARD if action == 'open' else REVERSE, 20)
        if self.control_module.get_current(self.control_module.gripper_motor) > threshold:
            self.control_module.gripper_motor.stop(HOLD if service == 'pick' else BRAKE)
            return True
        else:
            return False
    
    
# main module
class RoboticServices:
    def __init__(self):
        self.sensor = SensorModule()
        self.control = ControlModule(self.sensor)
        self.safety = SafetyModule(self.sensor, self.control)
        self.perception = PerceptionModule(self.sensor)
        self.mapping = MappingModule()
        self.comms = CommunicationManager()
        
        self.states = {
            'check_active': False,
            'safety_active': False,
            'scan_active': False,
            'pick_active': False,
            'scan_params': (0.0, 0.0, 0, 20),
        }
        
        self.safety_variables = {
            'safety_shoulder': False,
            'gripper_safety': False}
        
        self.scan_variables = {
            'scan_start': True,
            'scan_update': False,
            'scan_end': False,
            'start_time': 0.0,
            'last_angle': 0,
            'accumulated_rotation': 0,
            'timeout': 40,
            'pause_for_object': False
        }
        #self.sensor.calibrate_inertial()
        
    def run_service(self, service):
        try:
            if service == 'check':
                if self.safety.check_sensors() and self.safety.check_motors():
                    self.sensor.set_color(LED_COLORS['READY'])
                    data = {'state': 'approved'}
                    self.comms.send_message('check_service', data)
                    self.states['check_active'] = False
                else:
                    self.sensor.set_color(LED_COLORS['ERROR'])
                    data = {'error': 'Sensors or motors not installed'}
                    self.comms.send_message('check_error', data)
                    self.states['check_active'] = False
                    
            elif service == 'safety':
                while self.states['safety_active']:
                    if not self.safety_variables['safety_shoulder']:
                        safety_shoulder = self.safety.check_shoulder_safety(speed_forward=60, speed_reverse=10)
                        if safety_shoulder:
                            self.safety_variables['safety_shoulder'] = True
                    else:
                        if not self.safety_variables['gripper_safety']:
                            safety_gripper = self.safety.gripper_action('open', 'safety')
                            if safety_gripper:
                                self.states['safety_active'] = False
                                self.safety_variables['gripper_safety'] = True
                                self.sensor.set_color(LED_COLORS['READY'])

                data = {'state': 'approved'}
                self.comms.send_message('safety_service', data)
                self.states['safety_active'] = False
                self.safety_variables = {'safety_shoulder': False,'gripper_safety': False}
                    
            elif service == 'scan':
                while not self.scan_variables['scan_end']:
                    if self.scan_variables['scan_start']:
                        scan_init = self._execute_start_scan()
                        if scan_init:
                            self.scan_variables['scan_start'] = False
                            self.scan_variables['scan_update'] = True
                    elif self.scan_variables['scan_update']:
                        scan_end = self._execute_scan_service()
                        if scan_end:
                            self.scan_variables['scan_end'] = True
                            self.scan_variables['scan_start'] = True
                            self.scan_variables['scan_update'] = False
                            
                scan_data = self.mapping.get_objects_map()
                data = {'state': 'complete','objects': scan_data,}
                self.comms.send_message('scan_service', data)
                self.states['scan_active'] = False
                        
        except Exception as e:
            self.comms.send_message('error', {'msg': str(e)[:20]})
            
    def reset_scan_variables(self):
        self.scan_variables = {
            'scan_start': True,
            'scan_update': False,
            'scan_end': False,
            'start_time': 0.0,
            'last_angle': 0,
            'accumulated_rotation': 0,
            'timeout': 30,
            'pause_for_object': False
        }
        
    def _execute_start_scan(self):
        if self.scan_variables['scan_end']:
            return False
        
        speed = self.states['scan_params'][3]
        self.scan_variables['start_time'] = time.time()
        self.control.base_motor.spin(FORWARD, speed, RPM)
        self.sensor.set_color(LED_COLORS['RUNNING'])
        return True
        
            
    def _execute_scan_service(self):
        current_angle = self.sensor.get_angle()
        
        delta = current_angle - self.scan_variables['last_angle']
        if delta > 180: delta -= 360
        elif delta < -180: delta += 360
        
        self.scan_variables['accumulated_rotation'] += abs(delta)
        self.scan_variables['last_angle'] = current_angle
        
        data = self.perception.process_sensor_distance(self.sensor.base_distance, 50, 345)
        
        if data['detected'] and not self.scan_variables['pause_for_object']:
            self.scan_variables['pause_for_object'] = True
            self.control.base_motor.stop()
            self.comms.send_message('scan_service', {
                'state': 'detected',
                'angle': current_angle,
                'distance': data['distance'],
                'size': data['size']
            })
            wait(2, SECONDS)
            self.control.base_motor.spin(FORWARD, self.states['scan_params'][3], RPM)
            
        elif not data['detected']:
            self.scan_variables['pause_for_object'] = False
            
        self.mapping.process_object_detection(current_angle, data['size'], data['distance'])
            
        if self.scan_variables['accumulated_rotation'] >= 360 or time.time() - self.scan_variables['start_time'] >= self.scan_variables['timeout']:
            self.control.base_motor.stop()
            return True
                
        return False
    
    def _pick_place_service(self, msg_type, data):
        try:
            if data['joint'] == 'base':
                if data['angle'] > 180:
                    angle = data['angle'] - 4
                else:
                    angle = data['angle'] + 4
                self.control.move_motor_to_angle(self.control.base_motor, angle + 4, data.get('speed', 20))
                self.comms.send_message(msg_type, {'joint': data['joint'],'state': 'completed','target_angle': data['angle'],'actual_angle': self.sensor.get_angle(),'accuracy': abs(data['angle'] - self.sensor.get_angle())})
                
            elif data['joint'] == 'arm':
                object_distance = data['distance']
                if data['action'] == 'pick' or data['action'] == 'place':
                    if self._execute_pick_place_sequence(object_distance, data['action']):
                        self.comms.send_message(msg_type, {'joint': data['joint'], 'state': 'completed'})
                        
                elif data['action'] == 'up':
                    self.sensor.set_color(LED_COLORS['WARNING'])
                    shoulder_complete = False
                    while not shoulder_complete:
                        shoulder_complete = self.safety.check_shoulder_safety(80, 10)
                    self.comms.send_message(msg_type, {'joint': data['joint'], 'state': 'completed'})
                    
            elif data['joint'] == 'gripper':
                gripper_completed = False
                while not gripper_completed:
                    gripper_completed = self.safety.gripper_action(data.get('action', 'close'), 'pick')
                self.comms.send_message(msg_type, {'joint': data['joint'], 'state': 'completed'})
                
            
        except Exception as e:
            self.comms.send_message(msg_type, {'joint': data['joint'], 'error': str(e)})
            
    def _execute_pick_place_sequence(self, object_distance: float = 0.0, action: str = 'pick'):
        timeout = time.time() + 20
        start_time = time.time()
        self.control.gripper_motor.set_stopping(BRAKE)
        
        while time.time() < timeout:
            data = self.perception.process_sensor_distance(self.sensor.gripper_distance, 0, 40)
            
            if action == 'pick':
                if data['detected']:
                    self.control.shoulder_motor.set_stopping(BRAKE)
                    self.control.elbow_motor.set_stopping(BRAKE)
                    #wait(500, MSEC)
                    return True
            
                if object_distance > 160:
                    shoulder_speed = 15
                    elbow_speed = 30
                    
                else:
                    shoulder_speed = 10
                    elbow_speed = 0
            else:
                if time.time() - start_time >= 3:
                    self.control.shoulder_motor.set_stopping(BRAKE)
                    self.control.elbow_motor.set_stopping(BRAKE)
                    #wait(500, MSEC)
                    return True
                
                shoulder_speed = 20
                elbow_speed = 60
                
            self.control.shoulder_motor.spin(REVERSE, shoulder_speed, RPM)
            self.control.elbow_motor.spin(FORWARD, elbow_speed, RPM)
            #wait(100, MSEC)
        return False
        
    def process_message(self, msg):
        if not msg: return
        
        msg_type = msg['type'].lower()
        data = msg.get('data', {})
        
        if msg_type == 'check_service':
            self.states['check_active'] = True
            
        elif msg_type == 'safety_service':
            self.states['safety_active'] = True
            
        elif msg_type == 'scan_service':
            self.states['scan_params'] = (time.time(), 0.0, 0, data.get('speed', 20))
            self.reset_scan_variables()
            self.states['scan_active'] = True
            
        elif msg_type == 'pick_service' or msg_type == 'place_service':
            self._pick_place_service(msg_type, data)
    
    def run(self):
        self.comms.initialize()
        self.sensor.set_color(LED_COLORS['INIT'])
        while True:
            try:
                msg = self.comms.read_message()
                
                if msg:
                    self.process_message(msg)
                    
                    if self.states['check_active']: self.run_service('check')
                    if self.states['safety_active']: self.run_service('safety')
                    if self.states['scan_active']: self.run_service('scan')
                    
            except Exception as e:
                self.sensor.print_screen("Error: {}".format(str(e)[:20]), 1, 95)
                self.control.general_stop()
            
if __name__ == "__main__":
    robot = RoboticServices()
    robot.run()