import importlib.util

from tqdm import tqdm
import prompts
import os
import re
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
import time
from typing import List, Dict, Optional


class GenerationInterrupted(RuntimeError):
    """Raised when generation stops mid-chapter but partial content exists."""

    def __init__(self, message: str, partial_chapter: List[str]):
        super().__init__(message)
        self.partial_chapter = partial_chapter

openai = None
if importlib.util.find_spec('openai') is not None:
    import openai  # type: ignore

from ollama_client import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT, chat, OllamaError

class Book:
    def __str__(self):
        book_structure = "Structure of the book:\n"
        for chapter_index, chapter_info in enumerate(self.chapters, start=1):
            chapter_title = chapter_info['title']
            chapter_paragraphs = chapter_info['paragraphs']
            book_structure += f"Chapter {chapter_index} ({len(chapter_paragraphs)} paragraphs): {chapter_title}\n"
            for paragraph_index, paragraph_info in enumerate(chapter_paragraphs, start=1):
                paragraph_title = paragraph_info['title']
                paragraph_words = paragraph_info['words']
                book_structure += f"\tParagraph {paragraph_index} ({paragraph_words} words): {paragraph_title}\n"

        return book_structure
      
    def __init__(self, **kwargs):
        excluded_keys = {'tolerance', 'llm_backend', 'openai_model', 'ollama_options', 'ollama_model', 'ollama_base_url', 'ollama_timeout', 'max_retries', 'retry_delay', 'max_continuations', 'output_dir'}
        # Joining the keyword arguments into a single string
        self.arguments = '; '.join([
            f'{key}: {value}' for key, value in kwargs.items() if key not in excluded_keys
        ])

        # Get 'tolerance' attribute from kwargs
        self.tolerance = kwargs.get('tolerance', 0.9)

        # Configure LLM preferences
        self.llm_backend = kwargs.get('llm_backend', 'openai').lower()
        self.openai_model = kwargs.get('openai_model', 'gpt-3.5-turbo')
        self.ollama_options = kwargs.get('ollama_options')
        self.ollama_model = kwargs.get('ollama_model', OLLAMA_MODEL)
        self.ollama_base_url = kwargs.get('ollama_base_url', OLLAMA_BASE_URL)
        self.ollama_timeout = float(kwargs.get('ollama_timeout', OLLAMA_TIMEOUT))
        self.max_retries = int(kwargs.get('max_retries', 3))
        self.retry_delay = float(kwargs.get('retry_delay', 5))
        self.max_continuations = int(kwargs.get('max_continuations', 6))
        self.output_dir = Path(kwargs.get('output_dir', os.getenv('BOOKGPT_OUTPUT_DIR', '.')))

        # Track whether only partial content is available
        self.partial_content = False
        self.last_saved_path: Optional[str] = None

        # Assign a status variable
        self.status = 0

        # Setting up the base prompt
        self.base_prompt = [
            self.get_message('system', prompts.INITIAL_INSTRUCTIONS),
            self.get_message('user', self.arguments),
            self.get_message('assistant', 'Ready')
        ]

        # Setting up the title prompt
        self.title_prompt = [
            self.get_message('system', prompts.TITLE_INSTRUCTIONS),
            self.get_message('assistant', 'Ready'),
            self.get_message('user', self.arguments)
        ]

        # Setting up the structure prompt
        self.structure_prompt = [
            self.get_message('system', prompts.STRUCTURE_INSTRUCTIONS),
            self.get_message('assistant', 'Ready'),
        ]

        self.output('Prompts set up. Ready to generate book.')

    def get_title(self):
        self.title = self.get_response(self.title_prompt)
        return self.title

    def get_structure(self):
        if not hasattr(self, 'title'):
            self.output('Title not generated. Please generate title first.')
            return
        else:
            structure_arguments = self.arguments + f'; title: {self.title}'
            self.structure_prompt.append(self.get_message('user', structure_arguments))
            self.structure = self.get_response(self.structure_prompt)
            self.chapters = self.convert_structure(self.structure)

            if not self.chapters:
                raise ValueError('Unable to parse a valid book structure from the LLM response.')

            self.paragraph_amounts = self.get_paragraph_amounts(self.chapters)
            self.paragraph_words = self.get_paragraph_words(self.chapters)
            if not any(self.paragraph_amounts):
                raise ValueError('The generated book structure did not contain any paragraphs.')
            return str(self.structure)

    def finish_base(self):
        if not hasattr(self, 'title'):
            self.output('Title not generated. Please generate title first.')
            return
        elif not hasattr(self, 'structure'):
            self.output('Structure not generated. Please generate structure first.')
            return
        else:
            self.base_prompt.append(self.get_message('user', '!t'))
            self.base_prompt.append(self.get_message('assistant', self.title))

            self.base_prompt.append(self.get_message('user', '!s'))
            self.base_prompt.append(self.get_message('assistant', self.structure))
            return self.base_prompt

    def calculate_max_status(self):
        if not hasattr(self, 'chapters'):
            self.output('Structure not generated. Please generate structure first.')
            return
        else:
            self.max_status = sum(self.get_paragraph_amounts(self.chapters))
            return self.max_status

    def get_content(self):
        if not hasattr(self, 'chapters'):
            raise ValueError('Structure not generated yet.')

        chapters: List[List[str]] = []
        try:
            for i in tqdm(range(len(self.chapters))):
                prompt = self.base_prompt.copy()
                chapter = self.get_chapter(i, prompt.copy())
                chapters.append(chapter)
        except GenerationInterrupted as interrupted:
            if interrupted.partial_chapter:
                chapters.append(interrupted.partial_chapter)
            self._persist_partial_content(chapters, interrupted)
            raise RuntimeError(str(interrupted)) from interrupted.__cause__
        except Exception as exc:
            self._persist_partial_content(chapters, exc)
            raise
        else:
            self.content = chapters
            self.partial_content = False
            return self.content

    def save_book(self, filename: Optional[str] = None) -> str:
        """Save the generated book as Markdown using an atomic file replace."""

        if not getattr(self, 'content', None) or not any(self.content):
            raise ValueError('No generated content to save yet.')

        desired_time = datetime.now(timezone(timedelta(hours=-5)))  # EST timezone
        timestamp = desired_time.strftime('%Y%m%d%H%M%S%f')
        suffix = '_partial' if self.partial_content else ''

        path = Path(filename) if filename else self.output_dir / f'book{timestamp}{suffix}.md'
        path.parent.mkdir(parents=True, exist_ok=True)

        markdown = self.to_markdown()
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False) as tmp_file:
            tmp_file.write(markdown)
            tmp_path = Path(tmp_file.name)

        os.replace(tmp_path, path)
        self.last_saved_path = str(path)
        return str(path)

    def get_chapter(self, chapter_index, prompt):
        if len(self.base_prompt) <= 9:
            self.finish_base()

        paragraphs = []
        for i in range(self.paragraph_amounts[chapter_index]):
            try:
                paragraph = self.get_paragraph(prompt.copy(), chapter_index, i)
            except Exception as exc:  # pragma: no cover - network/runtime failure
                raise GenerationInterrupted(
                    f'Failed to generate paragraph {i + 1} of chapter {chapter_index + 1}',
                    paragraphs,
                ) from exc

            prompt.append(self.get_message('user', f'!w {chapter_index + 1} {i + 1}'))
            prompt.append(self.get_message('assistant', paragraph))
            self.status += 1
            paragraphs.append(paragraph)
            self._autosave_progress(paragraphs, chapter_index)
        return paragraphs

    def get_paragraph(self, prompt, chapter_index, paragraph_index):
        prompt.append(self.get_message('user', f'!w {chapter_index + 1} {paragraph_index + 1}'))
        paragraph = self.get_response(prompt)
        prompt.append(self.get_message('assistant', paragraph))

        target_words = int(self.paragraph_words[chapter_index][paragraph_index] * self.tolerance)
        continuation_count = 0
        while len(paragraph.split()) < target_words and continuation_count < self.max_continuations:
            prompt.append(self.get_message('system', '!c'))
            response = self.get_response(prompt)
            paragraph = f'{paragraph.rstrip()}\n\n{response.strip()}'
            prompt.append(self.get_message('assistant', response))
            continuation_count += 1

        if len(paragraph.split()) < target_words:
            self.output(
                f'Warning: paragraph {paragraph_index + 1} of chapter {chapter_index + 1} '
                f'is shorter than requested after {self.max_continuations} continuations.'
            )

        return paragraph

    @staticmethod
    def get_message(role, content):
        return {"role": role, "content": content}
      
    @staticmethod
    def convert_structure(structure):
        chapter_information = []
        current_chapter = None

        chapter_pattern = re.compile(r'^\s*Chapter\s+\d+\s*\((?:\d+\s+)?paragraphs?\)\s*:\s*(.+)\s*$', re.IGNORECASE)
        paragraph_pattern = re.compile(r'^\s*Paragraph\s+\d+\s*\((\d+)\s+words?\)\s*:\s*(.+)\s*$', re.IGNORECASE)

        for line in structure.splitlines():
            chapter_match = chapter_pattern.match(line)
            if chapter_match:
                current_chapter = {'title': chapter_match.group(1).strip(), 'paragraphs': []}
                chapter_information.append(current_chapter)
                continue

            paragraph_match = paragraph_pattern.match(line)
            if paragraph_match and current_chapter is not None:
                current_chapter['paragraphs'].append({
                    'title': paragraph_match.group(2).strip(),
                    'words': paragraph_match.group(1),
                })

        return chapter_information


    @staticmethod
    def get_paragraph_amounts(structure):
        amounts = []
        for chapter in structure:
            amounts.append(len(chapter['paragraphs']))
        return amounts

    @staticmethod
    def get_paragraph_words(structure):
        words = []
        for chapter in structure:
            words.append([int(x['words']) for x in chapter['paragraphs']])
        return words

    def get_response(self, prompt: List[Dict[str, str]], max_retries: Optional[int] = None) -> str:
        max_retries = self.max_retries if max_retries is None else max_retries
        retries = 0
        last_error: Optional[Exception] = None
        backend = self.llm_backend
        while retries < max_retries:
            try:
                if backend == 'ollama':
                    response = chat(
                        prompt,
                        model=self.ollama_model,
                        base_url=self.ollama_base_url,
                        timeout=self.ollama_timeout,
                        options=self.ollama_options,
                    )
                elif backend == 'openai':
                    if openai is None:  # pragma: no cover - dependency guard
                        raise RuntimeError('openai package is not installed')
                    response = openai.ChatCompletion.create(  # type: ignore[attr-defined]
                        model=self.openai_model,
                        messages=prompt
                    )["choices"][0]["message"]["content"]
                else:
                    raise RuntimeError(f"Unsupported LLM backend: {backend}")

                if not isinstance(response, str) or not response.strip():
                    raise RuntimeError('LLM returned an empty response')

                with open("log.txt", "a", encoding="utf-8") as f:
                    f.write(f"Prompt: {prompt}\nResponse: {response}\n\n")
                return response.strip()
            except OllamaError as exc:
                last_error = exc
            except Exception as exc:  # pragma: no cover - runtime/network failure
                last_error = exc

            retries += 1
            if retries < max_retries:
                print(f"An error occurred: {last_error}. Retrying ({retries}/{max_retries})...")
                time.sleep(self.retry_delay)

        if last_error is None:
            raise RuntimeError("Unknown error while requesting a response")
        raise RuntimeError(f"Failed to get a response after {max_retries} retries.") from last_error

    def to_markdown(self) -> str:
        if not hasattr(self, 'content'):
            raise ValueError('Content not generated yet.')

        lines = [f'# {getattr(self, "title", "Untitled Book")}']
        if self.partial_content:
            lines.append('')
            lines.append('> **Note:** Generation stopped early; the content below is partial.')

        for chapter_index, (chapter_meta, paragraphs) in enumerate(zip(self.chapters, self.content), start=1):
            lines.append('')
            lines.append(f'## Chapter {chapter_index}: {chapter_meta["title"]}')
            lines.append('')
            for paragraph_index, paragraph in enumerate(paragraphs, start=1):
                paragraph_meta = chapter_meta['paragraphs'][paragraph_index - 1]
                lines.append(f'### {paragraph_meta["title"]}')
                lines.append('')
                lines.append(paragraph)
                lines.append('')

        return '\n'.join(lines).strip() + '\n'

    @staticmethod
    def output(message):
        print(message)

    def _autosave_progress(self, current_chapter: List[str], chapter_index: int) -> None:
        """Save recoverable content after each completed paragraph."""

        previous_content = getattr(self, 'content', None)
        previous_partial = self.partial_content
        chapters = list(previous_content or [])

        while len(chapters) <= chapter_index:
            chapters.append([])
        chapters[chapter_index] = current_chapter.copy()

        self.content = chapters
        self.partial_content = True
        try:
            self.save_book(self.last_saved_path) if self.last_saved_path else self.save_book()
        finally:
            self.partial_content = previous_partial
            if previous_content is not None:
                self.content = previous_content

    def _persist_partial_content(self, chapters: List[List[str]], error: Optional[Exception] = None) -> None:
        """Persist partial content to disk for recovery without creating empty files."""

        if not chapters or not any(chapters):
            self.output('No generated paragraphs were available to save.')
            return

        self.content = chapters
        self.partial_content = True
        path = self.save_book(self.last_saved_path) if self.last_saved_path else self.save_book()
        message = f'Partial book saved to {path}.'
        if error is not None:
            message = f'{message} Reason: {error}'
        self.output(message)
