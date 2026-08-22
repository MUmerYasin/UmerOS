# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Dict Manager — Word Lists (/usr/share/dict)

FHS 3.0 Section 4.11.5: Word lists for spell checkers and look(1).

Manages:
- english, american-english, british-english (default word lists)
- Other language word lists (french, german, spanish, etc.)
- Word list lookup and management
- Character set validation (UTF-8 preferred)
"""

import os
import re
from enum import Enum, IntEnum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from pathlib import Path


class WordListType(Enum):
    """Types of word lists."""
    ENGLISH = "english"
    AMERICAN_ENGLISH = "american-english"
    BRITISH_ENGLISH = "british-english"
    FRENCH = "french"
    GERMAN = "german"
    SPANISH = "spanish"
    ITALIAN = "italian"
    PORTUGUESE = "portuguese"
    DUTCH = "dutch"
    RUSSIAN = "russian"
    JAPANESE = "japanese"
    CHINESE = "chinese"
    KOREAN = "korean"
    ARABIC = "arabic"
    HINDI = "hindi"
    TURKISH = "turkish"
    POLISH = "polish"
    SWEDISH = "swedish"
    DANISH = "danish"
    NORWEGIAN = "norwegian"
    FINNISH = "finnish"
    CZECH = "czech"
    ROMANIAN = "romanian"
    HUNGARIAN = "hungarian"
    GREEK = "greek"
    HEBREW = "hebrew"
    THAI = "thai"
    VIETNAMESE = "vietnamese"
    INDONESIAN = "indonesian"
    MALAY = "malay"
    CUSTOM = "custom"


class CharacterEncoding(IntEnum):
    """Character encoding types for word lists."""
    ASCII = 0
    ISO_8859_1 = 1
    ISO_8859_2 = 2
    ISO_8859_3 = 3
    ISO_8859_4 = 4
    ISO_8859_5 = 5
    ISO_8859_6 = 6
    ISO_8859_7 = 7
    ISO_8859_8 = 8
    ISO_8859_9 = 9
    ISO_8859_10 = 10
    ISO_8859_13 = 13
    ISO_8859_14 = 14
    ISO_8859_15 = 15
    ISO_8859_16 = 16
    UTF_8 = 65001
    UTF_16 = 1200
    UTF_16LE = 1200
    UTF_16BE = 1201
    UTF_32 = 12000
    UTF_32LE = 12001
    UTF_32BE = 12002


class WordListStatus(IntEnum):
    """Status of a word list."""
    MISSING = 0
    PRESENT = 1
    SYMLINK = 2
    EMPTY = 3
    CORRUPTED = 4


@dataclass
class WordList:
    """Represents a word list file."""
    name: str
    path: Path
    language_type: WordListType
    encoding: CharacterEncoding = CharacterEncoding.UTF_8
    word_count: int = 0
    file_size: int = 0
    status: WordListStatus = WordListStatus.MISSING
    is_symlink: bool = False
    symlink_target: Optional[str] = None
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": str(self.path),
            "language_type": self.language_type.value,
            "encoding": self.encoding.value,
            "word_count": self.word_count,
            "file_size": self.file_size,
            "status": self.status.value,
            "is_symlink": self.is_symlink,
            "symlink_target": self.symlink_target,
            "description": self.description
        }


class DictManager:
    """Manages /usr/share/dict word lists per FHS 3.0."""

    BASE_DIR = Path("/usr/share/dict")

    # Default word lists per FHS 3.0
    DEFAULT_WORD_LISTS = {
        "english": WordListType.ENGLISH,
        "american-english": WordListType.AMERICAN_ENGLISH,
        "british-english": WordListType.BRITISH_ENGLISH,
    }

    # Language to WordListType mapping
    LANGUAGE_MAP = {
        "english": WordListType.ENGLISH,
        "french": WordListType.FRENCH,
        "german": WordListType.GERMAN,
        "spanish": WordListType.SPANISH,
        "italian": WordListType.ITALIAN,
        "portuguese": WordListType.PORTUGUESE,
        "dutch": WordListType.DUTCH,
        "russian": WordListType.RUSSIAN,
        "japanese": WordListType.JAPANESE,
        "chinese": WordListType.CHINESE,
        "korean": WordListType.KOREAN,
        "arabic": WordListType.ARABIC,
        "hindi": WordListType.HINDI,
        "turkish": WordListType.TURKISH,
        "polish": WordListType.POLISH,
        "swedish": WordListType.SWEDISH,
        "danish": WordListType.DANISH,
        "norwegian": WordListType.NORWEGIAN,
        "finnish": WordListType.FINNISH,
        "czech": WordListType.CZECH,
        "romanian": WordListType.ROMANIAN,
        "hungarian": WordListType.HUNGARIAN,
        "greek": WordListType.GREEK,
        "hebrew": WordListType.HEBREW,
        "thai": WordListType.THAI,
        "vietnamese": WordListType.VIETNAMESE,
        "indonesian": WordListType.INDONESIAN,
        "malay": WordListType.MALAY,
    }

    def __init__(self):
        self._word_lists: Dict[str, WordList] = {}
        self._refresh()

    def _refresh(self):
        """Refresh the word list cache."""
        self._word_lists.clear()
        self.BASE_DIR.mkdir(parents=True, exist_ok=True)

        for entry in self.BASE_DIR.iterdir():
            if entry.is_file() or entry.is_symlink():
                wl = self._create_word_list(entry)
                self._word_lists[entry.name] = wl

    def _create_word_list(self, path: Path) -> WordList:
        """Create a WordList object for a path."""
        name = path.name
        wl_type = self.LANGUAGE_MAP.get(name, WordListType.CUSTOM)
        encoding = self._detect_encoding(path)

        status = WordListStatus.MISSING
        is_symlink = path.is_symlink()
        symlink_target = None
        word_count = 0
        file_size = 0

        if is_symlink:
            status = WordListStatus.SYMLINK
            symlink_target = str(path.resolve())
        elif path.exists():
            if path.stat().st_size == 0:
                status = WordListStatus.EMPTY
            else:
                status = WordListStatus.PRESENT
                file_size = path.stat().st_size
                word_count = self._count_words(path)

        return WordList(
            name=name,
            path=path,
            language_type=wl_type,
            encoding=encoding,
            word_count=word_count,
            file_size=file_size,
            status=status,
            is_symlink=is_symlink,
            symlink_target=symlink_target
        )

    def _detect_encoding(self, path: Path) -> CharacterEncoding:
        """Detect encoding of a word list file."""
        try:
            if path.is_symlink():
                path = path.resolve()
            with open(path, 'rb') as f:
                raw = f.read(1024)
            if raw[:3] == b'\xef\xbb\xbf':
                return CharacterEncoding.UTF_8
            if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
                return CharacterEncoding.UTF_16
            if raw[:4] in (b'\xff\xfe\x00\x00', b'\x00\x00\xfe\xff'):
                return CharacterEncoding.UTF_32
            try:
                raw.decode('ascii')
                return CharacterEncoding.ASCII
            except UnicodeDecodeError:
                pass
            try:
                raw.decode('iso-8859-1')
                return CharacterEncoding.ISO_8859_1
            except UnicodeDecodeError:
                pass
            return CharacterEncoding.UTF_8
        except Exception:
            return CharacterEncoding.UTF_8

    def _count_words(self, path: Path) -> int:
        """Count words in a word list file."""
        try:
            if path.is_symlink():
                path = path.resolve()
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                return sum(1 for line in f if line.strip())
        except Exception:
            return 0

    def list_word_lists(self) -> List[WordList]:
        """List all word lists."""
        return list(self._word_lists.values())

    def get_word_list(self, name: str) -> Optional[WordList]:
        """Get a specific word list."""
        return self._word_lists.get(name)

    def has_word_list(self, name: str) -> bool:
        """Check if a word list exists."""
        return name in self._word_lists

    def add_word_list(self, name: str, language: str = "english") -> bool:
        """Add a new word list file."""
        try:
            wl_type = self.LANGUAGE_MAP.get(language, WordListType.CUSTOM)
            path = self.BASE_DIR / name
            path.touch()
            wl = self._create_word_list(path)
            wl.language_type = wl_type
            self._word_lists[name] = wl
            return True
        except Exception:
            return False

    def remove_word_list(self, name: str) -> bool:
        """Remove a word list."""
        try:
            path = self.BASE_DIR / name
            if path.exists():
                path.unlink()
            self._word_lists.pop(name, None)
            return True
        except Exception:
            return False

    def add_words(self, name: str, words: List[str]) -> bool:
        """Add words to a word list."""
        try:
            path = self.BASE_DIR / name
            with open(path, 'a', encoding='utf-8') as f:
                for word in words:
                    f.write(word.strip() + '\n')
            self._refresh()
            return True
        except Exception:
            return False

    def get_word_count(self, name: str) -> int:
        """Get word count for a word list."""
        wl = self.get_word_list(name)
        return wl.word_count if wl else 0

    def search_word(self, word: str) -> List[str]:
        """Search for word lists containing a specific word."""
        results = []
        for name, wl in self._word_lists.items():
            if wl.status in (WordListStatus.MISSING, WordListStatus.EMPTY):
                continue
            try:
                path = wl.path
                if path.is_symlink():
                    path = path.resolve()
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        if line.strip() == word:
                            results.append(name)
                            break
            except Exception:
                continue
        return results

    def get_status(self) -> Dict[str, Any]:
        """Get dict manager status."""
        present = sum(1 for wl in self._word_lists.values()
                      if wl.status == WordListStatus.PRESENT)
        empty = sum(1 for wl in self._word_lists.values()
                    if wl.status == WordListStatus.EMPTY)
        symlinks = sum(1 for wl in self._word_lists.values()
                       if wl.status == WordListStatus.SYMLINK)
        total_words = sum(wl.word_count for wl in self._word_lists.values())

        return {
            "base_dir": str(self.BASE_DIR),
            "exists": self.BASE_DIR.exists(),
            "total_word_lists": len(self._word_lists),
            "present": present,
            "empty": empty,
            "symlinks": symlinks,
            "total_words": total_words,
            "word_lists": {name: wl.to_dict() for name, wl in self._word_lists.items()}
        }


# Singleton instance
dict_manager = DictManager()
