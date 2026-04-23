"""Statis Pro Football Game Engine (5th Edition)."""
from .season import Season, SeasonGame, SeasonRoster, SeasonStats, TeamRecord
from .fac_deck import FACDeck, FACCard, DECK_SIZE, Z_CARD_COUNT
from .player_card import PlayerCard, Position, Grade, PASS_SLOTS, RUN_SLOTS, RECEIVER_LETTERS
from .card_generator import CardGenerator
from .charts import Charts
from .team import Team, Roster
from .play_resolver import PlayResolver, PlayResult, PENALTY_TABLE_5E, resolve_z_penalty
from .game import Game, GameState, DriveResult
from .solitaire import SolitaireAI
from .play_types import (
    DefensivePlay, DefensiveFormation, DefensiveStrategy,
    OffensivePlay, OffensiveStrategy, PlayerInvolved,
    DEFENSIVE_PLAY_NAMES, OFFENSIVE_PLAY_NAMES,
    OFFENSIVE_STRATEGY_NAMES, DEFENSIVE_STRATEGY_NAMES,
    PLAYER_INVOLVED_NAMES,
    LEGACY_FORMATION_TO_PLAY, LEGACY_FORMATION_TO_FORMATION,
    is_run_defense, is_pass_defense, is_run_play, is_pass_play,
    get_run_number_modifier_5e, get_completion_modifier_5e,
)
from .fac_distributions import (
    FORMATION_MODIFIERS,
    DEFENSIVE_PLAY_MODIFIERS,
    effective_pass_rush,
    effective_coverage,
    effective_run_stop,
    get_defensive_play_modifier,
    PASS_SLOT_COUNT,
    RUN_SLOT_COUNT,
)

__all__ = [
    "FACDeck", "FACCard", "DECK_SIZE", "Z_CARD_COUNT",
    "PlayerCard", "Position", "Grade",
    "PASS_SLOTS", "RUN_SLOTS", "RECEIVER_LETTERS",
    "CardGenerator",
    "Charts",
    "Team", "Roster",
    "PlayResolver", "PlayResult", "PENALTY_TABLE_5E", "resolve_z_penalty",
    "Game", "GameState", "DriveResult",
    "SolitaireAI",
    "DefensivePlay", "DefensiveFormation", "DefensiveStrategy",
    "OffensivePlay", "OffensiveStrategy", "PlayerInvolved",
    "DEFENSIVE_PLAY_NAMES", "OFFENSIVE_PLAY_NAMES",
    "OFFENSIVE_STRATEGY_NAMES", "DEFENSIVE_STRATEGY_NAMES",
    "PLAYER_INVOLVED_NAMES",
    "LEGACY_FORMATION_TO_PLAY", "LEGACY_FORMATION_TO_FORMATION",
    "is_run_defense", "is_pass_defense", "is_run_play", "is_pass_play",
    "get_run_number_modifier_5e", "get_completion_modifier_5e",
    "FORMATION_MODIFIERS", "DEFENSIVE_PLAY_MODIFIERS",
    "effective_pass_rush", "effective_coverage", "effective_run_stop",
    "get_defensive_play_modifier",
    "PASS_SLOT_COUNT", "RUN_SLOT_COUNT",
    "Season", "SeasonGame", "SeasonRoster", "SeasonStats", "TeamRecord",
]
