import os

from typing import Dict
from ultralytics import YOLO


class ModelLoader:
    def __init__(self):
        current_path = os.path.dirname(os.path.abspath(__file__))
        object_model_path: str = current_path + '/models/yolo11s_ncnn_model'
        self.model: YOLO = YOLO(object_model_path, task='detect')
        
    def get_model(self) -> YOLO:
        return self.model
    