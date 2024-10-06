import argparse
import tiktoken

def count_tokens(model_name, file_path):
    # Load the tokenizer for the specified model
    encoding = tiktoken.encoding_for_model(model_name)
    
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()
    
    # Encode the text to count tokens
    tokens = encoding.encode(text)
    return len(tokens)

def main():
    parser = argparse.ArgumentParser(description='Count tokens in a file using tiktoken.')
    parser.add_argument('-m', '--model', type=str, required=True, help='Model name (e.g., gpt-4o)')
    parser.add_argument('input_file', type=str, help='Path to the input text file')
    
    args = parser.parse_args()
    
    token_count = count_tokens(args.model, args.input_file)
    print(f'Token count for model "{args.model}" in file "{args.input_file}": {token_count}')

if __name__ == '__main__':
    main()
