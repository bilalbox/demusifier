# Demusifier

A tool that automatically removes background music from videos while preserving speech/vocals using Lightning AI's cloud infrastructure.

## Overview

This project consists of several Python scripts that work together to:

1. Download videos
2. Process them using Demucs to separate vocals from background music
3. Create a new video with only the vocals/speech track

## Prerequisites

- Python 3.11+
- [Lightning AI](https://lightning.ai) account
- Lightning AI API key
- FFmpeg installed locally
- GPU access on Lightning AI (T4 recommended)

## Installation

1. Clone the repository:

```bash
git clone https://github.com/highwatersdev/demusifier.git
cd demusifier
```

2. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # On macOS/Linux
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the project root:

```plaintext
LIGHTNING_API_KEY=your_api_key_here
LIGHTNING_USER=your_username_here
LIGHTNING_TEAMSPACE=your_teamspace_name_here
```

## Project Structure

```
demusifier/
├── light_it.py          # Main script for Lightning AI integration
├── demusic.py        # Video processing script
├── cleanup_dirs.py      # Directory cleanup script
├── videos/
│   ├── input/          # Downloaded videos
│   └── output/         # Processed videos
└── .env                # Environment variables
```

## Setup in Lightning AI

1. Create a Lightning AI account at [lightning.ai](https://lightning.ai)
2. Create an API key:
   - Go to Settings -> API Keys
   - Generate a new key
   - Copy it to your `.env` file


## Usage

Run the script with a video URL:

```bash
python light_it.py "https://www.example.com/video_id"
```

The script will:

1. Download the video
2. Start a Lightning AI studio
3. Install required dependencies
4. Process the video (remove background music)
5. Download the processed video

## Expected Output

- Progress indicators for each step
- The processed video will be saved in `videos/output/`
- The output video will have the same video track but only vocals/speech audio

## Processing Steps

1. **Download**: Video is downloaded and sanitized
2. **Studio Setup**: Creates and configures Lightning AI studio
3. **Dependencies**: Installs required packages
4. **Processing**:
   - Extracts audio
   - Uses Demucs to separate vocals
   - Merges vocals with original video
5. **Cleanup**: Removes temporary files and stops the studio
