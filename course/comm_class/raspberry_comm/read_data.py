import serial


class SerialCommunication:
    def __init__(self):
        self.com = serial.Serial("COM7", 115200, write_timeout=10)

    def reading_data(self) -> None:
        while True:
            data = self.com.read()
            print(f'READING DATA: {data}')


if __name__ == "__main__":
    serial_comm = SerialCommunication()
    serial_comm.reading_data()
