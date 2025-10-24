import streamlit as st
from book import Book
from utils import *

from ollama_client import check_connection, OLLAMA_BASE_URL, OLLAMA_MODEL

try:
    import openai  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    openai = None

BACKEND_OPTIONS = ('Ollama', 'OpenAI')
valid = False
backend_choice = BACKEND_OPTIONS[0]

# Center the title
st.title('BookGPT')
st.markdown('---')


def initialize():
    global valid, backend_choice
    backend_choice = st.radio('LLM Backend', BACKEND_OPTIONS, index=0)

    if backend_choice == 'OpenAI':
        if openai is None:
            st.error('The openai package is not installed. Please install it to use the OpenAI backend.')
            valid = False
            return

        api_key = st.text_input('OpenAI API Key', type='password')
        st.text_input('OpenAI Model', value='gpt-3.5-turbo', key='openai_model_input')

        if api_key:
            openai.api_key = api_key
            try:
                openai.Model.list()
                valid = True
                st.success('API key is valid!')
            except openai.error.AuthenticationError:  # type: ignore[attr-defined]
                valid = False
                st.error('API key is not valid!')
            except Exception:
                valid = False
                st.warning('Unable to validate the API key right now. Please try again later.')
        else:
            valid = False
    else:
        if check_connection():
            valid = True
            st.success(f'Connected to {OLLAMA_MODEL} at {OLLAMA_BASE_URL}.')
        else:
            valid = False
            st.error('Unable to connect to the Ollama server.')


def generate_book(chapters, words, category, topic, language):
    backend = backend_choice.lower()
    kwargs = dict(
        chapters=chapters,
        words_per_chapter=words,
        topic=topic,
        category=category,
        language=language,
        llm_backend=backend,
    )

    if backend == 'openai':
        kwargs['openai_model'] = st.session_state.get('openai_model_input', 'gpt-3.5-turbo')

    try:
        with st.spinner('Generating book...'):
            book = Book(**kwargs)
            book.get_title()
            book.get_structure()
            book.finish_base()
            book.get_content()
            st.markdown(book.to_markdown())
    except Exception as exc:
        st.error(f'Failed to generate the book: {exc}')


def show_form():
    # Create form for user input
    with st.form('BookGPT'):

        # Get the number of chapters
        chapters = st.number_input('How many chapters should the book have?', min_value=1, max_value=100, value=5)

        # Get the number of words per chapter
        words = st.number_input('How many words should each chapter have?', min_value=100, max_value=2000, value=1200,
                                step=50)

        # Get the category of the book
        category = st.selectbox('What is the category of the book?',
                                get_categories())

        # Get the topic of the book
        topic = st.text_input('What is the topic of the book?', placeholder='e.g. "Finance"')

        # Get the language of the book
        language = st.text_input('What is the language of the book?', placeholder='e.g. "English"')

        # Submit button
        submit = st.form_submit_button('Generate')

        # Check if the selected backend is ready
        if submit and not valid:
            if backend_choice == 'OpenAI':
                st.error('The OpenAI configuration is not valid. Please check your API key and try again.')
            else:
                st.error('Unable to reach the Ollama server. Please try again later.')

        # Check if all fields are filled
        elif submit and not (chapters and words and category and topic and language):
            st.error('Please fill in all fields!')

        # Generate the book
        elif submit:
            # Generate the book outside the form
            generate_book(chapters, words, category, topic, language)


initialize()
show_form()
