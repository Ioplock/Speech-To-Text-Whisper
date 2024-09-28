import whisper
from tqdm import tqdm
import argparse
import os

import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

def transcribe_audio(input_file, output_file, lang, model):
    # Загружаем модель (можно выбрать различные варианты модели: "tiny", "base", "small", "medium", "large")
    model = whisper.load_model(model)

    # Начинаем транскрипцию
    print("Начинаю транскрипцию аудиофайла...")

    # Запускаем процесс транскрипции
    result = model.transcribe(input_file, language=lang, verbose=False)

    # Инициализируем прогресс-бар
    total_segments = len(result['segments'])
    with tqdm(total=total_segments, desc="Транскрибирование", unit="сегмент") as pbar:
        for segment in result['segments']:
            # Обрабатываем каждый сегмент (здесь, в данном случае, мы ничего не делаем)
            pbar.update(1)  # Обновляем прогресс-бар

    # Сохранение результата в текстовый файл
    with open(output_file, "w", encoding="utf-8") as file:
        file.write(result['text'])

    print(f"Файл с транскрипцией успешно сохранен в '{output_file}'")

if __name__ == "__main__":
    # Инициализируем парсер аргументов
    parser = argparse.ArgumentParser(description="Transcribe audio using Whisper model")
    parser.add_argument("audio_file", type=str, help="Path to the audio file for transcription")
    parser.add_argument("-o", "--output", type=str, help="Path to the output text file", default="transcription.txt")
    parser.add_argument("-l", "--lang", type=str, help="Language to detect", default="ru")
    parser.add_argument("-m", "--model", type=str, help="Model to use", default="medium")

    # Получаем аргументы
    args = parser.parse_args()

    # Проверяем, существует ли аудиофайл
    if not os.path.exists(args.audio_file):
        print(f"Ошибка: файл '{args.audio_file}' не существует.")
        exit(1)

    # Запускаем функцию транскрипции с заданными аргументами
    transcribe_audio(args.audio_file, args.output, args.lang, args.model)
