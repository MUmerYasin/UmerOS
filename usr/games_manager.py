"""
UmerOS Games Manager (/usr/games)
==================================
System games and entertainment programs.

  Filesystem Hierarchy - /usr/games
  /usr/games contains recreational and educational games
  installed on the system. These range from classic text-based
  games to more complex graphical games.

UmerOS Virtualization:
  /usr/games provides a collection of UmerOS system games,
  including classic text adventures, puzzles, trivia, and
  strategy games that demonstrate UmerOS capabilities while
  providing entertainment.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional, Set


# ─── Constants ───────────────────────────────────────────────────────────────

GAMES_PATH = "/usr/games"

# Game categories
GAME_CATEGORIES = {
    "text_adventure": ["adventure", "interactive-fiction", "mud", "roguelike"],
    "puzzle": ["logic", "sudoku", "chess", "checkers", "backgammon"],
    "trivia": ["quiz", "knowledge", "general", "specialized"],
    "strategy": ["board", "card", "turn-based", "real-time"],
    "arcade": ["classic", "puzzle", "action", "simulation"],
    "simulation": ["life", "city", "flight", "economic"],
    "gambling": ["slots", "poker", "blackjack", "roulette"],
    "educational": ["math", "language", "science", "history"],
}

# Classic UmerOS games
DEFAULT_GAMES = {
    "adventure": {
        "name": "UmerOS Adventure",
        "category": "text_adventure",
        "description": "Classic text adventure in the UmerOS universe",
        "multiplayer": False,
        "high_score_enabled": True,
    },
    "chess": {
        "name": "UmerOS Chess",
        "category": "strategy",
        "description": "Strategic board game against AI or human",
        "multiplayer": True,
        "high_score_enabled": False,
    },
    "sudoku": {
        "name": "UmerOS Sudoku",
        "category": "puzzle",
        "description": "Logic-based number placement puzzle",
        "multiplayer": False,
        "high_score_enabled": True,
    },
    "trivia": {
        "name": "UmerOS Trivia",
        "category": "trivia",
        "description": "Knowledge quiz about UmerOS and computing",
        "multiplayer": True,
        "high_score_enabled": True,
    },
    "life": {
        "name": "UmerOS Life",
        "category": "simulation",
        "description": "Conway's Game of Life implementation",
        "multiplayer": False,
        "high_score_enabled": False,
    },
    "snake": {
        "name": "UmerOS Snake",
        "category": "arcade",
        "description": "Classic snake game with increasing speed",
        "multiplayer": False,
        "high_score_enabled": True,
    },
}


# ─── Enums ───────────────────────────────────────────────────────────────────

class GameCategory(IntEnum):
    """Game categories."""
    TEXT_ADVENTURE = 1
    PUZZLE = 2
    TRIVIA = 3
    STRATEGY = 4
    ARCADE = 5
    SIMULATION = 6
    GAMBLING = 7
    EDUCATIONAL = 8
    OTHER = 9


class GameState(IntEnum):
    """Game states."""
    NOT_STARTED = 1
    IN_PROGRESS = 2
    PAUSED = 3
    COMPLETED = 4
    GAME_OVER = 5


class Difficulty(IntEnum):
    """Difficulty levels."""
    EASY = 1
    MEDIUM = 2
    HARD = 3
    EXPERT = 4


# ─── Data Structures ────────────────────────────────────────────────────────

@dataclass
class GameInfo:
    """Information about a game."""
    name: str
    display_name: str
    category: GameCategory
    description: str = ""
    version: str = "1.0"
    author: str = "UmerOS"
    multiplayer: bool = False
    high_score_enabled: bool = True
    supports_saves: bool = False
    installed: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "category": self.category.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "multiplayer": self.multiplayer,
            "high_score_enabled": self.high_score_enabled,
            "supports_saves": self.supports_saves,
            "installed": self.installed,
        }


@dataclass
class GameSession:
    """An active game session."""
    session_id: str
    game_name: str
    player: str
    state: GameState = GameState.NOT_STARTED
    score: int = 0
    moves: int = 0
    time_played: float = 0.0
    difficulty: Difficulty = Difficulty.MEDIUM
    started_at: float = 0.0
    last_move_at: float = 0.0
    game_data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.started_at == 0.0:
            self.started_at = time.time()
        if self.last_move_at == 0.0:
            self.last_move_at = time.time()

    def elapsed_time(self) -> float:
        return time.time() - self.started_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "game_name": self.game_name,
            "player": self.player,
            "state": self.state.name,
            "score": self.score,
            "moves": self.moves,
            "time_played": self.elapsed_time(),
            "difficulty": self.difficulty.name,
            "started_at": self.started_at,
        }


@dataclass
class HighScore:
    """A high score entry."""
    player: str
    score: int
    game_name: str
    difficulty: Difficulty = Difficulty.MEDIUM
    achieved_at: float = 0.0
    time_played: float = 0.0

    def __post_init__(self) -> None:
        if self.achieved_at == 0.0:
            self.achieved_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "player": self.player,
            "score": self.score,
            "game_name": self.game_name,
            "difficulty": self.difficulty.name,
            "achieved_at": self.achieved_at,
            "time_played": self.time_played,
        }


@dataclass
class GameStats:
    """Player statistics for a game."""
    player: str
    games_played: int = 0
    games_won: int = 0
    games_lost: int = 0
    total_score: int = 0
    total_time: float = 0.0
    best_score: int = 0
    current_streak: int = 0
    best_streak: int = 0
    favorite_game: str = ""
    last_played: float = 0.0

    def win_rate(self) -> float:
        if self.games_played == 0:
            return 0.0
        return self.games_won / self.games_played * 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "player": self.player,
            "games_played": self.games_played,
            "games_won": self.games_won,
            "games_lost": self.games_lost,
            "win_rate": self.win_rate(),
            "total_score": self.total_score,
            "total_time": self.total_time,
            "best_score": self.best_score,
            "current_streak": self.current_streak,
            "best_streak": self.best_streak,
            "favorite_game": self.favorite_game,
            "last_played": self.last_played,
        }


@dataclass
class Leaderboard:
    """Leaderboard for a game."""
    game_name: str
    entries: List[HighScore] = field(default_factory=list)
    last_updated: float = 0.0

    def add_entry(self, entry: HighScore) -> None:
        self.entries.append(entry)
        self.entries.sort(key=lambda e: e.score, reverse=True)
        self.entries = self.entries[:100]
        self.last_updated = time.time()

    def get_top(self, count: int = 10) -> List[HighScore]:
        return self.entries[:count]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_name": self.game_name,
            "entry_count": len(self.entries),
            "last_updated": self.last_updated,
            "top_entries": [e.to_dict() for e in self.get_top()],
        }


# ─── Games Manager ──────────────────────────────────────────────────────────

class GamesManager:
    """
    Manages /usr/games - System Games.

    Responsibilities:
        - Track installed games and their metadata
        - Manage game sessions and state
        - Handle high scores and leaderboards
        - Track player statistics
        - Provide game discovery and search
        - Support multiplayer session coordination
        - Handle difficulty and configuration settings
    """

    def __init__(self) -> None:
        self._games: Dict[str, GameInfo] = {}
        self._sessions: Dict[str, GameSession] = {}
        self._high_scores: Dict[str, Leaderboard] = {}
        self._player_stats: Dict[str, Dict[str, GameStats]] = {}
        self._active_session: Optional[str] = None
        self._initialized = False

    def initialize(self) -> None:
        """Initialize games manager with default games."""
        if self._initialized:
            return
        self._load_default_games()
        self._initialized = True

    def _load_default_games(self) -> None:
        """Load default UmerOS games."""
        for name, info in DEFAULT_GAMES.items():
            self._games[name] = GameInfo(
                name=name,
                display_name=info["name"],
                category=GameCategory[info["category"].upper()],
                description=info["description"],
                multiplayer=info["multiplayer"],
                high_score_enabled=info["high_score_enabled"],
            )

    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        import uuid
        return uuid.uuid4().hex[:8]

    # ─── Game Management ─────────────────────────────────────────────────

    def get_game(self, name: str) -> Optional[GameInfo]:
        """Get game by name."""
        return self._games.get(name)

    def list_games(self, category: Optional[GameCategory] = None) -> List[GameInfo]:
        """List all games, optionally filtered by category."""
        if category:
            return [g for g in self._games.values() if g.category == category]
        return list(self._games.values())

    def find_games(self, query: str) -> List[GameInfo]:
        """Find games matching query."""
        query_lower = query.lower()
        return [g for g in self._games.values()
                if query_lower in g.name.lower() or query_lower in g.description.lower()]

    def install_game(self, name: str) -> bool:
        """Install a game."""
        game = self._games.get(name)
        if game:
            game.installed = True
            return True
        return False

    def uninstall_game(self, name: str) -> bool:
        """Uninstall a game."""
        game = self._games.get(name)
        if game:
            game.installed = False
            return True
        return False

    # ─── Session Management ──────────────────────────────────────────────

    def start_session(
        self,
        game_name: str,
        player: str,
        difficulty: Difficulty = Difficulty.MEDIUM,
    ) -> GameSession:
        """Start a new game session."""
        game = self._games.get(game_name)
        if not game:
            raise ValueError(f"Game '{game_name}' not found")
        if not game.installed:
            raise RuntimeError(f"Game '{game_name}' is not installed")

        session_id = self._generate_session_id()
        session = GameSession(
            session_id=session_id,
            game_name=game_name,
            player=player,
            difficulty=difficulty,
        )
        session.state = GameState.IN_PROGRESS
        self._sessions[session_id] = session
        self._active_session = session_id
        return session

    def get_session(self, session_id: str) -> Optional[GameSession]:
        """Get session by ID."""
        return self._sessions.get(session_id)

    def pause_session(self, session_id: str) -> bool:
        """Pause a game session."""
        session = self._sessions.get(session_id)
        if session and session.state == GameState.IN_PROGRESS:
            session.state = GameState.PAUSED
            return True
        return False

    def resume_session(self, session_id: str) -> bool:
        """Resume a paused game session."""
        session = self._sessions.get(session_id)
        if session and session.state == GameState.PAUSED:
            session.state = GameState.IN_PROGRESS
            return True
        return False

    def end_session(self, session_id: str, final_score: int = 0) -> bool:
        """End a game session."""
        session = self._sessions.get(session_id)
        if not session:
            return False
        session.state = GameState.COMPLETED
        session.score = final_score
        if session.game_name in self._high_scores and final_score > 0:
            entry = HighScore(
                player=session.player,
                score=final_score,
                game_name=session.game_name,
                difficulty=session.difficulty,
                time_played=session.elapsed_time(),
            )
            self._high_scores[session.game_name].add_entry(entry)
        self._update_player_stats(session)
        if self._active_session == session_id:
            self._active_session = None
        return True

    def update_score(self, session_id: str, score: int) -> bool:
        """Update score for a session."""
        session = self._sessions.get(session_id)
        if session and session.state == GameState.IN_PROGRESS:
            session.score = score
            session.last_move_at = time.time()
            session.moves += 1
            return True
        return False

    def get_active_session(self) -> Optional[GameSession]:
        """Get the currently active session."""
        if self._active_session:
            return self._sessions.get(self._active_session)
        return None

    def list_sessions(self, player: Optional[str] = None) -> List[GameSession]:
        """List sessions, optionally filtered by player."""
        if player:
            return [s for s in self._sessions.values() if s.player == player]
        return list(self._sessions.values())

    # ─── High Scores ─────────────────────────────────────────────────────

    def get_leaderboard(self, game_name: str) -> Optional[Leaderboard]:
        """Get leaderboard for a game."""
        if game_name not in self._high_scores:
            self._high_scores[game_name] = Leaderboard(game_name=game_name)
        return self._high_scores.get(game_name)

    def get_high_scores(self, game_name: str, count: int = 10) -> List[HighScore]:
        """Get top scores for a game."""
        leaderboard = self.get_leaderboard(game_name)
        if leaderboard:
            return leaderboard.get_top(count)
        return []

    def submit_score(
        self,
        game_name: str,
        player: str,
        score: int,
        difficulty: Difficulty = Difficulty.MEDIUM,
    ) -> bool:
        """Submit a score to the leaderboard."""
        leaderboard = self.get_leaderboard(game_name)
        if not leaderboard:
            return False
        entry = HighScore(
            player=player,
            score=score,
            game_name=game_name,
            difficulty=difficulty,
        )
        leaderboard.add_entry(entry)
        return True

    # ─── Player Statistics ───────────────────────────────────────────────

    def _update_player_stats(self, session: GameSession) -> None:
        """Update player statistics after a game."""
        player = session.player
        game_name = session.game_name

        if player not in self._player_stats:
            self._player_stats[player] = {}
        if game_name not in self._player_stats[player]:
            self._player_stats[player][game_name] = GameStats(player=player, favorite_game=game_name)

        stats = self._player_stats[player][game_name]
        stats.games_played += 1
        stats.total_score += session.score
        stats.total_time += session.elapsed_time()
        stats.last_played = time.time()

        if session.state == GameState.COMPLETED:
            stats.games_won += 1
            stats.current_streak += 1
            stats.best_streak = max(stats.best_streak, stats.current_streak)
        elif session.state == GameState.GAME_OVER:
            stats.games_lost += 1
            stats.current_streak = 0

        stats.best_score = max(stats.best_score, session.score)

    def get_player_stats(self, player: str, game_name: Optional[str] = None) -> List[GameStats]:
        """Get player statistics."""
        if player not in self._player_stats:
            return []
        if game_name:
            stats = self._player_stats[player].get(game_name)
            return [stats] if stats else []
        return list(self._player_stats[player].values())

    def get_player_overall_stats(self, player: str) -> Dict[str, Any]:
        """Get overall player statistics across all games."""
        if player not in self._player_stats:
            return {"player": player, "games_played": 0, "total_score": 0}

        stats = self._player_stats[player]
        total_played = sum(s.games_played for s in stats.values())
        total_won = sum(s.games_won for s in stats.values())
        total_score = sum(s.total_score for s in stats.values())
        total_time = sum(s.total_time for s in stats.values())

        return {
            "player": player,
            "games_played": total_played,
            "games_won": total_won,
            "games_lost": total_played - total_won,
            "win_rate": (total_won / total_played * 100) if total_played > 0 else 0,
            "total_score": total_score,
            "total_time": total_time,
            "games_tracked": len(stats),
        }

    # ─── Statistics ──────────────────────────────────────────────────────

    def get_statistics(self) -> Dict[str, Any]:
        """Get overall games statistics."""
        total_games = len(self._games)
        installed = sum(1 for g in self._games.values() if g.installed)
        by_category: Dict[str, int] = {}
        for game in self._games.values():
            cat_name = game.category.name
            by_category[cat_name] = by_category.get(cat_name, 0) + 1

        return {
            "total_games": total_games,
            "installed_games": installed,
            "total_sessions": len(self._sessions),
            "active_sessions": sum(1 for s in self._sessions.values() if s.state == GameState.IN_PROGRESS),
            "leaderboards": len(self._high_scores),
            "players": len(self._player_stats),
            "by_category": by_category,
        }

    def refresh(self) -> None:
        """Reset games manager."""
        self._games.clear()
        self._sessions.clear()
        self._high_scores.clear()
        self._player_stats.clear()
        self._active_session = None
        self._initialized = False
        self.initialize()


# ─── Global Singleton ────────────────────────────────────────────────────────

_global_games_manager: Optional[GamesManager] = None


def get_global_games_manager() -> GamesManager:
    """Get or create the global games manager."""
    global _global_games_manager
    if _global_games_manager is None:
        _global_games_manager = GamesManager()
        _global_games_manager.initialize()
    return _global_games_manager
