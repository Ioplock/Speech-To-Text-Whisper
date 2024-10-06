# Base information
This is a essential scripts for transcripting anything in .wav format to .txt format.

`convert.py` is a script for converting .mp4 to .wav
`transcript.py` is a script for transcripting .wav to .txt
`tokens.py` is a script for counting tokens in file

Important: Use -h to see the help message for each script.
# How to use
```bash
python transcript.py [-h] [-o OUTPUT] [-l LANG] audio_file
```
```bash
python convert.py [-h] [-o OUTPUT] video_file
```
```bash
tokens.py [-h] -m MODEL input_file
```
# Dependencies
- python 3.11.9
- ffmpeg
- torch
- all requirements.txt