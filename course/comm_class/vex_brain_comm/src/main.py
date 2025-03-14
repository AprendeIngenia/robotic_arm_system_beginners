# ---------------------------------------------------------------------------- #
#                                                                              #
# 	Module:       main.py                                                      #
# 	Author:       santi                                                        #
# 	Created:      3/14/2025, 1:55:53 PM                                        #
# 	Description:  IQ2 project                                                  #
#                                                                              #
# ---------------------------------------------------------------------------- #
# vex:disable=repl

# Library imports
from vex import *
import json

brain = Brain()


def read_data():
    try:
        s = open('/dev/serial1', 'rb')
    except:
        raise Exception('serial port not available')

    while True:
        data = s.read(1)
        brain.screen.print_at("RX: {}".format(str(data)), x=1, y=95)
        
def write_data():
    try:
        s = open('/dev/serial1', 'wb')
    except:
        raise Exception('serial port not available')

    while True:
        s.write('A')
        brain.screen.print_at("TX: A", x=1, y=95)
        sleep(1000)
        
def json_data():
    buffer = bytearray()
    try:
        s = open('/dev/serial1', 'rb+')
    except:
        raise Exception('serial port error')
    
    while True:
        char = s.read(1)
        if char == b'\n':
            message = buffer.decode()
            buffer = bytearray()
            try:
                msg = json.loads(message)
                msg_type = msg['type'].lower()
                data = msg.get('data', {})
            
                if msg_type == 'test_service' and data.get('state') == 'successfully':
                    write_data = {'state': 'successfully'}
                    message = {
                        'type': msg_type,
                        'data': write_data,}
                    
                    encoded_message = json.dumps(message).encode() + b'\n'
                    s.write(encoded_message)
                    brain.screen.print_at("serial com:", x=1, y=15)
                    brain.screen.print_at("¡successfully!", x=1, y=35)
            except:
                raise Exception('json error')
        else:
            buffer.extend(char)
            

#t1 = Thread(read_data)
#t2 = Thread(write_data)
t3 = Thread(json_data)