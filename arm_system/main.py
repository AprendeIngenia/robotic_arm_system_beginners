import time
import logging as log

# Importa tu CommunicationManager
from communication.serial_manager import CommunicationManager

log.basicConfig(level=log.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class Robot:
    def __init__(self):
        self.serial_manager = CommunicationManager(port='/dev/ttyACM1', baudrate=115200)
        
        # register scan data
        self.scan_results = []
        self.serial_manager.register_callback('scan_service', self._scan_callback)
        
        # zones
        self.placement_zones = {
            'apple': {'angle': 90, 'distance': 200},
            'orange': {'angle': 180, 'distance': 200},
            'bottle': {'angle': 45, 'distance': 200},
            'default': {'angle': 270, 'distance': 200},
        }
        
    # --- MENU ---
    def main_menu_loop(self):
        running = True
        while running:
            print("\n=== Main menu ===")
            print(" [c] check service")
            print(" [s] safety service")
            print(" [n] scan service")
            print(" [p] pick & place service")
            print(" [q] exit")
            
            user_input = input("input command: ").strip().lower()

            if user_input == 'c':
                self.serial_manager.send_message('check_service', {})
                
            elif user_input == 's':
                self.serial_manager.send_message('safety_service', {})
                
            elif user_input == 'n':
                self.handle_scan_command()
                
            elif user_input == 'p':
                self.handle_pick_place_command()
                
            elif user_input == 'q':
                running = False
                
            else:
                print("command unrecognized")
            
            time.sleep(0.5)
            
    # --- SCAN ---
    def handle_scan_command(self):
        """scan command"""
                
        self.scan_results = []
        self.serial_manager.register_callback('scan_service', self._scan_callback)
        
        self.serial_manager.send_message('scan_service', {'speed': 20})
        
        log.info("scanning in progress...")
        
        if self.serial_manager.scan_complete_event.wait(timeout=60):
            self.serial_manager.scan_complete_event.clear()
            self.process_scan_results()
        else:
            log.error("scanning timeout")
        
        self.serial_manager.register_callback('scan_service', None)
        
    def _scan_callback(self, data):
        if data.get('class'):
            self._update_object_registry(data)
            
    def _update_object_registry(self, data: dict):
        """update object registry"""
        try:
            self.scan_results.append({
                'position': {
                    'angle': data.get('angle', 0),
                    'distance': data.get('distance', 0)
                },
                'detection':{
                    'class': data.get('class', 'default'),
                    'confidence': data.get('confidence', 0.0),
                    'image': data.get('image_path', '')
                },
                'placement_zone': self._get_placement_zones(data.get('class', 'default'))
            })
        except Exception as e:
            log.error(f"error updating registry: {str(e)}")
        
    def _get_placement_zones(self, object_class: str):
        return self.placement_zones.get(object_class.lower(), 
                                        self.placement_zones['default'])          
          
    def process_scan_results(self):
        """process scan data"""
        if not self.scan_results:
            log.warning("scanning completed without object detection")
            return
            
        log.info(f"\n=== objects scanned: ({len(self.scan_results)}) ===")
        processed_list = []
        for i, obj in enumerate(self.scan_results, start=1):
            angle = obj['position']['angle']
            distance = obj['position']['distance']
            obj_class = obj['detection']['class']
            confidence = obj['detection']['confidence']
            zone = obj['placement_zone']

            item = {
                'index': i,
                'center_angle': angle,
                'distance': distance,
                'class': obj_class,
                'confidence': confidence,
                'placement_zone': zone
            }
            processed_list.append(item)

            log.info(f"Obj {i} -> angle: {angle}°, distance: {distance}mm, class: {obj_class}, conf: {confidence:.2f}")

        self.scan_results = processed_list
    
    # --- PICK & PLACE ---
    def handle_pick_place_command(self):
        """pick & place command"""
        if not self.scan_results:
            log.warning("1. first scanning the enviroment (option 'n')")
            return

        selected_object = self.select_object_interactively()
        if not selected_object:
            return

        log.info(f"\ninit pick & place to object: {selected_object['index']}:")
        log.info(f"angle: {selected_object['center_angle']}°")
        log.info(f"distance: {selected_object['distance']} mm")
        
        if self.execute_pick_sequence(selected_object):
            log.info(f"¡pick completed!")
            if self.execute_place_sequence(selected_object):
                log.info(f"¡pick and place completed!")
                
    def select_object_interactively(self):
        """interface for object selection"""
        print("\n=== OBJECTS DETECTED LIST ===")
        for o in self.scan_results:
            i = o['index']
            print(f"[{i}] angle={o['center_angle']}° dist={o['distance']}mm class={o['class']} conf={o['confidence']:.2f}")
        print("[0] cancelar")
        
        try:
            selection = int(input("\nselect the object you want to take: "))
            if selection == 0:
                print("operation canceled")
                return {}
            
            return next((x for x in self.scan_results if x['index'] == selection), {})
        
        except ValueError:
            print("invalid input")
            return {}
        
    def execute_pick_sequence(self, target_object: dict) -> bool:
        try:
            plan = [
                {'joint': 'base', 'angle': target_object['center_angle'], 'speed': 30},
                {'joint': 'arm', 'distance': target_object['distance'], 'action': 'pick'},
                {'joint': 'gripper', 'action': 'close'},
                {'joint': 'arm', 'distance': target_object['distance'], 'action': 'up'},
            ]
            self.execute_movement('pick_service', plan)
            return True
        except Exception as e:
            log.error(f"Error in pick sequence: {e}")
            return False
        
    def execute_place_sequence(self, target_object: dict):
        """execute object in place"""
        try:
            zone_params = target_object['placement_zone']
            movement_plan = [
                {'joint': 'base', 'angle': zone_params['angle'], 'speed': 30},
                {'joint': 'arm', 'distance': zone_params['distance'], 'action': 'place'},
                {'joint': 'gripper', 'action': 'open'},
                {'joint': 'arm', 'distance': target_object['distance'], 'action': 'up'},
                {'joint': 'base', 'angle': 0, 'speed': 60},  # Regresar a base 0
            ]
            self.execute_movement('place_service', movement_plan)
            return True
        except Exception as e:
            log.error(f"Error in place sequence: {e}")
            return False
        
            
    def get_current_angles(self) -> dict:
        """get current angles"""
        try:
            self.serial_manager.send_message('get_angles', {})
            
            if self.serial_manager.wait_for_angles_response(timeout=5):
                return self.serial_manager.current_angles
            else:
                raise Exception('timeout for to get angles')
            
        except Exception as e:
            log.error(f"error to get angles: {e}")
            return None
        
    def execute_movement(self, message_type: str, movement_sequence: list):
        """send commands to arm"""
        log.info("\nexecution movements:")
        
        for move in movement_sequence:
            try:
                joint = move['joint']
                log.info(f"movement: {joint}")
                
                # reset state
                self.serial_manager.movement_status[joint] = {'state': 'pending'}
                
                # send command
                self.serial_manager.send_message(message_type, move)
                
                # wait for confirmation
                if not self.serial_manager.wait_for_confirmation(joint):
                    raise Exception(f"movement failed in: {joint}")
                
                # log
                log.info(f"-> ¡Movement {joint} completed!")
                    
            except Exception as e:
                log.error(f'error in movement: {str(e)}')
                self.handle_movement_failure()
                raise
            
    def handle_movement_failure(self):
        """Handles faults in the motion sequence"""
        log.error('executing security protocol')
        self.serial_manager.send_message('safety_service', {})
        
        start_time = time.time()
        while (time.time() - start_time) < 15:
            if self.serial_manager.safety_status.get('state') == 'completed':
                log.info("system safety")
                return
            time.sleep(0.5)
            
        log.error("error in safety service")
        self.serial_manager.close()
        exit(1)
            
            
    def run(self):
        try:
            if self.serial_manager.connect():
                log.info("connected to VEX brain")
                self.main_menu_loop()
                
        except KeyboardInterrupt:
            log.info("Programa interrumpido por el usuario.")
        finally:
            log.info("closing serial connection.")
            self.serial_manager.close()


if __name__ == '__main__':
    robot = Robot()
    robot.run()
