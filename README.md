# Multifunction Tool 

This tool provides three main functionalities:
 
- **Transcribe** : Convert audio files to text using the Whisper model.
 
- **Extract Audio** : Extract audio from video files.
 
- **Count Tokens** : Count the number of tokens in a text file using the `tiktoken` tokenizer.

## Installation 

### Prerequisites 

- Python 3.7 or higher
 
- `pip` (Python package installer)

### Steps to Install 

1. Clone or download the repository to your local machine.
 
2. Navigate to the root directory where `setup.py` is located.

3. Run the following command to install the package:


```Copy code
pip install .
```
This will install all necessary dependencies (like `whisper`, `tiktoken`, `moviepy`, and `tqdm`) and make the `transcript` command available globally on your system.

---


## Usage 

### Command Line Interface (CLI) 
Once installed, you can use the `transcript` command to access different functionalities.
### 1. Transcribing Audio 

To transcribe an audio file to text using the Whisper model:


```Copy code
transcript transcribe <audio_file> -o <output_file> -l <language> -m <model>
```
 
- `<audio_file>`: Path to the audio file you want to transcribe.
 
- `-o <output_file>`: (Optional) Path to the output text file (default is `transcription.txt`).
 
- `-l <language>`: (Optional) Language of the audio (default is `ru`).
 
- `-m <model>`: (Optional) Whisper model to use (default is `medium`). Available options: `tiny`, `base`, `small`, `medium`, `large`.

#### Example: 


```Copy code
transcript transcribe my_audio.mp3 -o result.txt -l en -m small
```

### 2. Extracting Audio from Video 

To extract audio from a video file:


```Copy code
transcript extract_audio <video_file> -o <output_audio_file>
```
 
- `<video_file>`: Path to the video file.
 
- `-o <output_audio_file>`: (Optional) Path to the output audio file (default is `output.wav`).

#### Example: 


```Copy code
transcript extract_audio my_video.mp4 -o extracted_audio.wav
```

### 3. Counting Tokens 

To count the number of tokens in a text file:


```Copy code
transcript count_tokens -m <model> <input_file>
```
 
- `-m <model>`: The model to use for tokenization (e.g., `gpt-4`).
 
- `<input_file>`: Path to the input text file.

#### Example: 


```Copy code
transcript count_tokens -m gpt-3.5-turbo my_text.txt
```


---


## Uninstallation 

To uninstall the tool from your system, simply run:


```Copy code
pip uninstall multifunction_tool
```

This will remove the package and its CLI commands from your environment.
