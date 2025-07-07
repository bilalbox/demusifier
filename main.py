from fasthtml.common import *
from starlette.responses import RedirectResponse, FileResponse, Response
from starlette.requests import Request
import asyncio
import os
import uuid
import threading
import time
import shutil
from process import process_video
from config import INPUT_DIR, OUTPUT_DIR, setup_logger
import traceback
import json

# Set up logging
logger = setup_logger(__name__)

# Simple in-memory job tracking
jobs = {}

# Job statuses
JOB_STATUS_PENDING = "pending"
JOB_STATUS_DOWNLOADING = "downloading"
JOB_STATUS_PROCESSING = "processing"
JOB_STATUS_COMPLETE = "complete"
JOB_STATUS_ERROR = "error"

# Create FastHTML app with PicoCSS
app, rt = fast_app(
    pico=True,  # Enable PicoCSS with default styles
)


def create_job(video_file_path, original_filename):
    """Create a new job and return job ID"""
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "id": job_id,
        "video_file_path": video_file_path,
        "original_filename": original_filename,
        "status": JOB_STATUS_PENDING,
        "created_at": time.time(),
        "updated_at": time.time(),
        "error_message": None,
        "output_file": None,
        "progress": 0,
    }

    # Create placeholder file
    placeholder_path = os.path.join(OUTPUT_DIR, f"{job_id}_placeholder.txt")
    with open(placeholder_path, "w") as f:
        f.write(
            f"Processing video: {original_filename}\nJob ID: {job_id}\nStatus: {JOB_STATUS_PENDING}"
        )

    return job_id


def update_job_status(
    job_id, status, progress=None, error_message=None, output_file=None
):
    """Update job status"""
    if job_id in jobs:
        jobs[job_id]["status"] = status
        jobs[job_id]["updated_at"] = time.time()
        if progress is not None:
            jobs[job_id]["progress"] = progress
        if error_message:
            jobs[job_id]["error_message"] = error_message
        if output_file:
            jobs[job_id]["output_file"] = output_file
            # Remove placeholder when complete
            placeholder_path = os.path.join(OUTPUT_DIR, f"{job_id}_placeholder.txt")
            if os.path.exists(placeholder_path):
                os.remove(placeholder_path)


def process_video_async(job_id, video_file_path):
    """Process video in background thread"""
    try:
        update_job_status(job_id, JOB_STATUS_PROCESSING, progress=25)
        logger.info(
            f"Starting video processing for job {job_id} with file {video_file_path}"
        )

        update_job_status(job_id, JOB_STATUS_PROCESSING, progress=50)
        result_path = process_video(video_file_path, dry_run=True)

        if result_path and os.path.exists(result_path):
            # Rename the file to include job_id for tracking
            original_filename = os.path.basename(result_path)
            new_filename = f"{job_id}_{original_filename}"
            new_filepath = os.path.join(OUTPUT_DIR, new_filename)

            # Rename the file if it's not already named with job_id
            if result_path != new_filepath:
                shutil.move(result_path, new_filepath)

            update_job_status(
                job_id, JOB_STATUS_COMPLETE, progress=100, output_file=new_filename
            )
            logger.info(f"Job {job_id} completed successfully. Output: {new_filepath}")
        else:
            update_job_status(
                job_id,
                JOB_STATUS_ERROR,
                progress=100,
                error_message="Video processing failed or no output file generated",
            )

    except Exception as e:
        logger.error(f"Error processing job {job_id}: {str(e)}")
        logger.error(traceback.format_exc())
        update_job_status(job_id, JOB_STATUS_ERROR, progress=100, error_message=str(e))


