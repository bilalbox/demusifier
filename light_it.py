import os
import sys
import yt_dlp
from lightning_sdk import Studio, Machine, Status, Teamspace
from dotenv import load_dotenv
import time
import re

# Load environment variables
load_dotenv()

# Constants
VIDEO_DIR = "videos"
INPUT_DIR = os.path.join(VIDEO_DIR, "input")
OUTPUT_DIR = os.path.join(VIDEO_DIR, "output")

if not os.getenv("LIGHTNING_API_KEY"):
    print("Error: LIGHTNING_API_KEY not found in environment variables")
    sys.exit(1)

def setup_directories():
    """Create necessary directories if they don't exist"""
    for dir in [VIDEO_DIR, INPUT_DIR, OUTPUT_DIR]:
        os.makedirs(dir, exist_ok=True)

def sanitize_filename(name):
    """Sanitize filename by removing special characters"""
    # First replace spaces with underscores
    name = re.sub(r'\s+', '_', name)
    # Then replace any remaining special characters with underscores
    name = re.sub(r'[^a-zA-Z0-9_.]', '_', name)
    # Remove multiple consecutive underscores
    name = re.sub(r'_+', '_', name)
    # Remove leading/trailing underscores
    return name.strip('_')

def download_youtube_video(url):
    """Download YouTube video using yt-dlp with progress tracking"""
    setup_directories()
    
    ydl_opts = {
        'format': 'best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best',
        'outtmpl': f'{INPUT_DIR}/%(title)s.%(ext)s',
        'merge_output_format': 'mp4',
        'retries': 10,
        'fragment_retries': 10,
        'ignoreerrors': False,
        'progress_hooks': [lambda d: print(f"Downloading: {d['_percent_str']} of {d['_total_bytes_str']}")],
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                # Get video info first
                info = ydl.extract_info(url, download=False)
                if info is None:
                    raise Exception("Could not retrieve video information")
                
                # Sanitize the filename before download
                sanitized_title = sanitize_filename(info['title'])
                ydl_opts['outtmpl'] = f'{INPUT_DIR}/{sanitized_title}.%(ext)s'
                
                # Download with sanitized filename
                with yt_dlp.YoutubeDL(ydl_opts) as ydl2:
                    info = ydl2.extract_info(url, download=True)
                
                # Get the downloaded file path
                original_video_path = os.path.join(INPUT_DIR, f"{sanitized_title}.mp4")
                
                # Rename to original_video.mp4
                new_video_path = os.path.join(INPUT_DIR, "original_video.mp4")
                if os.path.exists(new_video_path):
                    os.remove(new_video_path)
                os.rename(original_video_path, new_video_path)
                return new_video_path, "original_video"
                
            except Exception as e:
                print(f"Error during download: {str(e)}")
                raise
    except Exception as e:
        print(f"Error downloading video: {str(e)}")
        sys.exit(1)

def wait_for_studio_ready(studio, timeout=300):
    """Wait for studio to be in running state"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if studio.status == Status.Running:
            return True
        elif studio.status == Status.Failed:
            return False
        time.sleep(10)
        print("Waiting for studio to be ready...")
    return False

def cleanup_and_upload_scripts(studio):
    """Clean up existing Python files and upload new ones from current directory"""
    try:
        # Remove existing Python files
        print("Removing existing Python files...")
        studio.run("rm -f *.py")
        
        # Upload required Python files
        required_files = ['demusic.py', 'cleanup_dirs.py']
        for file in required_files:
            if os.path.exists(file):
                print(f"Uploading {file}...")
                studio.upload_file(file, file)
            else:
                raise FileNotFoundError(f"Required file {file} not found in current directory")
        
        print("✓ Scripts uploaded successfully")
        return True
    except Exception as e:
        print(f"❌ Error managing scripts: {str(e)}")
        return False

def process_video(video_url):
    """Main function to process the video"""
    studio = None
    try:
        # Download YouTube video
        print("\n1. Downloading YouTube video...")
        video_path, video_title = download_youtube_video(video_url)
        print(f"✓ Video downloaded to: {video_path}")

        # Create Teamspace
        print("\nCreating Teamspace...")
        teamspace = Teamspace(name=f'{os.getenv("LIGHTNING_TEAMSPACE")}', user=f'{os.getenv("LIGHTNING_USER")}')
        print(f"\nSuccessfully created teamspace: {teamspace.name}")

        # Initialize Lightning Studio
        print("\n2. Connecting to Lightning AI...")
        studio =  Studio(name="demusifier-studio", user=f'{os.getenv("LIGHTNING_USER")}', teamspace=f'{os.getenv("LIGHTNING_TEAMSPACE")}')
        
        # Create and start studio with 4 CPU
        print("\n3. Creating and starting studio with 4 CPU...")
        studio.start(machine=Machine.CPU, interruptible=True)
        
        if not wait_for_studio_ready(studio):
            raise Exception("Studio failed to start within timeout period")
        print("✓ Studio ready")

        # Run setup commands
        print("Running setup commands...")
        install_deps = studio.run("pip install xgboost==2.0.2 && \
            pip install moviepy ffmpeg-python demucs torch torchaudio soundfile librosa && \
            sudo apt install ffmpeg")
        print(f"\nInstalled dependencies: {install_deps}")

        # Clean up and upload Python scripts
        print("\n4. Managing scripts...")
        if not cleanup_and_upload_scripts(studio):
            raise Exception("Failed to manage scripts")

        # Clean up videos dir
        print("\nCleaning up videos directory...")
        cleanup_output = studio.run("python cleanup.py")
        print(f"Cleanup output: {cleanup_output}")

        # Upload video to Lightning Drive
        print("\n5. Uploading video to Lightning Drive...")
        studio.upload_file(video_path, f"videos/input/{video_title}")
        print("✓ Video uploaded")

        # Switch to GPU machine
        print("\nSwitching to T4 GPU machine...")
        studio.switch_machine(machine=Machine.T4, interruptible=True)

        # Run the cleanser script
        print("\n6. Running video processing...")
        output = studio.run("python demusic.py")
        print(f"Processing output: {output}")

        # Download processed file
        print("\n7. Downloading processed video...")
        output_filename = f"{video_title}_.mp4"
        studio.download_file(
            f"videos/output/{output_filename}", 
            os.path.join(OUTPUT_DIR, output_filename)
        )
        print(f"✓ Output saved to: {os.path.join(OUTPUT_DIR, output_filename)}")

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        return False
    finally:
        if studio and studio.status == Status.Running:
            print("\n8. Stopping studio...")
            studio.stop()
            print("✓ Studio stopped")
    
    return True

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python light_it.py <youtube_url>")
        sys.exit(1)
        
    youtube_url = sys.argv[1]
    success = process_video(youtube_url)
    sys.exit(0 if success else 1)