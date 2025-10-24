import streamlit as st
from book import Book
from utils import *

from ollama_client import check_connection, OLLAMA_BASE_URL, OLLAMA_MODEL

valid = False
content = ''

# Center the title
st.title('BookGPT')
st.markdown('---')


def initialize():
    global valid
    if check_connection():
        valid = True
        st.success(f'Connected to {OLLAMA_MODEL} at {OLLAMA_BASE_URL}.')
    else:
        valid = False
        st.error('Unable to connect to the Ollama server.')


def generate_book(chapters, words, category, topic, language):
    book = Book(
        chapters=chapters,
        words_per_chapter=words,
        topic=topic,
        category=category,
        language=language,
    )
    content = book.get_content()
    st.markdown(content)


def show_form():
    # Create form for user input
    with st.form('BookGPT'):

        # Get the number of chapters
        chapters = st.number_input('How many chapters should the book have?', min_value=1, max_value=100, value=10)

        # Get the number of words per chapter
        words = st.number_input('How many words should each chapter have?', min_value=100, max_value=2000, value=2000,
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

        # Check if the Ollama server is reachable
        if submit and not valid:
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
