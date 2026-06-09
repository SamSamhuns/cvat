import base64
import io
import json
import os
from pathlib import Path

import yaml
from PIL import Image
from ultralytics import YOLO


FUNCTION_CONFIG_PATH = "/opt/nuclio/function.yaml"


def _read_labels():
    with open(FUNCTION_CONFIG_PATH, "rb") as function_file:
        function_config = yaml.safe_load(function_file)

    labels_spec = function_config["metadata"]["annotations"]["spec"]
    return {int(item["id"]): item["name"] for item in json.loads(labels_spec)}


def _read_image_size():
    image_size = os.getenv("IMAGE_SIZE")
    if image_size:
        return int(image_size)
    return None


class ModelHandler:
    def __init__(self, labels):
        model_path = Path(os.getenv("MODEL_PATH", "/opt/nuclio/model.pt"))
        if not model_path.exists():
            raise FileNotFoundError(
                f"Cannot find YOLO26 weights at {model_path}. "
                "Put your .pt file in the function directory as model.pt, "
                "or set MODEL_PATH to a mounted weights file."
            )

        self.model = YOLO(str(model_path))
        self.labels = labels
        self.device = os.getenv("DEVICE") or None
        self.image_size = _read_image_size()

    def _label_name(self, result, class_id):
        if class_id in self.labels:
            return self.labels[class_id]

        names = getattr(result, "names", None) or getattr(self.model, "names", None) or {}
        if isinstance(names, dict):
            return names.get(class_id) or names.get(str(class_id)) or f"class_{class_id}"
        if isinstance(names, (list, tuple)) and 0 <= class_id < len(names):
            return names[class_id]
        return f"class_{class_id}"

    def infer(self, image, threshold):
        predict_kwargs = {
            "source": image,
            "conf": threshold,
            "verbose": False,
        }
        if self.device:
            predict_kwargs["device"] = self.device
        if self.image_size:
            predict_kwargs["imgsz"] = self.image_size

        prediction = self.model.predict(**predict_kwargs)[0]
        if prediction.boxes is None:
            return []

        boxes = prediction.boxes.xyxy.cpu().numpy()
        scores = prediction.boxes.conf.cpu().numpy()
        class_ids = prediction.boxes.cls.cpu().numpy().astype(int)

        width, height = image.size
        results = []
        for box, score, class_id in zip(boxes, scores, class_ids):
            xtl = max(int(box[0]), 0)
            ytl = max(int(box[1]), 0)
            xbr = min(int(box[2]), width)
            ybr = min(int(box[3]), height)

            results.append(
                {
                    "confidence": str(float(score)),
                    "label": self._label_name(prediction, int(class_id)),
                    "points": [xtl, ytl, xbr, ybr],
                    "type": "rectangle",
                }
            )

        return results


def init_context(context):
    context.logger.info("Init context...  0%")

    labels = _read_labels()
    context.user_data.model_handler = ModelHandler(labels)

    context.logger.info("Init context...100%")


def handler(context, event):
    context.logger.info("Run Ultralytics YOLO26 model")
    data = event.body
    buf = io.BytesIO(base64.b64decode(data["image"]))
    threshold = float(data.get("threshold", 0.5))
    image = Image.open(buf).convert("RGB")

    results = context.user_data.model_handler.infer(image, threshold)

    return context.Response(
        body=json.dumps(results), headers={}, content_type="application/json", status_code=200
    )
