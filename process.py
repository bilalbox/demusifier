import os
import re
import replicate
import subprocess
import time
import uuid
from pathlib import Path


from config import (
    BASE_DIR,
    INPUT_DIR,
    OUTPUT_DIR,
    WORKING_DIR,
    REPLICATE_API_TOKEN,
    REPLICATE_MODEL,
    setup_logger,
)

logger = setup_logger(__name__)


def setup_directories():
    """Create necessary directories if they don't exist"""
    for dir in [BASE_DIR, INPUT_DIR, OUTPUT_DIR]:
        os.makedirs(dir, exist_ok=True)


def sanitize_filename(name):
    """Sanitize filename by removing special characters"""
    # First replace spaces with underscores
    name = re.sub(r"\s+", "_", name)
    # Then replace any remaining special characters with underscores
    name = re.sub(r"[^a-zA-Z0-9_.]", "_", name)
    # Remove multiple consecutive underscores
    name = re.sub(r"_+", "_", name)
    # Remove leading/trailing underscores
    return name.strip("_")


def split_video_streams(video_path: str, working_dir: str) -> tuple[str, str]:
    """Split video file into separate audio and video streams."""
    video_name = Path(video_path).stem
    audio_path = os.path.join(working_dir, f"{video_name}_audio.mp3")
    video_only_path = os.path.join(working_dir, f"{video_name}_video.mp4")

    try:
        # Extract audio stream
        subprocess.run(
            [
                "ffmpeg",
                "-i",
                video_path,
                "-vn",
                "-acodec",
                "mp3",
                "-ab",
                "320k",
                "-y",
                audio_path,
            ],
            check=True,
            capture_output=True,
        )
        logger.info(f"Audio extracted to {audio_path}")

        # Extract video stream (without audio)
        subprocess.run(
            [
                "ffmpeg",
                "-i",
                video_path,
                "-an",
                "-vcodec",
                "copy",
                "-y",
                video_only_path,
            ],
            check=True,
            capture_output=True,
        )
        logger.info(f"Video stream extracted to {video_only_path}")

        return audio_path, video_only_path

    except subprocess.CalledProcessError as e:
        logger.error(f"Error splitting video streams: {e.stderr.decode()}")
        raise


def speed_up_audio(audio_path: str, speed_factor: float = 2.0) -> str:
    """Speed up audio by the specified factor using ffmpeg."""
    audio_name = Path(audio_path).stem
    working_dir = os.path.dirname(audio_path)
    sped_up_path = os.path.join(working_dir, f"{audio_name}_sped_{speed_factor}x.mp3")

    try:
        subprocess.run(
            [
                "ffmpeg",
                "-i",
                audio_path,
                "-filter:a",
                f"atempo={speed_factor}",
                "-y",
                sped_up_path,
            ],
            check=True,
            capture_output=True,
        )
        logger.info(f"Audio sped up to {speed_factor}x: {sped_up_path}")
        return sped_up_path

    except subprocess.CalledProcessError as e:
        logger.error(f"Error speeding up audio: {e.stderr.decode()}")
        raise


def isolate_vocals_with_replicate(audio_path: str) -> str:
    """Isolate vocals from audio file using Replicate API."""
    if not REPLICATE_API_TOKEN:
        raise ValueError("REPLICATE_API_TOKEN not found in environment variables")

    # Create a custom Replicate client with longer timeout (10 minutes)
    client = replicate.Client(
        api_token=REPLICATE_API_TOKEN,
        timeout=600,  # 10 minutes timeout
    )

    working_dir = os.path.dirname(audio_path)
    audio_name = Path(audio_path).stem
    vocals_path = os.path.join(working_dir, f"{audio_name}_vocals.mp3")

    try:
        logger.info("Calling Replicate API to isolate vocals...")
        start_time = time.monotonic()

        # Open the audio file for Replicate API
        with open(audio_path, "rb") as audio_file:
            output = client.run(
                REPLICATE_MODEL,
                input={
                    "audio": audio_file,
                    "stem": "vocals",  # We want vocals only
                },
            )

        end_time = time.monotonic()
        duration = end_time - start_time
        logger.info(f"Replicate API processing completed in {duration:.2f} seconds!")

        # Handle the output - it should be a FileOutput object
        if hasattr(output, "read"):
            # Single file output
            with open(vocals_path, "wb") as f:
                f.write(output.read())
        elif isinstance(output, dict) and "vocals" in output:
            # Dictionary output with vocals key
            vocals_output = output["vocals"]
            with open(vocals_path, "wb") as f:
                f.write(vocals_output.read())
        elif isinstance(output, list) and len(output) > 0:
            # List output, take the first file
            with open(vocals_path, "wb") as f:
                f.write(output[0].read())
        else:
            raise Exception(
                f"Unexpected output format from Replicate API: {type(output)}"
            )

        logger.info(f"Vocals isolated and saved to: {vocals_path}")
        return vocals_path

    except Exception as e:
        logger.error(f"Error calling Replicate API: {str(e)}")
        raise


