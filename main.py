from fasthtml.common import (
    FastHTML,
    H2,
    H4,
    A,
    Span,
    P,
    Input,
    Form,
    Video,
    Div,
    Script,
    Html,
    Head,
    Meta,
    Body,
    Title,
    Thead,
    Tr,
    serve,
)
from monsterui.all import (
    Theme,
    DivCentered,
    DivVStacked,
    Card,
    CardHeader,
    CardBody,
    UkIcon,
    UkIconLink,
    Button,
    ButtonT,
    TextT,
    Container,
    Alert,
    AlertT,
    DivLAligned,
    Label,
    Progress,
    Table,
    TableT,
    Th,
    Tbody,
    Td,
)
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
from typing import List
import re

from components import BackButton
from auth import Auth, cli


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

# Create FastHTML app with MonsterUI
app = FastHTML(hdrs=(Theme.blue.headers()))
oauth = Auth(app=app, cli=cli)


@app.get("/favicon.ico")
def favicon():
    return RedirectResponse("/static/images/favicon.ico")


def login_form(req):
    return DivCentered(
        Card(
            CardHeader(
                DivCentered(
                    UkIcon(icon="audio-waveform", height=75, width=75),
                    H2("Demusicator", cls=TextT.lg),
                )
            ),
            CardBody(
                A(
                    Button(
                        Span(
                            UkIcon("chrome", cls="mr-2"),
                            "Login with Google",
                            cls="flex items-center justify-center",
                        ),
                        cls=(
                            ButtonT.primary,
                            TextT.medium,
                            "rounded-lg",
                        ),
                        submit=False,
                    ),
                    href=oauth.login_link(req),
                    cls="no-underline",
                ),
                cls="flex items-center justify-center max-w-md mx-auto p-8 rounded-lg shadow-md",
            ),
        ),
        cls="flex items-center justify-center min-h-screen",
    )


def unauthorized_form():
    return Container(
        Card(
            CardHeader(
                "Please logout and login with an authorized Google account.",
                cls="text-xl font-bold mb-4",
            ),
            CardBody(
                A(
                    Button(
                        "Logout",
                        cls=(ButtonT.primary, "rounded-lg"),
                        button=True,
                    ),
                    href="/auth/logout",
                ),
                cls="flex items-center justify-center max-w-md mx-auto p-8 rounded-lg shadow-md",
            ),
            cls="flex items-center justify-center min-h-screen",
        ),
    )


@app.get("/login")
def login(req):
    # Check for error parameter
    error = req.query_params.get("error")

    login_content = login_form(req)

    if error == "unauthorized":
        # Add unauthorized message above the login form
        unauthorized_alert = Alert(
            "❌ Unauthorized User",
            "Your email address is not authorized to access this application. Please contact the administrator.",
            cls=AlertT.error + " mb-4",
        )
        content = Div(unauthorized_alert, login_content)
    else:
        content = login_content

    return Title("Login"), content