def create_layout(content):
    """Create consistent layout with header and navigation"""
    return Html(
        Head(
            Title("Demusifier - AI Video Music Separation"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
        ),
        Body(
            Main(
                Container(
                    Header(
                        H1(
                            "🎵 Demusifier",
                            style="text-align: center; margin-bottom: 1rem;",
                        ),
                        P(
                            "Separate music from video using AI",
                            style="text-align: center; color: var(--muted-color); margin-bottom: 2rem;",
                        ),
                    ),
                    content,
                    style="max-width: 800px; margin: 0 auto; padding: 2rem;",
                )
            )
        ),
    )


@rt("/")
def get():
    """Landing page with file upload form"""
    form = Form(
        Fieldset(
            Legend("Process Video"),
            Label(
                "Upload Video File:",
                Input(
                    type="file",
                    name="video_file",
                    accept="video/*,.mp4,.avi,.mov,.mkv,.webm",
                    required=True,
                    style="margin-top: 0.5rem;",
                ),
            ),
            P(
                "Supported formats: MP4, AVI, MOV, MKV, WebM",
                style="font-size: 0.8rem; color: var(--muted-color); margin-top: 0.25rem;",
            ),
            Button(
                "🚀 Process Video",
                type="submit",
                style="margin-top: 1rem; width: 100%;",
            ),
        ),
        method="post",
        action="/videos",
        enctype="multipart/form-data",
        style="margin-bottom: 2rem;",
    )

    info_section = Article(
        Header(H3("How it works")),
        Ol(
            Li("Upload a video file from your device"),
            Li("Our AI will process the video"),
            Li("Music will be separated from the original audio"),
            Li("Download your processed video"),
        ),
        Footer(
            Small(
                "⚡ Powered by RunPod AI • 🤖 Demucs AI Model",
                style="color: var(--muted-color);",
            )
        ),
    )

    content = Div(form, info_section)
    return create_layout(content)


@rt("/videos", methods=["POST"])
async def create_video_job(request: Request):
    """Create video processing job from uploaded file"""
    try:
        # Parse multipart form data
        form = await request.form()
        video_file = form.get("video_file")

        if not video_file or not hasattr(video_file, "filename"):
            return create_layout(
                Article(
                    Header(H2("❌ Error")),
                    P("Please upload a valid video file."),
                    A("← Go back", href="/", role="button", style="margin-top: 1rem;"),
                )
            )

        # Validate file extension
        filename = video_file.filename
        allowed_extensions = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
        file_ext = os.path.splitext(filename)[1].lower()

        if file_ext not in allowed_extensions:
            return create_layout(
                Article(
                    Header(H2("❌ Invalid File Type")),
                    P(
                        f"File type '{file_ext}' is not supported. Please upload: {', '.join(allowed_extensions)}"
                    ),
                    A("← Go back", href="/", role="button", style="margin-top: 1rem;"),
                )
            )

        # Generate unique filename and save to INPUT_DIR
        job_id = str(uuid.uuid4())
        safe_filename = f"{job_id}_{filename}"
        file_path = os.path.join(INPUT_DIR, safe_filename)

        # Save uploaded file
        with open(file_path, "wb") as f:
            content = await video_file.read()
            f.write(content)

        logger.info(f"File uploaded successfully: {file_path} ({len(content)} bytes)")

        # Create job
        job_id = create_job(file_path, filename)

        # Start processing in background thread
        thread = threading.Thread(target=process_video_async, args=(job_id, file_path))
        thread.daemon = True
        thread.start()

        # Return 302 redirect to job status page
        return RedirectResponse(url=f"/videos/{job_id}", status_code=302)

    except Exception as e:
        logger.error(f"Error handling file upload: {str(e)}")
        logger.error(traceback.format_exc())
        return create_layout(
            Article(
                Header(H2("❌ Upload Error")),
                P(f"Error processing upload: {str(e)}"),
                A("← Go back", href="/", role="button", style="margin-top: 1rem;"),
            )
        )


@rt("/videos/{job_id}")
def get_video_status(job_id: str):
    """Get video processing status with polling"""
    if job_id not in jobs:
        return create_layout(
            Article(
                Header(H2("❌ Job Not Found")),
                P(f"Job {job_id} not found."),
                A("← Go back", href="/", role="button", style="margin-top: 1rem;"),
            )
        )

    job = jobs[job_id]
    status = job["status"]

    # Check if placeholder exists (still processing)
    placeholder_path = os.path.join(OUTPUT_DIR, f"{job_id}_placeholder.txt")
    is_processing = os.path.exists(placeholder_path)

    if (
        status in [JOB_STATUS_PENDING, JOB_STATUS_DOWNLOADING, JOB_STATUS_PROCESSING]
        or is_processing
    ):
        # Show processing page with auto-refresh
        processing_content = Article(
            Header(H2("🔄 Processing Video")),
            P(f"Job ID: {job_id}"),
            P(f"File: {job['original_filename']}"),
            P(f"Status: {status.title()}"),
            Progress(value=job["progress"], max=100, style="margin: 1rem 0;"),
            P(f"Progress: {job['progress']}%"),
            P("Steps:", style="margin-top: 1rem;"),
            Ol(
                Li(
                    "Processing uploaded video file",
                    style="color: green;" if job["progress"] > 10 else "",
                ),
                Li(
                    "Splitting audio and video streams",
                    style="color: green;" if job["progress"] > 30 else "",
                ),
                Li(
                    "Running AI music separation",
                    style="color: green;" if job["progress"] > 50 else "",
                ),
                Li(
                    "Preparing download",
                    style="color: green;" if job["progress"] > 90 else "",
                ),
            ),
            Details(
                Summary("Technical Details"),
                P(
                    "We use the Demucs AI model running on RunPod's cloud infrastructure to separate music from video audio tracks."
                ),
            ),
            # Auto-refresh via script
            Script("""
                setTimeout(function() {
                    window.location.reload();
                }, 3000);
            """),
        )

        # Add meta refresh as well
        return Html(
            Head(
                Title("Demusifier - Processing Video"),
                Meta(name="viewport", content="width=device-width, initial-scale=1"),
                Meta(httpEquiv="refresh", content="3"),
            ),
            Body(
                Main(
                    Container(
                        Header(
                            H1(
                                "🎵 Demusifier",
                                style="text-align: center; margin-bottom: 1rem;",
                            ),
                            P(
                                "Separate music from video using AI",
                                style="text-align: center; color: var(--muted-color); margin-bottom: 2rem;",
                            ),
                        ),
                        processing_content,
                        style="max-width: 800px; margin: 0 auto; padding: 2rem;",
                    )
                )
            ),
        )

    elif status == JOB_STATUS_COMPLETE:
        # Show success page with video player
        output_file = job["output_file"]
        if output_file and os.path.exists(os.path.join(OUTPUT_DIR, output_file)):
            success_content = Article(
                Header(H2("✅ Processing Complete!")),
                P("Your video has been processed successfully."),
                P(f"Processed file: {output_file}"),
                # Embedded Video Player
                Div(
                    H3("🎬 Processed Video"),
                    Video(
                        controls=True,
                        style="width: 100%; max-width: 800px; height: auto; border-radius: 0.5rem;",
                        preload="metadata",
                        src=f"/videos/{job_id}/stream",
                    ),
                    P("Video processing completed with AI music separation."),
                    style="margin: 2rem 0; padding: 1rem; border: 1px solid var(--muted-border-color); border-radius: 0.5rem; text-align: center;",
                ),
                # Download button
                Div(
                    A(
                        "⬇️ Download Video",
                        href=f"/videos/{job_id}/download",
                        role="button",
                        style="margin-right: 1rem;",
                        download=output_file,
                    ),
                    A(
                        "← Process Another Video",
                        href="/",
                        role="button",
                        style="margin-top: 1rem;",
                    ),
                    style="display: flex; flex-wrap: wrap; gap: 1rem; justify-content: center; margin-top: 2rem;",
                ),
            )
        else:
            success_content = Article(
                Header(H2("⚠️ Processing Complete")),
                P("Processing finished, but output file not found."),
                A("← Go back", href="/", role="button", style="margin-top: 1rem;"),
            )

        return create_layout(success_content)

    else:  # JOB_STATUS_ERROR
        error_content = Article(
            Header(H2("❌ Processing Failed")),
            P(f"Error: {job.get('error_message', 'Unknown error')}"),
            Details(
                Summary("Job Details"),
                P(f"Job ID: {job_id}"),
                P(f"File: {job.get('original_filename', 'Unknown')}"),
                P(f"Created: {time.ctime(job['created_at'])}"),
            ),
            A("← Try Again", href="/", role="button", style="margin-top: 1rem;"),
        )
        return create_layout(error_content)


@rt("/videos/{job_id}/download")
def download_video(job_id: str):
    """Serve the processed video file for download or streaming"""
    if job_id not in jobs:
        return Response("Job not found", status_code=404)

    job = jobs[job_id]
    if job["status"] != JOB_STATUS_COMPLETE or not job["output_file"]:
        return Response("Video not ready", status_code=404)

    file_path = os.path.join(OUTPUT_DIR, job["output_file"])
    if not os.path.exists(file_path):
        return Response("File not found", status_code=404)

    return FileResponse(
        path=file_path, media_type="video/mp4", filename=job["output_file"]
    )


@rt("/videos/{job_id}/stream")
def stream_video(job_id: str):
    """Serve the processed video file for streaming/embedding"""
    if job_id not in jobs:
        return Response("Job not found", status_code=404)

    job = jobs[job_id]
    if job["status"] != JOB_STATUS_COMPLETE or not job["output_file"]:
        return Response("Video not ready", status_code=404)

    file_path = os.path.join(OUTPUT_DIR, job["output_file"])
    if not os.path.exists(file_path):
        return Response("File not found", status_code=404)

    return FileResponse(
        path=file_path, media_type="video/mp4", headers={"Cache-Control": "no-cache"}
    )


@rt("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "demusifier"}


if __name__ == "__main__":
    # Check for required environment variables
    required_env_vars = [
        "RUNPOD_API_KEY",
    ]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]

    if missing_vars:
        logger.error(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )
        print(
            f"Please set the following environment variables: {', '.join(missing_vars)}"
        )
        exit(1)

    logger.info("Starting Demusifier FastHTML app...")
    serve()
