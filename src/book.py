from tqdm import tqdm
import prompts
import random
from datetime import datetime, timezone, timedelta
import time
from typing import List, Dict, Optional


class GenerationInterrupted(RuntimeError):
    """Raised when generation stops mid-chapter but partial content exists."""

    def __init__(self, message: str, partial_chapter: List[str]):
        super().__init__(message)
        self.partial_chapter = partial_chapter

try:
    import openai  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    openai = None

from ollama_client import chat, OllamaError

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
        excluded_keys = {'tolerance', 'llm_backend', 'openai_model', 'ollama_options'}
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

            # Ensure self.chapters contains the actual chapter information before assigning paragraph amounts and words.
            if isinstance(self.chapters, list):
                self.paragraph_amounts = self.get_paragraph_amounts(self.chapters)  # updated line
                self.paragraph_words = self.get_paragraph_words(self.chapters)  # updated line
                return str(self.structure)
            else:
                self.output('Error in converting the book structure.')

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
            chapters.append(interrupted.partial_chapter)
            self._persist_partial_content(chapters, interrupted)
            raise RuntimeError(str(interrupted)) from interrupted.__cause__
        except Exception:
            if chapters:
                self._persist_partial_content(chapters)
            raise
        else:
            self.content = chapters
            self.partial_content = False
            return self.content

    def save_book(self, filename: Optional[str] = None) -> str:
        # Save the book in md format
        # Corrected saving the book with the specified time
        desired_time = datetime.now(timezone(timedelta(hours=-5)))  # EST timezone
        # Use the desired time as a seed for the random number generator
        random.seed(desired_time)
        # Generate a random 4-digit number
        random_number = random.randint(1000009, 9999999)
        # Ensure it's 4 digits long
        random_number = str(random_number).zfill(random.randint(7, 10))
        suffix = '_partial' if self.partial_content else ''
        path = filename or f'book{random_number}{suffix}.md'
        with open(path, 'w') as file:
            file.write(self.to_markdown())
        self.last_saved_path = path
        return path

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
        return paragraphs

    def get_paragraph(self, prompt, chapter_index, paragraph_index):
        prompt.append(self.get_message('user', f'!w {chapter_index + 1} {paragraph_index + 1}'))
        paragraph = self.get_response(prompt)
        prompt.append(self.get_message('assistant', paragraph))

        while len(paragraph.split(' ')) < int(self.paragraph_words[chapter_index][paragraph_index] * self.tolerance):
            prompt.append(self.get_message('system', '!c'))
            response = self.get_response(prompt)
            paragraph += response
            prompt.append(self.get_message('assistant', response))

        return paragraph

    @staticmethod
    def get_message(role, content):
        return {"role": role, "content": content}
      
    @staticmethod
    def convert_structure(structure):
        chapters = structure.split("Chapter")
        chapters = [x for x in chapters if x != '']
        chapter_information = []
        for chapter in chapters:
            chapter_lines = chapter.split("\n")
            if len(chapter_lines) > 1:
                chapter_title_line = chapter_lines[0]
                if 'paragraphs' in chapter_title_line.lower():
                    chapter_info = {'title': chapter_title_line.split('): ')[1], 'paragraphs': []}
                    for line in chapter_lines[1:]:
                        if 'paragraph' in line.lower():
                            words_info = line.split('(')[1].split(')')[0].split(' ')
                            if len(words_info) >= 2:
                                paragraph_title = line.split('): ')[1]
                                paragraph_words = words_info[0]
                                chapter_info['paragraphs'].append({'title': paragraph_title, 'words': paragraph_words})
                    chapter_information.append(chapter_info)
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

    def get_response(self, prompt: List[Dict[str, str]], max_retries: int = 5) -> str:
        retries = 0
        last_error: Optional[Exception] = None
        backend = self.llm_backend
        while retries < max_retries:
            try:
                if backend == 'ollama':
                    response = chat(prompt, options=self.ollama_options)
                elif backend == 'openai':
                    if openai is None:  # pragma: no cover - dependency guard
                        raise RuntimeError('openai package is not installed')
                    response = openai.ChatCompletion.create(  # type: ignore[attr-defined]
                        model=self.openai_model,
                        messages=prompt
                    )["choices"][0]["message"]["content"]
                else:
                    raise RuntimeError(f"Unsupported LLM backend: {backend}")

                with open("log.txt", "a") as f:
                    f.write(f"Prompt: {prompt}\nResponse: {response}\n\n")
                return response
            except OllamaError as exc:
                last_error = exc
            except Exception as exc:  # pragma: no cover - runtime/network failure
                last_error = exc

            retries += 1
            print(f"An error occurred: {last_error}. Retrying ({retries}/{max_retries})...")
            time.sleep(20)

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

    def _persist_partial_content(self, chapters: List[List[str]], error: Optional[Exception] = None) -> None:
        """Persist partial content to disk for recovery."""

        self.content = chapters
        self.partial_content = True
        path = self.save_book()
        message = f'Partial book saved to {path}.'
        if error is not None:
            message = f'{message} Reason: {error}'
        self.output(message)
