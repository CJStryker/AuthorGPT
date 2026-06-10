<h1 align="center">BookGPT (Beta)</h1>
<p align="center">This program uses the ChatGPT API to generate books based on your specified parameters.
<br><br>
</p>


## Installation
To install this program, simply follow these steps:
1. Clone this repository to your local machine by running the following command in your terminal:
```bash
git clone https://github.com/mikavehns/BookGPT.git
```
2. Navigate to the root directory of the repository using `cd BookGPT`
3. Install the required dependencies by running the following command:
```bash
pip install -r requirements.txt
```


## Prerequisites
BookGPT can generate with either Ollama (default) or OpenAI.

### Ollama (default)
1. Install and start [Ollama](https://ollama.com/).
2. Pull a chat model, for example:
```bash
ollama pull llama3.1
```
3. If you use a different host or model, configure it with environment variables:
```bash
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_MODEL=llama3.1
export OLLAMA_TIMEOUT=300
```

The Streamlit app also exposes the Ollama base URL, model, and timeout fields in the UI.

### OpenAI (optional)
To use OpenAI instead, install the dependencies, set `BOOKGPT_BACKEND=openai`, and provide `OPENAI_KEY`.


## Usage
To use this program from the terminal, run:
```bash
python src/run.py
```

To use the Streamlit interface, run:
```bash
streamlit run src/app.py
```
You will then be prompted to enter the following information:
- Chapter Amount: The amount of chapters you want the book to have.
- Chapter Length: The amount of words you want each chapter to have.
- Topic: The topic you want the book to be about.
- Category: The type of book you want to generate. (Science, Biography, etc.)

The program will then generate a Title and Chapter Titles + Content. You will get a detailed structure of the book.
Generated books are saved as Markdown files in the current directory by default. Set `BOOKGPT_OUTPUT_DIR` to choose a different output folder. Partial progress is autosaved after each completed paragraph so an Ollama crash or timeout does not overwrite existing content with an empty file.


## Examples
Here are some examples:
- Generate book with 5 chapters and 300 words per chapter, with quotes as chapter title, with the topic "success":

https://user-images.githubusercontent.com/66560242/210459589-751c82d7-e874-4119-a09a-cc36ea2be73c.mp4

- You can see all examples in the `examples/` directory.


## Notes
- The run.py file is just one example on how to use the book generator. You can also implement it into a website, discord bot, desktop app, etc.
- The program may take some time to run, depending on the specified parameters and the performance of the ChatGPT API. Please be patient while the book is being generated.
- The program may not always generate the wished amount of words for each chapter. This can happen, if there is not enough data available for the specified topic.
- Currently, it is only possible to generate Non-Fiction books.
- Since this is a really early version (v0.8.0), there are many missing features, that will be added by time


## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.


## Contributing
- If you are interested in contributing to BookGPT, I welcome any suggestions or pull requests. Please feel free to open an issue or submit a pull request on the [GitHub repository](https://github.com/mikavehns/BookGPT).
- You can also submit your books, which I will then add to the `examples` folder. Just open a pull request with the book in the `examples` folder.
