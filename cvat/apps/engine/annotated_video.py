# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from __future__ import annotations

import os
import tempfile
from collections import defaultdict
from collections.abc import Iterator
from typing import Any

import av
import cv2
import numpy as np
from django.conf import settings
from rest_framework.exceptions import ValidationError

import cvat.apps.dataset_manager as dm
from cvat.apps.dataset_manager.annotation import AnnotationIR, AnnotationManager
from cvat.apps.engine import models
from cvat.apps.engine.media_extractors import IMediaReader, Mpeg4ChunkWriter
from cvat.apps.engine.media_io.frame_provider import FrameOutputType, JobFrameProvider

_DEFAULT_EXPORT_QUALITY = 70
_LINE_THICKNESS = 2
_FONT_SCALE = 0.45
_PALETTE: tuple[tuple[int, int, int], ...] = (
    (0, 153, 255),
    (51, 204, 51),
    (255, 128, 0),
    (204, 102, 255),
    (255, 80, 80),
    (0, 204, 204),
    (255, 204, 0),
)


def export_annotated_job_video(db_job: models.Job) -> str:
    db_task = db_job.segment.task
    if db_task.dimension != str(models.DimensionType.DIM_2D):
        raise ValidationError("Annotated video export is available only for 2D jobs")

    output_file = tempfile.NamedTemporaryFile(
        prefix=f"job_{db_job.id}_annotated_",
        suffix=".mp4",
        dir=settings.TMP_FILES_ROOT,
        delete=False,
    )
    output_path = output_file.name
    output_file.close()

    try:
        writer = Mpeg4ChunkWriter(
            quality=db_task.data.image_quality or _DEFAULT_EXPORT_QUALITY,
            dimension=models.DimensionType.DIM_2D,
        )
        writer.save_as_chunk(_iter_annotated_frames(db_job), output_path)
    except Exception:
        if os.path.exists(output_path):
            os.remove(output_path)
        raise

    return output_path


def _iter_annotated_frames(db_job: models.Job) -> Iterator[IMediaReader.VideoFrame]:
    shapes_by_frame = _get_shapes_by_frame(db_job)
    labels = _get_labels(db_job)
    provider = JobFrameProvider(db_job)

    for frame_number in range(db_job.segment.start_frame, db_job.segment.stop_frame + 1):
        try:
            frame = provider.get_frame(
                frame_number,
                quality=models.FrameQuality.ORIGINAL,
                out_type=FrameOutputType.NUMPY_ARRAY,
            ).data
        except ValidationError:
            continue

        frame = _to_bgr24(frame)
        for shape in sorted(
            shapes_by_frame.get(frame_number, ()),
            key=lambda s: s.get("z_order", 0),
        ):
            _draw_shape(frame, shape, labels)

        yield av.VideoFrame.from_ndarray(frame, format="bgr24"), None


def _to_bgr24(frame: np.ndarray) -> np.ndarray:
    if len(frame.shape) == 2:
        return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
    if frame.shape[2] == 4:
        return frame[:, :, :3].copy()
    return frame.copy()


def _get_shapes_by_frame(db_job: models.Job) -> dict[int, list[dict[str, Any]]]:
    db_task = db_job.segment.task
    annotations = dm.task.get_job_data(db_job.id)
    annotation_manager = AnnotationManager(
        AnnotationIR(db_task.dimension, annotations),
        dimension=db_task.dimension,
    )
    included_frames = range(db_job.segment.start_frame, db_job.segment.stop_frame + 1)
    shapes_by_frame: dict[int, list[dict[str, Any]]] = defaultdict(list)

    for shape in annotation_manager.to_shapes(
        db_job.segment.stop_frame + 1,
        included_frames=included_frames,
        deleted_frames=db_task.data.deleted_frames,
        include_outside=False,
    ):
        shapes_by_frame[shape["frame"]].append(shape)

    return shapes_by_frame


def _get_labels(db_job: models.Job) -> dict[int, str]:
    db_task = db_job.segment.task
    labels = db_task.project.label_set.all() if db_task.project_id else db_task.label_set.all()
    return {label.id: label.name for label in labels}


