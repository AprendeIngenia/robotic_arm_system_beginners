from ultralytics import YOLO

model = YOLO('model/yolo11s.pt')

model.export(format="ncnn")
