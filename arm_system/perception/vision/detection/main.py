import numpy as np
from typing import Tuple, Dict
from abc import ABC, abstractmethod

from ultralytics.engine.results import Results
from .model_loader import ModelLoader


class DetectionModelInterface(ABC):
    @abstractmethod
    def inference(self, image: np.ndarray) -> Tuple[Results, Dict[int, str]]:
        pass
    

class DetectionModel(DetectionModelInterface):
    def __init__(self):
        self.object_model = ModelLoader().get_model()

    def inference(self, image: np.ndarray) -> tuple[list[Results], Dict[int, str]]:
        results = self.object_model.predict(image, conf=0.55, verbose=False, imgsz=640, stream=True, task='detect', half=True)
        return results, self.object_model.names
    