def _label_color(label_id: int | None) -> tuple[int, int, int]:
    return _PALETTE[(label_id or 0) % len(_PALETTE)]


def _points(points: list[float]) -> np.ndarray:
    return np.rint(np.asarray(points, dtype=np.float32).reshape((-1, 2))).astype(np.int32)


def _draw_shape(
    frame: np.ndarray,
    shape: dict[str, Any],
    labels: dict[int, str],
    parent_color: tuple[int, int, int] | None = None,
) -> None:
    if shape.get("outside"):
        return

    shape_type = shape["type"]
    color = parent_color or _label_color(shape.get("label_id"))
    points = shape.get("points") or []
    label_origin: tuple[int, int] | None = None

    if shape_type == str(models.ShapeType.SKELETON):
        for element in shape.get("elements", []):
            _draw_shape(frame, element, labels, color)
        return

    if shape_type == str(models.ShapeType.RECTANGLE) and len(points) == 4:
        x0, y0, x1, y1 = points
        rotation = float(shape.get("rotation") or 0)
        if rotation:
            center = ((x0 + x1) / 2, (y0 + y1) / 2)
            size = (abs(x1 - x0), abs(y1 - y0))
            box = cv2.boxPoints((center, size, rotation)).astype(np.int32)
            cv2.polylines(frame, [box], True, color, _LINE_THICKNESS, cv2.LINE_AA)
            label_origin = tuple(box.min(axis=0))
        else:
            start = (round(x0), round(y0))
            end = (round(x1), round(y1))
            cv2.rectangle(frame, start, end, color, _LINE_THICKNESS)
            label_origin = start
    elif shape_type == str(models.ShapeType.ELLIPSE) and len(points) == 4:
        center_x, center_y, right, top = points
        center = (round(center_x), round(center_y))
        axes = (round(abs(right - center_x)), round(abs(center_y - top)))
        cv2.ellipse(
            frame,
            center,
            axes,
            float(shape.get("rotation") or 0),
            0,
            360,
            color,
            _LINE_THICKNESS,
            cv2.LINE_AA,
        )
        label_origin = (center[0] - axes[0], center[1] - axes[1])
    elif (
        shape_type in {str(models.ShapeType.POLYGON), str(models.ShapeType.POLYLINE)}
        and len(points) >= 4
    ):
        contour = _points(points)
        cv2.polylines(
            frame,
            [contour],
            shape_type == str(models.ShapeType.POLYGON),
            color,
            _LINE_THICKNESS,
            cv2.LINE_AA,
        )
        label_origin = tuple(contour.min(axis=0))
    elif shape_type == str(models.ShapeType.POINTS) and len(points) >= 2:
        contour = _points(points)
        for point in contour:
            cv2.circle(frame, tuple(point), 3, color, -1, cv2.LINE_AA)
        label_origin = tuple(contour.min(axis=0))
    elif shape_type == str(models.ShapeType.MASK) and len(points) >= 4:
        x0, y0, x1, y1 = points[-4:]
        start = (round(x0), round(y0))
        end = (round(x1), round(y1))
        cv2.rectangle(frame, start, end, color, _LINE_THICKNESS)
        label_origin = start

    if label_origin and shape.get("label_id") in labels:
        _draw_label(frame, labels[shape["label_id"]], label_origin, color)


def _draw_label(
    frame: np.ndarray,
    label: str,
    origin: tuple[int, int],
    color: tuple[int, int, int],
) -> None:
    x = max(0, min(int(origin[0]), frame.shape[1] - 1))
    y = max(0, min(int(origin[1]), frame.shape[0] - 1))
    (text_width, text_height), baseline = cv2.getTextSize(
        label,
        cv2.FONT_HERSHEY_SIMPLEX,
        _FONT_SCALE,
        1,
    )
    y = max(y, text_height + baseline + 4)
    cv2.rectangle(
        frame,
        (x, y - text_height - baseline - 4),
        (min(x + text_width + 4, frame.shape[1] - 1), y + baseline),
        color,
        -1,
    )
    cv2.putText(
        frame,
        label,
        (x + 2, y - 3),
        cv2.FONT_HERSHEY_SIMPLEX,
        _FONT_SCALE,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
