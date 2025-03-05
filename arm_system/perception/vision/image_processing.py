import cv2
import numpy as np
import logging as log
log.basicConfig(level=log.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

from .detection.main import (DetectionModelInterface, DetectionModel)

class ImageProcessor:
    def __init__(self, confidence_threshold: float = 0.45):
        self.detection: DetectionModelInterface = DetectionModel()
        self.conf_threshold = confidence_threshold
        
    def read_image_path(self, path: str, draw_results: bool = True, save_drawn_img: bool = True):
        object_image = cv2.imread(path)
        processed_img, best_detection = self.process_image(object_image, self.conf_threshold)
        
        if draw_results and best_detection is not None and best_detection.get('confidence', 0) > 0:
            self._draw_detection(processed_img, best_detection)
            if save_drawn_img:
                self._save_drawn_image(processed_img, path)

        return processed_img, best_detection
    
    def process_image(self, image: np.ndarray, confidence_threshold: float =0.45):
        try:
            # 1. inference
            copy_image = image.copy()
            object_results, object_classes = self.detection.inference(copy_image)
            
            # 2. init variables
            best_detection = {'class': '', 'confidence': 0.0, 'box': [], 'class_id': -1}
            
            # 3. process results
            for res in object_results:
                boxes = res.boxes
                
                if boxes.shape[0] == 0:
                        continue
                    
                confidence = boxes.conf.cpu().numpy()[0]
                class_id = int(boxes.cls[0])
                box_data = boxes.xyxy.cpu().numpy()[0]
                    
                if confidence < confidence_threshold:
                    continue
                    
                detected_class = object_classes[class_id]
                clss_object = 'default'
                    
                if detected_class in ['apple', 'orange', 'bottle']:
                    clss_object = detected_class
                    
                log.info(f'class: {clss_object}')
                        
                if confidence > best_detection['confidence']:
                    best_detection.update({
                        'class': str(clss_object),
                        'confidence': float(confidence),
                        'box': box_data,
                        'class_id': class_id
                    })
                        
            # 4. final result
            if best_detection['confidence'] >= confidence_threshold:
                log.info(f"best detection: {best_detection}")
                return image, best_detection
            else:
                log.info("not found detections")
                return image, best_detection
        except Exception as e:
            log.info(f'error un image processing: {e}')
            return image, None
        
    def _draw_detection(self, image: np.ndarray, detection: dict):
        """
        draw image. 
        """
        box = detection['box']
        class_name = detection['class']
        confidence = detection['confidence']

        x1, y1, x2, y2 = map(int, box)
        color = (0, 255, 0)  # BGR - verde
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)

        label = f"{class_name} {confidence:.2f}"
        cv2.putText(image, label, (x1, y1 - 10),cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

    def _save_drawn_image(self, image: np.ndarray, original_path: str):
        """
        save image.
        """
        out_path = original_path.replace('.jpg', '_detected.jpg')
        cv2.imwrite(out_path, image)
        log.info(f"save image with draw detections: {out_path}")