# Imports
import os
from pyfiglet import Figlet
from book import Book

try:
    import openai  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    openai = None

# Draw the given text in a figlet
def draw(text):
    # Create a new figlet object
    f = Figlet()

    # Print the figlet
    print(f.renderText(text))


# Get a selection from a list of options
def get_option(options):
    # Print the available options
    print('Please select an option:')
    for i, option in enumerate(options):
        print(f'[{i + 1}] {option}')

    # While the user input is not valid
    while True:
        try:

            # Get the selection
            selection = int(input('> '))

            # Check if the selection is valid
            if selection < 1 or selection > len(options):
                raise ValueError

            # Return the selection
            return selection

        # User input was not valid
        except ValueError:
            print('Invalid option. Please try again.')


def select_backend() -> str:
    backend = os.getenv('BOOKGPT_BACKEND', 'ollama').lower()
    if backend not in {'openai', 'ollama'}:
        backend = 'ollama'

    if backend == 'openai':
        if openai is None:
            print('openai package is not installed. Falling back to Ollama backend.')
            return 'ollama'

        api_key = os.getenv('OPENAI_KEY')
        if not api_key:
            print('OPENAI_KEY not found. Falling back to Ollama backend.')
            return 'ollama'

        openai.api_key = api_key
        print('Using OpenAI backend for generation.')
    else:
        print('Using Ollama backend for generation.')

    return backend


def get_default_book_kwargs(backend: str) -> dict:
    data = {
        'chapters': int(os.getenv('BOOKGPT_CHAPTERS', 5)),
        'words_per_chapter': int(os.getenv('BOOKGPT_WORDS_PER_CHAPTER', 1200)),
        'category': os.getenv('BOOKGPT_CATEGORY', 'Science Fiction'),
        'topic': os.getenv('BOOKGPT_TOPIC', """William a 27-year-old boy moves to an unfamiliar city and rents a house, where he will begin a new life. He is quiet, socially awkward, and dislikes interacting with people, Nevertheless, he will inevitably encounter various situations requiring social interaction in the future, as well as many moments where friends will be needed, whether for problem-solving or emotional support. Despite his quirky personality, this also makes it easier for him to find genuine friends. These friends, while tolerating his rationality and sharpness, care about him and try their best to help him resolve the problems he encounters. His life is simple. He lives frugally, spending only the necessary money on essential daily necessities. When it comes to interpersonal relationships, he highly values "choice" and "necessity." He believes that no friend or person has any obligation to do anything for him, and he himself has no justification to demand that anyone must do anything for him. If someone tells the protagonist, "You are very important to me," he would feel flustered and overwhelmed. He takes commitments seriously and will always do his utmost to fulfill promises he has made. However, he is usually cautious and tends to avoid making promises altogether. 未自华为备意录"""),
        'tolerance': float(os.getenv('BOOKGPT_TOLERANCE', 0.6)),
        'llm_backend': backend,
    }

    if backend == 'openai':
        data['openai_model'] = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')

    return data


def prompt_with_default(prompt_text: str, default: str) -> str:
    response = input(f"{prompt_text} [{default}]: ").strip()
    return response or default


def prompt_int_with_default(prompt_text: str, default: int, minimum: int = 1) -> int:
    while True:
        response = input(f"{prompt_text} [{default}]: ").strip()
        if not response:
            return default
        try:
            value = int(response)
        except ValueError:
            print('Please enter a valid number.')
            continue

        if value < minimum:
            print(f'Please enter a value greater than or equal to {minimum}.')
            continue

        return value


def collect_book_preferences(defaults: dict) -> dict:
    print('Provide details for your book (press Enter to keep the default).')
    chapters = prompt_int_with_default('How many chapters should the book have?', defaults['chapters'], minimum=1)
    words = prompt_int_with_default(
        'How many words should each chapter have?',
        defaults['words_per_chapter'],
        minimum=100,
    )
    category = prompt_with_default('What is the category of the book?', defaults['category'])
    topic = prompt_with_default('What is the topic of the book?', defaults['topic'])

    data = {
        'chapters': chapters,
        'words_per_chapter': words,
        'category': category,
        'topic': topic,
        'tolerance': defaults['tolerance'],
        'llm_backend': defaults['llm_backend'],
    }

    if defaults.get('openai_model'):
        data['openai_model'] = defaults['openai_model']

    return data


def main():
    backend = select_backend()

    # Draw the title
    draw('BookGPT')

    if get_option(['Generate a book', 'Exit']) - 1:
        return

    defaults = get_default_book_kwargs(backend)
    book_kwargs = collect_book_preferences(defaults)
    book = Book(**book_kwargs)

    title = book.get_title()
    print(f'Title: {title}')

    while True:
        print('Do you want to generate a new title?')
        if get_option(['No', 'Yes']) - 1:
            title = book.get_title()
            print(f'Title: {title}')
        else:
            break

    print('Structure of the book:')
    structure = book.get_structure()
    print(structure)

    while True:
        print('Do you want to generate a new structure?')
        if get_option(['No', 'Yes']) - 1:
            print('Structure of the book:')
            structure = book.get_structure()
            print(structure)
        else:
            break

    print('Generating book...')

    book.finish_base()
    book.get_content()
    book.save_book()
    print('Book saved.')

# Run the main function
if __name__ == "__main__":
    main()
