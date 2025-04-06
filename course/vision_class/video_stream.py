import os
import sys
import cv2
import logging as log

from process.image_processing import ImageProcessor

class VideoStream:
    def __init__(self, source: str = 0, confidence_threshold: float = 0.45):
        self.source = source
        self.confidence_threshold = confidence_threshold
        self.image_processor = ImageProcessor(confidence_threshold=confidence_threshold)
        self.video_capture = None

    def start_stream(self):
        self.video_capture = cv2.VideoCapture(self.source)
        if not self.video_capture.isOpened():
            log.error(f"Error opening video stream or file: {self.source}")
            return False

        while True:
            ret, frame = self.video_capture.read()
            if not ret:
                log.error("Failed to capture frame from video stream.")
                break
            
            # inference
            processed_frame, best_detection = self.image_processor.process_image(frame, self.confidence_threshold)
            
            # draw detections
            if best_detection is not None and best_detection.get('confidence', 0) > 0:
                self.image_processor._draw_detection(processed_frame, best_detection)
                
            cv2.imshow('Video Stream', processed_frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        self.video_capture.release()
        cv2.destroyAllWindows()
        return True
    

if __name__ == "__main__":
    real_time_inference = VideoStream(0, 0.45)
    real_time_inference.start_stream()