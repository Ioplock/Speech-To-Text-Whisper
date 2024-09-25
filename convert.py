import argparse
from moviepy.editor import VideoFileClip
import os

def extract_audio(video_file, audio_output):
    video = VideoFileClip(video_file)
    video.audio.write_audiofile(audio_output)

def main():
    # Create an argument parser object
    parser = argparse.ArgumentParser(description="Extract audio from a video file.")
    
    # Add the positional argument for the video file
    parser.add_argument('video_file', type=str, help="Path to the input video file")
    
    # Add the optional argument for the audio output file
    parser.add_argument('-o', '--output', type=str, default="output.wav", help="Output audio file (optional, defaults to 'output.wav')")
    
    # Parse the arguments
    args = parser.parse_args()
    
    if not os.path.exists(args.video_file):
        print(f"Ошибка: файл '{args.video_file}' не существует.")
        exit(1)

    # Call the function to extract audio
    extract_audio(args.video_file, args.output)

if __name__ == "__main__":
    main()
