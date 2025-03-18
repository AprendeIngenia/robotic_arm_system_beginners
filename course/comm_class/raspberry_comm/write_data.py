import serial


class SerialCommunication:
    def __init__(self):
        self.com = serial.Serial("COM7", 115200, write_timeout=10) # raspberry: "/dev/ttyACM0"

    def writing_data(self, command: str) -> None:
        self.com.write(command.encode('ascii'))
        print(f'SENDING DATA: {command}')


if __name__ == "__main__":
    serial_comm = SerialCommunication()
    serial_comm.writing_data('e')