def slow_down_audio(audio_path: str, speed_factor: float = 0.5) -> str:
    """Slow down audio by the specified factor using ffmpeg."""
    audio_name = Path(audio_path).stem
    working_dir = os.path.dirname(audio_path)
    slowed_path = os.path.join(
        working_dir, f"{audio_name}_slowed_{1 / speed_factor}x.mp3"
    )

    try:
        subprocess.run(
            [
                "ffmpeg",
                "-i",
                audio_path,
                "-filter:a",
                f"atempo={speed_factor}",
                "-y",
                slowed_path,
            ],
            check=True,
            capture_output=True,
        )
        logger.info(f"Audio slowed down by {speed_factor}: {slowed_path}")
        return slowed_path

    except subprocess.CalledProcessError as e:
        logger.error(f"Error slowing down audio: {e.stderr.decode()}")
        raise


def merge_audio_video_streams(
    video_path: str, audio_path: str, output_path: str
) -> str:
    """Merge audio and video streams using ffmpeg's streamcopy feature."""
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-i",
                video_path,
                "-i",
                audio_path,
                "-c:v",
                "copy",  # Copy video stream without re-encoding
                "-c:a",
                "aac",  # Re-encode audio to AAC
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-shortest",  # End when shortest stream ends
                "-y",
                output_path,
            ],
            check=True,
            capture_output=True,
        )
        logger.info(f"Audio and video merged successfully: {output_path}")
        return output_path

    except subprocess.CalledProcessError as e:
        logger.error(f"Error merging audio and video: {e.stderr.decode()}")
        raise


def process_video(video_file: str, dry_run: bool = False, cleanup: bool = True) -> str:
    """
    Main function to process the video with optional dry run mode.

    Args:
        video_file: Path to the input video file
        dry_run: If True, skip Replicate API call for vocal isolation
        cleanup: If True, clean up input and working directories after processing

    Returns:
        Path to the processed video file
    """
    working_dir = None
    try:
        # Create unique working directory for this job
        job_id = str(uuid.uuid4())
        working_dir = os.path.join(WORKING_DIR, f"job_{job_id}")
        os.makedirs(working_dir, exist_ok=True)
        logger.info(f"Created working directory: {working_dir}")

        # Generate output path
        video_name = Path(video_file).stem
        output_filename = f"{video_name}_processed_{job_id}.mp4"
        output_path = os.path.join(OUTPUT_DIR, output_filename)

        logger.info(f"Processing video: {video_file}")
        logger.info(f"Dry run mode: {dry_run}")

        # Step 1: Split video into audio and video streams
        logger.info("Step 1: Splitting video into audio and video streams...")
        audio_path, video_only_path = split_video_streams(video_file, working_dir)

        # Step 2: Process audio with Replicate API (or skip if dry_run)
        if not dry_run:
            logger.info("Step 2: Isolating vocals using Replicate API...")
            vocals_path = isolate_vocals_with_replicate(audio_path)
        else:
            logger.info("Step 2: Skipping vocal isolation (dry run mode)")
            vocals_path = audio_path

        # Step 3: Merge audio and video using streamcopy
        logger.info("Step 3: Merging audio and video streams...")
        final_video_path = merge_audio_video_streams(
            video_only_path, vocals_path, output_path
        )

        logger.info(f"Processing complete. Output saved to: {final_video_path}")

        # Cleanup if requested
        if cleanup:
            logger.info("Cleaning up temporary files...")
            cleanup_directories(working_dir=working_dir, input_file=video_file)

        return final_video_path

    except Exception as e:
        logger.error(f"Error processing video: {str(e)}")
        # Clean up on error if cleanup is enabled
        if cleanup and working_dir:
            cleanup_directories(working_dir=working_dir)
        raise


def cleanup_directories(working_dir: str = None, input_file: str = None):
    """Clean up files from input and working directories after processing."""
    try:
        # Clean up working directory
        if working_dir and os.path.exists(working_dir):
            import shutil

            shutil.rmtree(working_dir)
            logger.info(f"Cleaned up working directory: {working_dir}")

        # Clean up input file if specified
        if input_file and os.path.exists(input_file):
            os.remove(input_file)
            logger.info(f"Cleaned up input file: {input_file}")

    except Exception as e:
        logger.warning(f"Error during cleanup: {str(e)}")
