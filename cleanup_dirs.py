import os
import shutil

def cleanup_input_directory():
    """Clean up the input directory in Studio workspace"""
    dirs = ['videos/input','videos/output','videos/working']
    for dir in dirs:
        if os.path.exists(dir):
            try:
                shutil.rmtree(dir)
                print(f"✓ Successfully cleaned up {dir}")
            except Exception as e:
                print(f"❌ Error cleaning up {dir}: {str(e)}")
        else:
            print(f"! Directory {dir} does not exist")
        
        # Recreate the directory
        os.makedirs(dir, exist_ok=True)

if __name__ == "__main__":
    cleanup_input_directory()