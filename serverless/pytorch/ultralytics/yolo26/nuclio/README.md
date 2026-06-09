# Ultralytics YOLO26

This Nuclio function runs a custom Ultralytics YOLO26 `.pt` object detection model for CVAT auto annotation.

## Start CVAT with Nuclio

Start CVAT with the serverless compose file from the CVAT repository root:

```bash
docker compose -f docker-compose.yml -f components/serverless/docker-compose.serverless.yml up -d
```

This starts the Nuclio dashboard container that manages local serverless functions. `nuctl` does not start the Nuclio server by itself; it is the CLI used to deploy, inspect, and invoke functions after the Nuclio dashboard is running.

Make sure your `nuctl` version matches the Nuclio dashboard image version in `components/serverless/docker-compose.serverless.yml`.

## Custom classes

Edit the `metadata.annotations.spec` array in `function.yaml` or `function-gpu.yaml` so its IDs match the class IDs used by your trained model:

```json
[
  { "id": 0, "name": "helmet", "type": "rectangle" },
  { "id": 1, "name": "vest", "type": "rectangle" }
]
```

## Custom weights

By default the function loads `/opt/nuclio/model.pt` inside the deployed function container.

For the default CVAT deployment scripts, put your weights in this local function directory before deployment:

```text
serverless/pytorch/ultralytics/yolo26/nuclio/model.pt
```

The scripts call `nuctl deploy --path serverless/pytorch/ultralytics/yolo26/nuclio ...`. Nuclio stages that directory as the function source, so the local file above is copied into the container as:

```text
/opt/nuclio/model.pt
```

Alternatively, set the `MODEL_PATH` environment variable in the function YAML to a mounted path that contains your `.pt` file.

## Deploy with the CVAT scripts

Deploy only this YOLO26 CPU function:

```bash
./serverless/deploy_cpu.sh serverless/pytorch/ultralytics/yolo26/nuclio
```

Deploy only this YOLO26 GPU function:

```bash
./serverless/deploy_gpu.sh serverless/pytorch/ultralytics/yolo26/nuclio
```

You can also pass the parent directory; both scripts recurse and will find the YAML below it:

```bash
./serverless/deploy_cpu.sh serverless/pytorch/ultralytics/yolo26
./serverless/deploy_gpu.sh serverless/pytorch/ultralytics/yolo26
```

The CPU script deploys `function.yaml`. The GPU script deploys `function-gpu.yaml`.

Check deployment status:

```bash
nuctl get functions --platform local
```

Expected function name:

```text
pth-ultralytics-yolo26
```

## Deploy with nuctl directly

CPU:

```bash
nuctl create project cvat --platform local
nuctl deploy --project-name cvat \
  --path serverless/pytorch/ultralytics/yolo26/nuclio \
  --file serverless/pytorch/ultralytics/yolo26/nuclio/function.yaml \
  --platform local \
  --env CVAT_FUNCTIONS_REDIS_HOST=cvat_redis_ondisk \
  --env CVAT_FUNCTIONS_REDIS_PORT=6666 \
  --platform-config '{"attributes": {"network": "cvat_cvat"}}'
```

GPU:

```bash
nuctl create project cvat --platform local
nuctl deploy --project-name cvat \
  --path serverless/pytorch/ultralytics/yolo26/nuclio \
  --file serverless/pytorch/ultralytics/yolo26/nuclio/function-gpu.yaml \
  --platform local \
  --env CVAT_FUNCTIONS_REDIS_HOST=cvat_redis_ondisk \
  --env CVAT_FUNCTIONS_REDIS_PORT=6666 \
  --platform-config '{"attributes": {"network": "cvat_cvat"}}'
```

The `nuctl create project` command is safe to run if the project already exists; the CVAT scripts run it before deploying.

Optional environment variables:

- `MODEL_PATH`: path to the `.pt` weights file. Defaults to `/opt/nuclio/model.pt`.
- `IMAGE_SIZE`: inference image size passed to Ultralytics. Defaults to `640` in the YAML.
- `DEVICE`: `cpu` for CPU or `0` for the first CUDA device in the GPU YAML.

## Quick local invocation

After the function is ready, you can invoke it with any base64-encoded image:

```bash
image=$(base64 -w 0 /path/to/image.jpg)
printf '{"image":"%s","threshold":0.5}' "$image" | \
  nuctl invoke pth-ultralytics-yolo26 --platform local -c application/json
```
