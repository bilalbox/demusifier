import os
import sys
import re
import subprocess
import requests
import uuid
import shutil
from pathlib import Path

from config import (
    BASE_DIR,
    INPUT_DIR,
    OUTPUT_DIR,
    WORKING_DIR,
    RUNPOD_API_KEY,
    RUNPOD_ENDPOINT,
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


def call_runpod_api(audio_path: str) -> str:
    """Call RunPod API to isolate vocals from audio file."""
    if not RUNPOD_API_KEY:
        raise ValueError("RUNPOD_API_KEY not found in environment variables")

    # Upload audio file and get the vocals back
    # For now, we'll simulate this by returning the input path
    # In a real implementation, you'd upload the file and process it
    working_dir = os.path.dirname(audio_path)
    audio_name = Path(audio_path).stem
    vocals_path = os.path.join(working_dir, f"{audio_name}_vocals.mp3")

    try:
        # Prepare the API call payload
        payload = {
            "input": {
                "jobs": 0,
                "stem": "vocals",  # We want vocals only
                "audio": os.path.basename(audio_path),
                "model": "htdemucs",
                "split": True,
                "shifts": 1,
                "overlap": 0.25,
                "clip_mode": "rescale",
                "mp3_preset": 2,
                "wav_format": "int24",
                "mp3_bitrate": 320,
                "output_format": "mp3",
            }
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {RUNPOD_API_KEY}",
        }

        # Make API call
        response = requests.post(RUNPOD_ENDPOINT, headers=headers, json=payload)

        if response.status_code != 200:
            raise Exception(
                f"RunPod API call failed: {response.status_code} - {response.text}"
            )

        result = response.json()
        logger.info(f"RunPod API call successful: {result}")

        # Poll for completion and download result
        # This is a simplified version - in reality you'd need to:
        # 1. Upload the audio file to RunPod
        # 2. Poll the job status until complete
        # 3. Download the processed vocals file

        # For now, copy the original file as a placeholder
        shutil.copy2(audio_path, vocals_path)
        logger.info(f"Vocals isolated (placeholder): {vocals_path}")

        return vocals_path

    except Exception as e:
        logger.error(f"Error calling RunPod API: {str(e)}")
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


def process_video(video_file: str, dry_run: bool = True) -> str:
    """
    Main function to process the video with optional dry run mode.

    Args:
        video_file: Path to the input video file
        dry_run: If True, skip RunPod API call for vocal isolation

    Returns:
        Path to the processed video file
    """
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

        # Step 2: Speed up audio to 2x
        logger.info("Step 2: Speeding up audio to 2x...")
        # sped_audio_path = speed_up_audio(audio_path, speed_factor=2.0)

        # Step 3: Process audio (RunPod API call or skip if dry_run)
        if not dry_run:
            logger.info("Step 3: Calling RunPod API to isolate vocals...")
            # vocals_path = call_runpod_api(sped_audio_path)
            vocals_path = call_runpod_api(audio_path)
        else:
            logger.info("Step 3: Skipping RunPod API call (dry run mode)")
            # vocals_path = sped_audio_path
            vocals_path = audio_path

        # Step 4: Slow audio back down to 1x
        logger.info("Step 4: Slowing audio back down to 1x...")
        # final_audio_path = slow_down_audio(vocals_path, speed_factor=0.5)
        final_audio_path = vocals_path

        # Step 5: Merge audio and video using streamcopy
        logger.info("Step 5: Merging audio and video streams...")
        final_video_path = merge_audio_video_streams(
            video_only_path, final_audio_path, output_path
        )

        # Cleanup intermediate files (optional)
        # You might want to keep them for debugging
        logger.info(f"Processing complete. Output saved to: {final_video_path}")

        return final_video_path

    except Exception as e:
        logger.error(f"Error processing video: {str(e)}")
        raise
