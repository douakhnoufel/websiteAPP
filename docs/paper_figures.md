# PotatoScan Paper Figures

This file contains paper-ready source diagrams for the PotatoScan system. The figures are based on the current FastAPI, YOLO, stream, and drone bridge implementation in this repository.

## Figure 1. System Architecture

```mermaid
flowchart LR
    Client[User / Browser / Mobile Client]
    API[FastAPI Application]

    subgraph Presentation["Presentation Layer"]
        Template["templates/index.html"]
        Static["/static assets"]
        Results["/outputs annotated media"]
    end

    subgraph ApiLayer["API Layer"]
        Health["routers/health.py\n(GET /, /health, /models)"]
        Predict["routers/predict.py"]
        Stream["routers/stream.py"]
        Drone["routers/drone.py"]
    end

    subgraph Core["Core Services"]
        Config["core/config.py"]
        Models["services/model_manager.py"]
        Infer["services/inference.py"]
        Security["services/security.py"]
        DroneMgr["services/drone_manager.py"]
        Files["services/file_handler.py"]
    end

    subgraph Artifacts["Model and Runtime Artifacts"]
        ModelFile["models/potato.pt"]
        Uploads["uploads/"]
        Outputs["outputs/"]
    end

    subgraph External["External Systems"]
        MediaMTX["MediaMTX"]
        StreamSrc["RTMP / RTSP source"]
        DroneBridge["DJI bridge / telemetry producer"]
    end

    Client --> API
    API --> Static
    API --> Results
    Health --> Template

    API --> Health
    API --> Predict
    API --> Stream
    API --> Drone

    Health --> Models
    Predict --> Models
    Predict --> Infer
    Predict --> Files
    Stream --> Security
    Stream --> Infer
    Stream --> Models
    Drone --> Security
    Drone --> DroneMgr

    Models --> ModelFile
    Predict --> Uploads
    Predict --> Outputs

    Stream --> MediaMTX
    MediaMTX --> StreamSrc
    Drone --> DroneBridge

    API --> Config
    Predict --> Config
    Stream --> Config
    Drone --> Config
```

Caption: PotatoScan is organized as a FastAPI application with separate routers for health, prediction, streaming, and drone control. Model loading and inference are isolated in service modules, while annotated results are stored in `outputs/` and temporary uploads are stored in `uploads/`.

## Figure 2. Inference Workflow

```mermaid
sequenceDiagram
    participant U as Client
    participant A as FastAPI
    participant F as File Storage
    participant Y as YOLO Inference
    participant O as Output Storage

    U->>A: POST /predict/image
    A->>F: Save uploaded image
    A->>A: Validate file type and size
    A->>A: Decode image with OpenCV
    A->>Y: run_inference(image)
    Y-->>A: Prediction boxes and class scores
    A->>A: draw_inference()
    A->>O: Save annotated image
    A-->>U: JSON response with result_url

    U->>A: POST /predict/video
    A->>F: Save uploaded video
    A->>A: Sample frames
    A->>Y: run_inference(frame loop)
    A->>A: draw_inference() on frames
    A->>O: Save annotated video
    A-->>U: JSON response with summary metrics

    U->>A: POST /predict/frame
    A->>A: Decode frame bytes
    A->>A: Resize to FRAME_MAX_EDGE
    A->>Y: run_inference(frame)
    A->>A: Filter weak detections
    A-->>U: Prediction JSON
```

Caption: The inference pipeline supports image, video, and frame inputs. Uploaded media is processed in memory or from temporary files, passed through YOLO-based inference, and returned either as structured JSON or as annotated output files.

## Figure 3. Deployment Topology

```mermaid
flowchart TB
    Browser[Client Browser]

    subgraph Host["Host or VPS"]
        subgraph App["potatoescan container"]
            FastAPI["FastAPI on port 8000"]
            Template["templates/index.html"]
            Static["static/"]
            Models["models/"]
            Uploads["uploads/"]
            Outputs["outputs/"]
        end

        subgraph Stream["mediamtx container"]
            MTX["MediaMTX"]
            RTMP["Port 1935"]
            RTSP["Port 8554"]
            HTTP1["Port 8888"]
            HTTP2["Port 8889"]
        end
    end

    Browser -->|HTTP 8000| FastAPI
    FastAPI --> Template
    FastAPI --> Static
    FastAPI --> Models
    FastAPI --> Uploads
    FastAPI --> Outputs
    FastAPI -->|RTMP / RTSP ingest| MTX
    MTX --> RTMP
    MTX --> RTSP
    MTX --> HTTP1
    MTX --> HTTP2
```

Caption: PotatoScan is deployed as two cooperating containers. The FastAPI container serves the web UI and inference API, while MediaMTX provides the stream ingestion layer used for live RTMP/RTSP processing.

## Notes For Paper Export

- Use these Mermaid sources to export SVG or PNG figures for the paper.
- Keep the architecture figure for the system overview.
- Keep the sequence figure for the inference method section.
- Keep the deployment figure for the implementation or infrastructure section.
- If the journal does not accept Mermaid directly, export the diagrams before submission.
