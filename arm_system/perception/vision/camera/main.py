import os
import cv2
import time

class CameraManager:
    def __init__(self, camera_index: int = 0, width: int = 1280, height: int = 720):
        self.cap = cv2.VideoCapture(camera_index)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        
    def capture_image(self):
        for _ in range(5):
            self.cap.grab()
        
        ret, frame = self.cap.read()
        if not ret:
            return None
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"{current_dir}/objects_images/{timestamp}.png"
        
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        cv2.imwrite(filename, frame)
        return filename
        
    def __del__(self):
        self.cap.release()