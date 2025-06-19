"""Book analyzer service for intelligent chapter detection and splitting."""

import logging
import re
from dataclasses import dataclass
from typing import ClassVar

logger = logging.getLogger(__name__)


@dataclass
class ChapterInfo:
    """Information about a detected chapter."""

    title: str
    start_position: int
    end_position: int
    chapter_number: int | None = None
    word_count: int = 0
    is_special: bool = False  # For prologue, epilogue, etc.


class BookAnalyzer:
    """Analyzes books to detect chapter boundaries and structure."""

    # Common chapter patterns
    CHAPTER_PATTERNS: ClassVar[list[tuple[str, str]]] = [
        # Numbered chapters (most specific first)
        (r"^Chapter\s+([IVX]+)(?:\s|$)", "roman"),
        (r"^CHAPTER\s+([IVX]+)(?:\s|$)", "roman"),
        (r"^Chapter\s+(\d+)(?:\s|$)", "numbered"),
        (r"^CHAPTER\s+(\d+)(?:\s|$)", "numbered"),
        (r"^Ch\.\s*(\d+)(?:\s|$)", "numbered"),
        (r"^(\d+)\.?\s*$", "numbered"),  # Just numbers
        # Special sections (before generic word chapters)
        (r"^(Prologue|PROLOGUE)(?:\s|$)", "special"),
        (r"^(Epilogue|EPILOGUE)(?:\s|$)", "special"),
        (r"^(Introduction|INTRODUCTION)(?:\s|$)", "special"),
        (r"^(Preface|PREFACE)(?:\s|$)", "special"),
        (r"^(Appendix|APPENDIX)(?:\s|$)", "special"),
        # Part markers
        (r"^Part\s+(\d+|[IVX]+|\w+)(?:\s|$)", "part"),
        (r"^PART\s+(\d+|[IVX]+|\w+)(?:\s|$)", "part"),
        # Book markers (for series)
        (r"^Book\s+(\d+|[IVX]+|\w+)(?:\s|$)", "book"),
        (r"^BOOK\s+(\d+|[IVX]+|\w+)(?:\s|$)", "book"),
        # Word chapters (last, as least specific)
        (r"^Chapter\s+(\w+)(?:\s|$)", "word"),
        (r"^CHAPTER\s+(\w+)(?:\s|$)", "word"),
    ]

    # Minimum and maximum chapter lengths
    MIN_CHAPTER_WORDS = 5  # Allow very short chapters for testing
    MAX_CHAPTER_WORDS = 15000  # Very long chapters should be split
    IDEAL_CHAPTER_WORDS = 5000  # Target for content-based splitting

    def __init__(self):
        self.compiled_patterns = [
            (re.compile(pattern, re.MULTILINE), pattern_type)
            for pattern, pattern_type in self.CHAPTER_PATTERNS
        ]

    def analyze_book(self, text: str) -> list[ChapterInfo]:
        """Analyze a book and return detected chapters."""
        logger.info("Starting book analysis")

        # First, try to detect explicit chapter markers
        chapters = self._detect_chapter_markers(text)

        if chapters:
            logger.info(f"Found {len(chapters)} chapters using markers")
            # Validate and adjust chapters
            chapters = self._validate_chapters(text, chapters)
        else:
            logger.info("No chapter markers found, using content-based splitting")
            # Fall back to content-based splitting
            chapters = self._content_based_split(text)

        # Calculate word counts for each chapter
        for chapter in chapters:
            chapter_text = text[chapter.start_position : chapter.end_position]
            chapter.word_count = len(chapter_text.split())

        logger.info(f"Analysis complete: {len(chapters)} chapters detected")
        return chapters

    def _detect_chapter_markers(self, text: str) -> list[ChapterInfo]:
        """Detect chapters using explicit markers."""
        chapters = []
        seen_positions = set()

        # Find all chapter markers in the text
        for pattern, pattern_type in self.compiled_patterns:
            for match in pattern.finditer(text):
                start_pos = match.start()

                # Skip if we've already found a chapter at this position
                if start_pos in seen_positions:
                    continue

                seen_positions.add(start_pos)
                title = match.group(0).strip()

                chapter_info = ChapterInfo(
                    title=title,
                    start_position=start_pos,
                    end_position=start_pos,  # Will be updated later
                    is_special=(pattern_type == "special"),
                )

                # Try to extract chapter number
                if pattern_type in ("numbered", "roman"):
                    try:
                        if pattern_type == "numbered":
                            chapter_info.chapter_number = int(match.group(1))
                        elif pattern_type == "roman":
                            chapter_info.chapter_number = self._roman_to_int(match.group(1))
                    except (ValueError, IndexError):
                        pass

                chapters.append(chapter_info)

        # Sort chapters by position
        chapters.sort(key=lambda c: c.start_position)

        # Update end positions
        for i in range(len(chapters)):
            if i < len(chapters) - 1:
                chapters[i].end_position = chapters[i + 1].start_position
            else:
                chapters[i].end_position = len(text)

        return chapters

    def _validate_chapters(self, text: str, chapters: list[ChapterInfo]) -> list[ChapterInfo]:
        """Validate detected chapters and handle edge cases."""
        validated = []

        for _i, chapter in enumerate(chapters):
            chapter_text = text[chapter.start_position : chapter.end_position]
            word_count = len(chapter_text.split())

            # Skip very short chapters (likely false positives)
            if word_count < self.MIN_CHAPTER_WORDS and not chapter.is_special:
                logger.warning(f"Skipping short chapter '{chapter.title}' with {word_count} words")
                continue

            # Handle very long chapters
            if word_count > self.MAX_CHAPTER_WORDS:
                logger.info(f"Splitting long chapter '{chapter.title}' with {word_count} words")
                # Split the chapter into smaller parts
                sub_chapters = self._split_long_chapter(
                    chapter_text, chapter.start_position, chapter.title
                )
                validated.extend(sub_chapters)
            else:
                validated.append(chapter)

        return validated

    def _split_long_chapter(
        self, text: str, start_position: int, original_title: str
    ) -> list[ChapterInfo]:
        """Split a long chapter into smaller parts."""
        parts = []
        words = text.split()
        total_words = len(words)

        # Calculate number of parts needed
        num_parts = (total_words // self.IDEAL_CHAPTER_WORDS) + 1
        words_per_part = total_words // num_parts

        current_pos = 0
        for i in range(num_parts):
            # Find a good breaking point (end of paragraph)
            start_word = i * words_per_part
            end_word = min((i + 1) * words_per_part, total_words)

            # Reconstruct text for this part
            part_words = words[start_word:end_word]
            part_text = " ".join(part_words)

            # Find the last paragraph break
            last_para = part_text.rfind("\n\n")
            if last_para > 0 and i < num_parts - 1:
                part_text = part_text[:last_para]
                # Adjust end_word
                end_word = start_word + len(part_text.split())

            part = ChapterInfo(
                title=f"{original_title} - Part {i + 1}",
                start_position=start_position + current_pos,
                end_position=start_position + current_pos + len(part_text),
                word_count=len(part_text.split()),
            )
            parts.append(part)
            current_pos += len(part_text) + 2  # +2 for paragraph break

        return parts

    def _content_based_split(self, text: str) -> list[ChapterInfo]:
        """Split text into chapters based on content when no markers are found."""
        chapters = []

        # Split by multiple newlines (potential section breaks)
        sections = re.split(r"\n{3,}", text)

        current_chapter_text = ""
        current_position = 0
        chapter_num = 1

        for section in sections:
            section = section.strip()
            if not section:
                continue

            # Check if adding this section would make the chapter too long
            combined_text = (
                current_chapter_text + "\n\n" + section if current_chapter_text else section
            )
            word_count = len(combined_text.split())

            if word_count > self.IDEAL_CHAPTER_WORDS and current_chapter_text:
                # Save current chapter
                chapter = ChapterInfo(
                    title=f"Chapter {chapter_num}",
                    start_position=current_position,
                    end_position=current_position + len(current_chapter_text),
                    chapter_number=chapter_num,
                    word_count=len(current_chapter_text.split()),
                )
                chapters.append(chapter)

                # Start new chapter
                chapter_num += 1
                current_position += len(current_chapter_text) + 3  # +3 for newlines
                current_chapter_text = section
            else:
                current_chapter_text = combined_text

        # Don't forget the last chapter
        if current_chapter_text:
            chapter = ChapterInfo(
                title=f"Chapter {chapter_num}",
                start_position=current_position,
                end_position=current_position + len(current_chapter_text),
                chapter_number=chapter_num,
                word_count=len(current_chapter_text.split()),
            )
            chapters.append(chapter)

        return chapters

    def _roman_to_int(self, roman: str) -> int:
        """Convert Roman numerals to integers."""
        roman_values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}

        total = 0
        prev_value = 0

        for char in reversed(roman.upper()):
            value = roman_values.get(char, 0)
            if value < prev_value:
                total -= value
            else:
                total += value
            prev_value = value

        return total
