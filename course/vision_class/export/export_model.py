from ultralytics import YOLO

model = YOLO('models/torch/yolo11s.pt')

model.export(format="mnn")
