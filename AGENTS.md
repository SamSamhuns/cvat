# AI Agent Instructions for CVAT Fork

## Primary Objective

Implement custom features and extensions for this CVAT fork while strictly minimizing merge conflicts with the upstream `cvat-ai/cvat` repository.

## Golden Rules for Code Modification

1. **Isolation over Modification:** Do NOT modify core files unless absolutely necessary. Prefer adding new files, using Django signals (backend), decorators, or subclassing.
2. **UI/Frontend Extensions:** Utilize existing Redux middleware, React hooks, or CVAT's plugin architecture to inject custom UI components or logic. Avoid hardcoding directly into core `cvat-ui` component files.
3. **Infrastructure Overrides:** Use `docker-compose.override.yml` to append services, modify container networking, or change environment variables instead of altering the base `docker-compose.yml`.
4. **Minimal Footprint:** If a core file _must_ be changed, keep the diff to an absolute minimum (e.g., insert a single function call that points to an isolated custom module).

## Repository Map

Here are pointers to specific domains of the repo but feel free to check other parts if you cannot find something.

### Frontend & UI (React, TypeScript)

- `/cvat-ui/`: Main React frontend application, UI components, routing, and state management.
- `/cvat-core/`: Client-side JavaScript API wrapper for communicating with the backend.
- `/cvat-canvas/` & `/cvat-canvas3d/`: The 2D and 3D annotation workspace (canvas rendering, bounding box drawing, masking interaction).
- `/cvat-data/`: Client-side data management, caching, and payload decoding.

### Backend (Django, Python)

- `/cvat/apps/engine/`: Core backend logic, REST API endpoints, task/job management, and database models.
- `/cvat/apps/dataset_manager/`: Import and export logic for handling various annotation formats.
- `/cvat/settings/`: Django configuration and base environment settings.

### Machine Learning & Auto-Annotation (Nuclio)

- `/serverless/`: Nuclio serverless function definitions. Go here for adding or modifying automated annotation models (e.g., custom YOLO inference pipelines, SAM variants, or vision-language models). Create new isolated directories for new models rather than altering existing templates.
