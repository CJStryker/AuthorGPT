import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from book import Book
from ollama_client import OLLAMA_BASE_URL, OllamaError, chat


class GenerationRecoveryTests(unittest.TestCase):
    def test_default_ollama_base_url_is_project_ngrok_host(self):
        self.assertEqual(
            'https://b88c-2607-fb90-2e06-f693-405d-1c37-476f-b7e6.ngrok-free.app',
            OLLAMA_BASE_URL,
        )

    def make_book(self, output_dir):
        book = Book(
            chapters=1,
            words_per_chapter=100,
            topic='testing',
            category='technical',
            llm_backend='ollama',
            output_dir=output_dir,
            max_continuations=0,
        )
        book.title = 'Reliable Generation'
        book.structure = 'Chapter 1 (1 paragraphs): Recovery\n\tParagraph 1 (100 words): Autosaves'
        book.chapters = book.convert_structure(book.structure)
        book.paragraph_amounts = book.get_paragraph_amounts(book.chapters)
        book.paragraph_words = book.get_paragraph_words(book.chapters)
        return book

    def test_save_book_refuses_empty_content(self):
        with tempfile.TemporaryDirectory() as output_dir:
            book = self.make_book(output_dir)
            book.content = [[]]

            with self.assertRaises(ValueError):
                book.save_book()

            self.assertEqual([], list(Path(output_dir).glob('*.md')))

    def test_partial_content_is_saved_after_completed_paragraph(self):
        with tempfile.TemporaryDirectory() as output_dir:
            book = self.make_book(output_dir)
            book._autosave_progress(['Generated text.'], 0)

            saved_files = list(Path(output_dir).glob('*_partial.md'))
            self.assertEqual(1, len(saved_files))
            saved_text = saved_files[0].read_text(encoding='utf-8')
            self.assertIn('Generation stopped early', saved_text)
            self.assertIn('Generated text.', saved_text)

    def test_ollama_empty_response_raises_clear_error(self):
        response = Mock(ok=True, status_code=200)
        response.json.return_value = {'message': {'content': '   '}}

        with patch('ollama_client.requests.post', return_value=response):
            with self.assertRaisesRegex(OllamaError, 'empty response'):
                chat([{'role': 'user', 'content': 'hello'}], model='test')


if __name__ == '__main__':
    unittest.main()
