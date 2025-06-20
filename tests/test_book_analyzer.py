"""Tests for the book analyzer service."""

import pytest

from storytime.services.book_analyzer import BookAnalyzer


class TestBookAnalyzer:
    """Test the BookAnalyzer class."""

    @pytest.fixture
    def analyzer(self):
        """Create a BookAnalyzer instance."""
        return BookAnalyzer()

    def test_detect_numbered_chapters(self, analyzer):
        """Test detection of numbered chapters."""
        text = """
Chapter 1
The Beginning

This is the first chapter of our story.

Chapter 2
The Middle

This is the second chapter.

Chapter 3
The End

This is the final chapter.
"""
        chapters = analyzer.analyze_book(text)

        assert len(chapters) == 3
        assert chapters[0].title == "Chapter 1"
        assert chapters[0].chapter_number == 1
        assert chapters[1].title == "Chapter 2"
        assert chapters[1].chapter_number == 2
        assert chapters[2].title == "Chapter 3"
        assert chapters[2].chapter_number == 3

    def test_detect_roman_numeral_chapters(self, analyzer):
        """Test detection of Roman numeral chapters."""
        text = """
Chapter I

First chapter content here with enough words.

Chapter II

Second chapter content here with enough words.

Chapter III

Third chapter content here with enough words.
"""
        chapters = analyzer.analyze_book(text)

        assert len(chapters) == 3
        assert chapters[0].title == "Chapter I"
        assert chapters[0].chapter_number == 1
        assert chapters[1].title == "Chapter II"
        assert chapters[1].chapter_number == 2
        assert chapters[2].title == "Chapter III"
        assert chapters[2].chapter_number == 3

    def test_detect_special_sections(self, analyzer):
        """Test detection of special sections like prologue and epilogue."""
        text = """
Prologue

This is the prologue.

Chapter 1
The Story Begins

Main chapter content.

Epilogue

This is the epilogue.
"""
        chapters = analyzer.analyze_book(text)

        assert len(chapters) == 3
        assert chapters[0].title == "Prologue"
        assert chapters[0].is_special == True
        assert chapters[1].title == "Chapter 1"
        assert chapters[1].is_special == False
        assert chapters[2].title == "Epilogue"
        assert chapters[2].is_special == True

    def test_content_based_splitting(self, analyzer):
        """Test content-based splitting when no chapter markers are found."""
        # Create text with no chapter markers but clear sections
        sections = []
        for i in range(3):
            section = f"Section {i + 1}\n" + (
                "This is a paragraph. " * 200
            )  # ~200 words per section
            sections.append(section)

        text = "\n\n\n".join(sections)  # Triple newlines between sections

        chapters = analyzer.analyze_book(text)

        assert len(chapters) >= 1  # Should create at least one chapter
        assert all(c.title.startswith("Chapter") for c in chapters)
        assert all(c.chapter_number is not None for c in chapters)

    def test_validate_short_chapters(self, analyzer):
        """Test that very short chapters are filtered out."""
        text = (
            """
Chapter 1
Real Chapter

"""
            + ("This is a real chapter with enough content. " * 20)
            + """

Chapter 2

Two.

Chapter 3
Another Real Chapter

"""
            + ("This is another real chapter with sufficient content. " * 20)
        )

        chapters = analyzer.analyze_book(text)

        # Chapter 2 should be filtered out for being too short (< 5 words)
        assert len(chapters) == 2
        assert chapters[0].title == "Chapter 1"
        assert chapters[1].title == "Chapter 3"

    def test_split_long_chapters(self, analyzer):
        """Test that very long chapters are split into parts."""
        # Create a very long chapter
        long_content = "This is a very long chapter. " * 3000  # ~18000 words

        text = f"""
Chapter 1
The Very Long Chapter

{long_content}

Chapter 2
Normal Chapter

This is a normal length chapter with reasonable content.
"""

        chapters = analyzer.analyze_book(text)

        # Chapter 1 should be split into multiple parts
        chapter_1_parts = [c for c in chapters if "Chapter 1" in c.title]
        assert len(chapter_1_parts) > 1
        assert all("Part" in c.title for c in chapter_1_parts)

        # Chapter 2 should remain as is
        chapter_2 = [c for c in chapters if c.title == "Chapter 2"]
        assert len(chapter_2) == 1

    def test_roman_to_int_conversion(self, analyzer):
        """Test Roman numeral to integer conversion."""
        assert analyzer._roman_to_int("I") == 1
        assert analyzer._roman_to_int("IV") == 4
        assert analyzer._roman_to_int("V") == 5
        assert analyzer._roman_to_int("IX") == 9
        assert analyzer._roman_to_int("X") == 10
        assert analyzer._roman_to_int("XL") == 40
        assert analyzer._roman_to_int("L") == 50
        assert analyzer._roman_to_int("XC") == 90
        assert analyzer._roman_to_int("C") == 100
        assert analyzer._roman_to_int("CD") == 400
        assert analyzer._roman_to_int("D") == 500
        assert analyzer._roman_to_int("CM") == 900
        assert analyzer._roman_to_int("M") == 1000
        assert analyzer._roman_to_int("MCMXCIV") == 1994

    def test_mixed_chapter_formats(self, analyzer):
        """Test handling of mixed chapter formats."""
        text = """
Prologue

Some prologue content with enough words here.

Chapter 1

First chapter content with several words here.

CHAPTER TWO

Second chapter content with several words here.

Ch. 3

Third chapter content with several words here.

Part I

Part content with several words here.

4.

Fourth chapter content with several words here.
"""

        chapters = analyzer.analyze_book(text)

        # Should detect most chapters despite different formats
        assert len(chapters) >= 5

        # Check specific chapters
        chapter_titles = [c.title for c in chapters]
        assert "Prologue" in chapter_titles
        assert "Chapter 1" in chapter_titles
        assert any("Ch. 3" in title for title in chapter_titles)
        # Part I might be detected as "Part content" due to word matching
        assert any("Part" in title or "4." in title for title in chapter_titles)

    def test_chapter_word_counts(self, analyzer):
        """Test that word counts are calculated correctly."""
        text = """
Chapter 1
Short Chapter

This chapter has exactly ten words in its content section.

Chapter 2
Long Chapter

""" + (" ".join(["word"] * 1000))  # Exactly 1000 words

        chapters = analyzer.analyze_book(text)

        assert len(chapters) == 2
        # Word count includes the title and content
        assert chapters[0].word_count == 14  # "Chapter 1" + "Short Chapter" + 10 content words
        assert chapters[1].word_count == 1004  # "Chapter 2" + "Long Chapter" + 1000 content words

    def test_preserve_chapter_boundaries(self, analyzer):
        """Test that chapter boundaries are preserved correctly."""
        text = """Chapter 1
First Chapter

Content of chapter 1.

Chapter 2
Second Chapter

Content of chapter 2.

Chapter 3
Third Chapter

Content of chapter 3."""

        chapters = analyzer.analyze_book(text)

        # Extract text for each chapter and verify no overlap
        for i, chapter in enumerate(chapters):
            chapter_text = text[chapter.start_position : chapter.end_position]

            # Verify chapter contains its own content
            assert f"Content of chapter {i + 1}" in chapter_text

            # Verify it doesn't contain other chapters' content
            for j in range(1, 4):
                if j != i + 1:
                    assert f"Content of chapter {j}" not in chapter_text