@app.get("/auth/logout")
def logout(session):
    # Clear the session
    for key in list(session.keys()):
        session.pop(key)

    # Redirect to login page
    return RedirectResponse("/", status_code=302)


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
        result_path = process_video(video_file_path, dry_run=False)

        if result_path and os.path.exists(result_path):
            # Clean up the filename: use original name + _processed + extension
            original_filename = jobs[job_id]["original_filename"]
            base, ext = os.path.splitext(original_filename)
            clean_filename = f"{base}_processed{ext}"
            new_filepath = os.path.join(OUTPUT_DIR, clean_filename)

            # Move/rename the processed file to the clean filename
            shutil.move(result_path, new_filepath)

            update_job_status(
                job_id, JOB_STATUS_COMPLETE, progress=100, output_file=clean_filename
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


def nav_menu():
    return Div(
        DivLAligned(
            A("Home", href="/", cls="px-4 py-2 font-semibold"),
            A(
                "Processed Videos",
                href="/videos",
                cls="px-4 py-2 font-semibold",
            ),
            A(
                "Logout",
                href="/auth/logout",
                cls="px-4 py-2 font-semibold",
            ),
            cls="space-x-4",
        ),
        cls="w-full flex justify-center py-4 border-b mb-8 backdrop-blur",
    )


def create_layout(content):
    """App layout styled to match login_form: full-page centered, card with consistent styles, with nav menu."""
    return Div(
        nav_menu(),
        DivCentered(
            Card(
                CardHeader(
                    DivCentered(
                        UkIcon(icon="audio-waveform", height=75, width=75),
                        H2("Demusicator"),
                        H4("AI-Powered Video Music Removal"),
                    ),
                ),
                CardBody(
                    content,
                    cls="flex items-center justify-center max-w-md mx-auto rounded-lg",
                ),
            ),
            cls="flex items-center justify-center min-h-screen",
        ),
        cls="min-h-screen",
    )


@app.get("/")
def index():
    """Landing page with file upload form using MonsterUI components only, styled like login_form."""
    form = Form(
        DivVStacked(
            P("Upload a video file to get started"),
            Input(
                type="file",
                name="video_file",
                accept="video/*,.mp4,.avi,.mov,.mkv,.webm",
                required=True,
            ),
            P("📁 Supported: MP4, AVI, MOV, MKV, WebM"),
        ),
        Button(
            "Process Video",
            type="submit",
            cls=(ButtonT.primary, TextT.medium, "rounded-lg w-full mt-4"),
        ),
        method="post",
        action="/videos",
        enctype="multipart/form-data",
        cls="space-y-8",
    )
    return create_layout(form)


@app.post("/videos")
async def create_video_job(request: Request):
    """Create video processing job from uploaded file"""
    try:
        # Parse multipart form data
        form = await request.form()
        video_file = form.get("video_file")

        if not video_file or not hasattr(video_file, "filename"):
            return create_layout(
                Alert(
                    "❌ No File Selected - Please select a valid video file to upload.",
                    BackButton("/"),
                    cls=AlertT.error,
                )
            )

        # Validate file extension
        filename = video_file.filename
        allowed_extensions = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
        file_ext = os.path.splitext(filename)[1].lower()

        if file_ext not in allowed_extensions:
            return create_layout(
                Alert(
                    "❌ Invalid File Type",
                    f"File type '{file_ext}' is not supported. Please upload: {', '.join(allowed_extensions)}",
                    Button("/"),
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
        return RedirectResponse(url=f"/jobs/{job_id}", status_code=302)

    except Exception as e:
        logger.error(f"Error handling file upload: {str(e)}")
        logger.error(traceback.format_exc())
        return create_layout(
            Alert(
                "❌ Upload Error",
                f"Error processing upload: {str(e)}",
                Button("/"),
            )
        )


@app.get("/videos/{video_filename}")
def video_detail(video_filename: str):
    """Show video preview and download for a processed video by filename."""
    # Check if file exists in OUTPUT_DIR
    file_path = os.path.join(OUTPUT_DIR, video_filename)
    if not os.path.exists(file_path):
        return create_layout(
            Alert(
                "Video not found.",
                BackButton("/videos"),
            )
        )

    # Show video preview and download
    return create_layout(
        Card(
            CardHeader(H2("🎬 Video Preview")),
            CardBody(
                Video(
                    controls=True,
                    preload="metadata",
                    src=f"/videos/{video_filename}/stream",
                    cls="w-full max-w-lg mx-auto mb-4",
                ),
                Div(
                    A(
                        Button("⬇️ Download Video"),
                        href=f"/videos/{video_filename}/download",
                        download=True,
                    ),
                    Button(
                        "← Back to List",
                        hx_get="/videos",
                        hx_push_url="true",
                        hx_target="body",
                    ),
                    cls="flex gap-4 mt-4",
                ),
            ),
        )
    )


@app.get("/videos")
def videos_list():
    """Display a list of all processed videos with links to their detail pages."""
    videos = list_videos()
    if not videos:
        content = P("No processed videos found.")
    else:
        # Create table using MonsterUI components
        table = Table(
            Thead(
                Tr(
                    Th("Filename"),
                    Th("Size", cls="text-center"),
                    Th("Created", cls="text-center"),
                    Th("Actions", cls="text-center"),
                )
            ),
            Tbody(
                *[
                    Tr(
                        Td(
                            A(
                                video["display_name"],
                                href=f"/videos/{video['filename']}",
                                cls="text-blue-600 font-medium",
                            )
                        ),
                        Td(
                            f"{video['size_mb']:.1f} MB",
                            cls="text-center text-gray-600",
                        ),
                        Td(
                            video["created_date"],
                            cls="text-center text-gray-600",
                        ),
                        Td(
                            Div(
                                A(
                                    UkIcon("download", cls="w-5 h-5"),
                                    href=f"/videos/{video['filename']}/download",
                                    download=True,
                                    cls=(
                                        TextT.primary,
                                        "inline-flex items-center justify-center w-8 h-8",
                                    ),
                                    title="Download",
                                ),
                                UkIconLink(
                                    icon="x",
                                    button=True,
                                    hx_delete=f"/videos/{video['filename']}",
                                    hx_target="body",
                                    hx_confirm=f"Are you sure you want to delete '{video['display_name']}'?",
                                    cls=(
                                        TextT.error,
                                        "text-2xl hover:scale-125 hover:brightness-125",
                                    ),
                                    title="Delete",
                                ),
                                cls="flex items-center justify-center",
                            ),
                            cls="text-center",
                        ),
                    )
                    for video in videos
                ]
            ),
            cls=(
                TableT.hover,
                "w-full border border-gray-200 rounded-lg overflow-hidden",
            ),
        )
        content = table
    return create_layout(Div(H2("Processed Videos"), content, cls="space-y-4"))


def extract_display_name(filename):
    """Extract a user-friendly display name from a processed video filename."""
    # Remove leading UUID and trailing _processed_UUID if present
    # Example: 14df24c0-..._The Giant Pond Rat That Built America_processed_ba61c6a1-...mp4
    # Should become: The Giant Pond Rat That Built America
    name = filename
    # Remove leading UUID and underscore
    name = re.sub(r"^[0-9a-fA-F-]+_", "", name)
    # Remove trailing _processed_UUID
    name = re.sub(r"_processed_[0-9a-fA-F-]+", "", name)
    # Remove file extension
    name = re.sub(r"\.[^.]+$", "", name)
    return name


def list_videos():
    """Return a list of all processed videos in OUTPUT_DIR."""
    videos = []
    for fname in os.listdir(OUTPUT_DIR):
        if (
            fname.endswith((".mp4", ".avi", ".mov", ".mkv", ".webm"))
            and "_processed" in fname
        ):
            file_path = os.path.join(OUTPUT_DIR, fname)

            # Get file size in MB
            file_size_bytes = os.path.getsize(file_path)
            size_mb = file_size_bytes / (1024 * 1024)

            # Get creation date
            created_timestamp = os.path.getctime(file_path)
            created_date = time.strftime(
                "%Y-%m-%d %H:%M", time.localtime(created_timestamp)
            )

            base, ext = os.path.splitext(fname)
            display_name = base.replace("_processed", "")

            videos.append(
                {
                    "video_id": fname,
                    "filename": fname,
                    "display_name": display_name,
                    "size_mb": size_mb,
                    "created_date": created_date,
                }
            )
    return videos


@app.get("/videos/{video_filename}/download")
def download_video_by_id(video_filename: str):
    """Serve the processed video file for download by filename."""
    file_path = os.path.join(OUTPUT_DIR, video_filename)
    if os.path.exists(file_path):
        return FileResponse(
            path=file_path, media_type="video/mp4", filename=video_filename
        )
    return Response("File not found", status_code=404)


@app.get("/videos/{video_filename}/stream")
def stream_video_by_id(video_filename: str):
    """Serve the processed video file for streaming by filename."""
    file_path = os.path.join(OUTPUT_DIR, video_filename)
    if os.path.exists(file_path):
        return FileResponse(
            path=file_path,
            media_type="video/mp4",
            headers={"Cache-Control": "no-cache"},
        )
    return Response("File not found", status_code=404)


def get_video_status(job_id: str):
    """Get video processing status with polling"""
    if job_id not in jobs:
        return create_layout(
            Alert(
                "❌ Job Not Found",
                f"Job {job_id} not found.",
                BackButton("/"),
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
        # Show processing page with consistent styling and HTMX auto-refresh
        processing_content = Div(
            P(f"📄 Job ID: {job_id}"),
            P(f"📁 File: {job['original_filename']}"),
            Div(
                Progress(value=job["progress"], max=100),
                P(f"{job['progress']}% Complete"),
                cls="mt-4",
            ),
            # HTMX auto-refresh every 5 seconds
            hx_get=f"/jobs/{job_id}",
            hx_trigger="every 5s",
            hx_target="body",
            cls="space-y-4",
        )

        return create_layout(
            Card(
                CardHeader(H2("🔄 Processing Your Video")),
                CardBody(processing_content),
            )
        )

    elif status == JOB_STATUS_COMPLETE:
        # Redirect to video detail page using the clean filename
        output_file = job["output_file"]
        if output_file:
            return RedirectResponse(url=f"/videos/{output_file}", status_code=302)
        else:
            return create_layout(
                Alert(
                    "Processing finished, but output file not found.",
                    BackButton("/videos"),
                )
            )

    else:  # JOB_STATUS_ERROR
        error_content = Card(
            CardHeader(
                H2("❌ Processing Failed"),
                Label("Error"),
            ),
            CardBody(
                P("Sorry, we encountered an issue processing your video."),
                Div(
                    H4("Error Details:"),
                    P(job.get("error_message", "Unknown error occurred")),
                ),
                Div(
                    Button("🔄 Try Again", href="/"),
                    Button("📧 Report Issue", href="#"),
                ),
            ),
        )
        return create_layout(error_content)


@app.get("/jobs/{job_id}")
def job_status(job_id: str):
    """Check job status and redirect appropriately"""
    return get_video_status(job_id)


@app.delete("/videos/{video_filename}")
def delete_video(video_filename: str):
    """Delete a processed video file."""
    file_path = os.path.join(OUTPUT_DIR, video_filename)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            logger.info(f"Deleted video file: {file_path}")
            # Return the updated videos list page
            return videos_list()
        except Exception as e:
            logger.error(f"Error deleting video {video_filename}: {str(e)}")
            return create_layout(
                Alert(
                    "❌ Delete Error",
                    f"Failed to delete video: {str(e)}",
                    BackButton("/videos"),
                    cls=AlertT.error,
                )
            )
    else:
        return create_layout(
            Alert(
                "❌ Video Not Found",
                f"Video file '{video_filename}' not found.",
                BackButton("/videos"),
                cls=AlertT.error,
            )
        )


serve()
