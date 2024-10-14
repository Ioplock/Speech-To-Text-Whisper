import argparse
import os
import whisper
import tiktoken
from tqdm import tqdm
from moviepy.editor import VideoFileClip

def transcribe_audio(input_file, output_file, lang, model):
    # Load Whisper model
    model = whisper.load_model(model)

    # Start transcribing the audio
    print("Starting transcription...")
    result = model.transcribe(input_file, language=lang, verbose=False)

    # Initialize progress bar
    total_segments = len(result['segments'])
    with tqdm(total=total_segments, desc="Transcribing", unit="segment") as pbar:
        for segment in result['segments']:
            pbar.update(1)

    # Save result to text file
    with open(output_file, "w", encoding="utf-8") as file:
        file.write(result['text'])

    print(f"Transcription saved to '{output_file}'")


def extract_audio(video_file, audio_output):
    video = VideoFileClip(video_file)
    video.audio.write_audiofile(audio_output)


def count_tokens(model_name, file_path):
    encoding = tiktoken.encoding_for_model(model_name)
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()
    tokens = encoding.encode(text)
    return len(tokens)


def main():
    parser = argparse.ArgumentParser(description='A tool for transcription, audio extraction, and token counting.')
    
    subparsers = parser.add_subparsers(dest='command', help='Sub-command help')

    # Transcribe sub-command
    parser_transcribe = subparsers.add_parser('transcribe', help='Transcribe an audio file.')
    parser_transcribe.add_argument('audio_file', type=str, help="Path to the audio file for transcription")
    parser_transcribe.add_argument('-o', '--output', type=str, default="transcription.txt", help="Path to the output text file")
    parser_transcribe.add_argument('-l', '--lang', type=str, default="ru", help="Language to detect")
    parser_transcribe.add_argument('-m', '--model', type=str, default="medium", help="Model to use")

    # Extract audio sub-command
    parser_extract = subparsers.add_parser('extract_audio', help='Extract audio from a video file.')
    parser_extract.add_argument('video_file', type=str, help="Path to the input video file")
    parser_extract.add_argument('-o', '--output', type=str, default="output.wav", help="Output audio file")

    # Count tokens sub-command
    parser_tokens = subparsers.add_parser('count_tokens', help='Count tokens in a text file.')
    parser_tokens.add_argument('-m', '--model', type=str, required=True, help='Model name (e.g., gpt-4)')
    parser_tokens.add_argument('input_file', type=str, help="Path to the input text file")

    args = parser.parse_args()

    if args.command == 'transcribe':
        if not os.path.exists(args.audio_file):
            print(f"Error: '{args.audio_file}' does not exist.")
            return
        transcribe_audio(args.audio_file, args.output, args.lang, args.model)

    elif args.command == 'extract_audio':
        if not os.path.exists(args.video_file):
            print(f"Error: '{args.video_file}' does not exist.")
            return
        extract_audio(args.video_file, args.output)

    elif args.command == 'count_tokens':
        if not os.path.exists(args.input_file):
            print(f"Error: '{args.input_file}' does not exist.")
            return
        token_count = count_tokens(args.model, args.input_file)
        print(f'Token count for model "{args.model}" in file "{args.input_file}": {token_count}')

if __name__ == '__main__':
    main()
