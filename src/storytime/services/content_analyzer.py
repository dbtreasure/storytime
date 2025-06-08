"""Content analysis service for automatic job type detection and text processing."""

import re
import logging
from typing import Any

from storytime.models import ContentAnalysisResult, JobType, SourceType

logger = logging.getLogger(__name__)


class ContentAnalyzer:
    """Service for analyzing content and determining appropriate processing strategies."""
    
    def __init__(self):
        # Patterns for detecting dialogue and character speech
        self.dialogue_patterns = [
            r'"[^"]*"',  # Double quoted speech
            r"'[^']*'",  # Single quoted speech  
            r'"[^"]*"',  # Smart quotes
            r'—[^—]*—',  # Em dash dialogue
        ]
        
        # Patterns for chapter detection
        self.chapter_patterns = [
            r'^chapter\s+\d+',
            r'^ch\.\s*\d+',
            r'^\d+\.',
            r'^[IVX]+\.',  # Roman numerals
        ]
        
        # Minimum lengths for different processing types
        self.single_voice_max_length = 5000  # Characters
        self.chapter_min_length = 1000      # Characters
        
    async def analyze_content(
        self, 
        content: str, 
        source_type: SourceType = SourceType.TEXT
    ) -> ContentAnalysisResult:
        """Analyze content and suggest appropriate job type."""
        logger.info(f"Analyzing content of length {len(content)} with source_type {source_type}")
        
        features = await self._extract_features(content)
        suggested_type, confidence, reasons = await self._determine_job_type(features, source_type)
        estimated_time = await self._estimate_processing_time(content, suggested_type)
        
        return ContentAnalysisResult(
            suggested_job_type=suggested_type,
            confidence=confidence,
            reasons=reasons,
            detected_features=features,
            estimated_processing_time=estimated_time
        )
    
    async def split_book_into_chapters(self, content: str) -> list[str]:
        """Split book content into individual chapters."""
        logger.info(f"Splitting book content of length {len(content)} into chapters")
        
        chapters = []
        
        # Try to find chapter boundaries
        chapter_boundaries = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            line_clean = line.strip().lower()
            
            # Check if line matches chapter pattern
            for pattern in self.chapter_patterns:
                if re.match(pattern, line_clean):
                    chapter_boundaries.append(i)
                    break
        
        if not chapter_boundaries:
            # No clear chapter structure found, split by length
            logger.info("No chapter structure detected, splitting by length")
            return await self._split_by_length(content)
        
        # Split content at chapter boundaries
        for i, start_line in enumerate(chapter_boundaries):
            end_line = chapter_boundaries[i + 1] if i + 1 < len(chapter_boundaries) else len(lines)
            
            chapter_lines = lines[start_line:end_line]
            chapter_content = '\n'.join(chapter_lines).strip()
            
            if len(chapter_content) > self.chapter_min_length:
                chapters.append(chapter_content)
            elif chapters:  # Append to previous chapter if too short
                chapters[-1] += '\n\n' + chapter_content
        
        logger.info(f"Split content into {len(chapters)} chapters")
        return chapters
    
    async def _extract_features(self, content: str) -> dict[str, str]:
        """Extract features from content for analysis."""
        features = {}
        
        # Basic metrics
        features["length"] = str(len(content))
        features["word_count"] = str(len(content.split()))
        features["line_count"] = str(len(content.split('\n')))
        features["paragraph_count"] = str(len([p for p in content.split('\n\n') if p.strip()]))
        
        # Dialogue detection
        dialogue_matches = 0
        for pattern in self.dialogue_patterns:
            dialogue_matches += len(re.findall(pattern, content))
        
        features["dialogue_count"] = str(dialogue_matches)
        features["dialogue_ratio"] = str(round(dialogue_matches / max(1, len(content.split())), 3))
        
        # Character name patterns (simple heuristic)
        # Look for capitalized words that might be character names
        capitalized_words = re.findall(r'\b[A-Z][a-z]+\b', content)
        unique_caps = set(capitalized_words)
        features["potential_character_count"] = str(len(unique_caps))
        
        # Chapter detection
        chapter_indicators = 0
        for pattern in self.chapter_patterns:
            chapter_indicators += len(re.findall(pattern, content, re.IGNORECASE | re.MULTILINE))
        
        features["chapter_indicators"] = str(chapter_indicators)
        
        # Document structure indicators
        features["has_table_of_contents"] = str(
            bool(re.search(r'table\s+of\s+contents|contents', content, re.IGNORECASE))
        )
        features["has_title_page"] = str(
            bool(re.search(r'^\s*[A-Z\s]{10,}\s*$', content, re.MULTILINE))
        )
        
        # Technical content detection
        features["has_code_blocks"] = str(
            bool(re.search(r'```|<code>|def\s+\w+|class\s+\w+', content))
        )
        features["has_markdown"] = str(
            bool(re.search(r'#{1,6}\s|^\*\s|\[.*\]\(.*\)', content, re.MULTILINE))
        )
        
        return features
    
    async def _determine_job_type(
        self, 
        features: dict[str, str], 
        source_type: SourceType
    ) -> tuple[JobType, float, list[str]]:
        """Determine appropriate job type based on features."""
        reasons = []
        confidence = 0.5  # Base confidence
        
        length = int(features.get("length", "0"))
        dialogue_count = int(features.get("dialogue_count", "0"))
        dialogue_ratio = float(features.get("dialogue_ratio", "0"))
        chapter_indicators = int(features.get("chapter_indicators", "0"))
        potential_characters = int(features.get("potential_character_count", "0"))
        
        # Simple content -> SINGLE_VOICE
        if length <= self.single_voice_max_length:
            reasons.append(f"Short content ({length} chars) suitable for single voice")
            confidence += 0.3
            return JobType.SINGLE_VOICE, min(confidence, 0.95), reasons
        
        # Book with chapters -> BOOK_PROCESSING
        if chapter_indicators > 1 and source_type == SourceType.BOOK:
            reasons.append(f"Detected {chapter_indicators} chapter indicators")
            confidence += 0.4
            return JobType.BOOK_PROCESSING, min(confidence, 0.95), reasons
        
        # High dialogue content -> MULTI_VOICE
        if dialogue_count > 10 and dialogue_ratio > 0.1:
            reasons.append(f"High dialogue content ({dialogue_count} instances, {dialogue_ratio:.1%} ratio)")
            confidence += 0.3
            
        if potential_characters > 5:
            reasons.append(f"Multiple potential characters detected ({potential_characters})")
            confidence += 0.2
            
        # Technical content usually stays single voice
        if features.get("has_code_blocks") == "True" or features.get("has_markdown") == "True":
            reasons.append("Technical content detected, using single voice")
            return JobType.SINGLE_VOICE, min(confidence + 0.2, 0.9), reasons
        
        # Default decision based on dialogue content
        if dialogue_count > 5 or dialogue_ratio > 0.05:
            reasons.append("Sufficient dialogue detected for multi-voice processing")
            return JobType.MULTI_VOICE, min(confidence, 0.85), reasons
        else:
            reasons.append("Limited dialogue, using single voice")
            return JobType.SINGLE_VOICE, min(confidence, 0.8), reasons
    
    async def _estimate_processing_time(self, content: str, job_type: JobType) -> int:
        """Estimate processing time in seconds based on content and job type."""
        word_count = len(content.split())
        
        # Base time estimates (seconds per word)
        time_per_word = {
            JobType.SINGLE_VOICE: 0.1,      # ~6 words per second
            JobType.MULTI_VOICE: 0.3,       # ~3 words per second (more complex)
            JobType.CHAPTER_PARSING: 0.05,  # ~20 words per second (parsing only)
            JobType.BOOK_PROCESSING: 0.4,   # ~2.5 words per second (most complex)
        }
        
        base_time = word_count * time_per_word.get(job_type, 0.2)
        
        # Add overhead for setup and finalization
        overhead = {
            JobType.SINGLE_VOICE: 30,       # 30 seconds
            JobType.MULTI_VOICE: 120,       # 2 minutes
            JobType.CHAPTER_PARSING: 60,    # 1 minute
            JobType.BOOK_PROCESSING: 300,   # 5 minutes
        }
        
        total_time = int(base_time + overhead.get(job_type, 60))
        
        # Minimum processing time
        return max(total_time, 10)
    
    async def _split_by_length(self, content: str, max_chunk_size: int = 50000) -> list[str]:
        """Split content by length when no clear structure is found."""
        chunks = []
        
        # Try to split at paragraph boundaries first
        paragraphs = content.split('\n\n')
        current_chunk = ""
        
        for paragraph in paragraphs:
            if len(current_chunk) + len(paragraph) <= max_chunk_size:
                current_chunk += paragraph + '\n\n'
            else:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = paragraph + '\n\n'
        
        # Add final chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        # If still too large, split at sentence boundaries
        final_chunks = []
        for chunk in chunks:
            if len(chunk) <= max_chunk_size:
                final_chunks.append(chunk)
            else:
                # Split large chunks at sentence boundaries
                sentences = re.split(r'[.!?]+\s+', chunk)
                current_subchunk = ""
                
                for sentence in sentences:
                    if len(current_subchunk) + len(sentence) <= max_chunk_size:
                        current_subchunk += sentence + '. '
                    else:
                        if current_subchunk.strip():
                            final_chunks.append(current_subchunk.strip())
                        current_subchunk = sentence + '. '
                
                if current_subchunk.strip():
                    final_chunks.append(current_subchunk.strip())
        
        return final_chunks