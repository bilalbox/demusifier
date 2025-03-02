import os
import subprocess
import shutil
import librosa
import soundfile as sf
import torch
import uuid

# Define directory structure
BASE_DIR = 'videos'
INPUT_DIR = os.path.join(BASE_DIR, 'input')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
WORKING_DIR = os.path.join(BASE_DIR, 'working')

# Ensure directories exist
for dir_path in [INPUT_DIR, OUTPUT_DIR, WORKING_DIR]:
    os.makedirs(dir_path, exist_ok=True)

def get_input_video():
    """Finds the first MP4 video in the input directory."""
    for root, _, files in os.walk(INPUT_DIR):
        for file in files:
            if file.endswith('.mp4'):
                return os.path.join(root, file)
    return None

def extract_audio(video_path, output_path):
    """Extracts audio from a video file using ffmpeg."""
    try:
        subprocess.run([
            'ffmpeg', '-i', video_path, 
            '-vn', '-ac', '2', 
            '-ar', '44100', 
            '-ab', '320k', 
            '-y', output_path
        ], check=True, capture_output=True)
        print("✓ Audio extracted successfully")
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"❌ Error extracting audio: {e.stderr.decode()}")
        return None

def isolate_vocals(audio_path, demucs_output_root):
    """Isolates vocals using Demucs, explicitly using GPU if available."""
    try:
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"🔧 Using {device} for Demucs")

        subprocess.run([
            'python', '-m', 'demucs.separate',
            '-n', 'htdemucs',
            '--out', demucs_output_root,
            audio_path,
            '--device', device
        ], check=True, capture_output=True)

        base_name = os.path.splitext(os.path.basename(audio_path))[0]
        vocals_path = os.path.join(demucs_output_root, "htdemucs", base_name, "vocals.wav")

        if not os.path.exists(vocals_path):
            print(f"❌ Vocals file not found at {vocals_path}")
            return None

        print("✓ Vocals isolated successfully")
        return vocals_path
    except subprocess.CalledProcessError as e:
        print(f"❌ Error isolating vocals: {e.stderr.decode()}")
        return None

def merge_audio_video(video_path, audio_path, output_path):
    """Merges isolated vocals with original video using FFmpeg."""
    try:
        gpu_available = torch.cuda.is_available()
        encoder = 'h264_nvenc' if gpu_available else 'libx264'
        print(f"🔧 Using {encoder} for encoding")

        subprocess.run([
            'ffmpeg', '-y',
            '-i', video_path,
            '-i', audio_path,
            '-map', '0:v',
            '-map', '1:a',
            '-c:v', encoder,
            '-c:a', 'aac',
            '-b:v', '5M',
            '-shortest',
            output_path
        ], check=True, capture_output=True)
        
        print("✓ Audio and video merged successfully")
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg error: {e.stderr.decode()}")
        return None

def process_video(input_video_path, output_video_path):
    """Process video with intermediate files stored in working directory."""
    unique_id = str(uuid.uuid4())
    extracted_audio_path = os.path.join(WORKING_DIR, f"extracted_audio_{unique_id}.wav")
    demucs_output_dir = os.path.join(WORKING_DIR, f"demucs_{unique_id}")
    base_name = os.path.splitext(os.path.basename(extracted_audio_path))[0]
    vocals_audio_path = os.path.join(demucs_output_dir, "htdemucs", base_name, "vocals.wav")

    try:
        # Extract audio
        if not extract_audio(input_video_path, extracted_audio_path):
            return False

        # Validate audio
        try:
            y, sr = librosa.load(extracted_audio_path)
            sf.write(extracted_audio_path, y, sr)
            print("✓ Audio file validated")
        except Exception as e:
            print(f"❌ Error validating audio: {e}")
            return False

        # Process vocals
        if not isolate_vocals(extracted_audio_path, demucs_output_dir):
            print("❌ Failed to isolate vocals")
            return False

        # Merge back with video
        if not merge_audio_video(input_video_path, vocals_audio_path, output_video_path):
            print("❌ Failed to merge audio and video")
            return False

        print("✨ Video processing completed successfully")
        return True

    except Exception as e:
        print(f"❌ Unexpected error during processing: {str(e)}")
        return False
    
    finally:
        # Clean up working files
        if os.path.exists(extracted_audio_path):
            os.remove(extracted_audio_path)
        if os.path.exists(demucs_output_dir):
            shutil.rmtree(demucs_output_dir, ignore_errors=True)

if __name__ == "__main__":
    print("\n🔍 Checking CUDA availability...")
    print("✓ CUDA is available!" if torch.cuda.is_available() else "! CUDA is NOT available (processing will be slower)")

    input_video_path = get_input_video()
    if not input_video_path:
        print("❌ No MP4 files found in input directory")
        exit(1)

    video_name = os.path.splitext(os.path.basename(input_video_path))[0]
    output_path = os.path.join(OUTPUT_DIR, f"{video_name}_nomusic.mp4")

    print(f"\n🎥 Processing: {input_video_path}")
    if process_video(input_video_path, output_path):
        print(f"✨ Successfully processed: {output_path}")
        exit(0)
    else:
        print(f"❌ Failed to process: {input_video_path}")
        exit(1)