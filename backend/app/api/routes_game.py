from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.models.game import Game, TurnSnapshot
from app.schemas.game import (
    GameCreateRequest,
    GameDetailResponse,
    GameSummaryResponse,
    SnapshotResponse,
    TurnRequest,
)
from app.services.ai_client import call_openai_chat, enforce_turn_budget

router = APIRouter(prefix="/api", tags=["game"])


SYSTEM_PROMPT = (
    "You are an SLG campaign engine. "
    "Always return strict JSON only. "
    "Your response must include storyline progression, NPC behaviors, strategic advice, and dynamic events."
)


def to_iso(dt):
    return dt.astimezone(timezone.utc).isoformat()


@router.get("/health")
def health_check():
    return {"status": "ok", "service": settings.app_name}


@router.get("/budget")
def get_budget():
    return {
        "turn_token_budget": settings.turn_token_budget,
        "turn_output_max_tokens": settings.turn_output_max_tokens,
        "model": settings.openai_model,
    }


@router.post("/games", response_model=GameDetailResponse)
async def create_game(payload: GameCreateRequest, db: Session = Depends(get_db)):
    preferences = payload.preferences.model_dump()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Create an SLG opening. Return JSON with keys: "
                "intro, factions, objectives, state_summary, current_situation, suggested_actions.\n"
                f"Player preferences: {preferences}"
            ),
        },
    ]

    output_max = min(settings.turn_output_max_tokens, settings.turn_token_budget)
    enforce_turn_budget(messages, output_max)
    ai_result = await call_openai_chat(messages, max_tokens=output_max)

    world_state = {
        "intro": ai_result.get("intro", ""),
        "factions": ai_result.get("factions", []),
        "objectives": ai_result.get("objectives", []),
        "state_summary": ai_result.get("state_summary", ""),
        "current_situation": ai_result.get("current_situation", ""),
        "suggested_actions": ai_result.get("suggested_actions", []),
    }

    game = Game(
        player_id=payload.player_id,
        title=payload.title,
        preferences=preferences,
        world_state=world_state,
        turn_count=0,
    )
    db.add(game)
    db.flush()

    snapshot = TurnSnapshot(
        game_id=game.id,
        turn_index=0,
        player_action="[system_init]",
        ai_response=world_state,
    )
    db.add(snapshot)
    db.commit()
    db.refresh(game)

    return GameDetailResponse(
        id=game.id,
        player_id=game.player_id,
        title=game.title,
        turn_count=game.turn_count,
        preferences=game.preferences,
        world_state=game.world_state,
        created_at=to_iso(game.created_at),
        updated_at=to_iso(game.updated_at),
    )


@router.get("/games", response_model=list[GameSummaryResponse])
def list_games(player_id: str = Query(...), db: Session = Depends(get_db)):
    stmt = select(Game).where(Game.player_id == player_id).order_by(desc(Game.updated_at))
    rows = db.execute(stmt).scalars().all()
    return [
        GameSummaryResponse(
            id=g.id,
            player_id=g.player_id,
            title=g.title,
            turn_count=g.turn_count,
            created_at=to_iso(g.created_at),
            updated_at=to_iso(g.updated_at),
        )
        for g in rows
    ]


@router.get("/games/{game_id}", response_model=GameDetailResponse)
def get_game(game_id: str, player_id: str = Query(...), db: Session = Depends(get_db)):
    game = db.get(Game, game_id)
    if not game or game.player_id != player_id:
        raise HTTPException(status_code=404, detail="Game not found")
    return GameDetailResponse(
        id=game.id,
        player_id=game.player_id,
        title=game.title,
        turn_count=game.turn_count,
        preferences=game.preferences,
        world_state=game.world_state,
        created_at=to_iso(game.created_at),
        updated_at=to_iso(game.updated_at),
    )


@router.get("/games/{game_id}/snapshots", response_model=list[SnapshotResponse])
def list_snapshots(game_id: str, player_id: str = Query(...), db: Session = Depends(get_db)):
    game = db.get(Game, game_id)
    if not game or game.player_id != player_id:
        raise HTTPException(status_code=404, detail="Game not found")

    stmt = (
        select(TurnSnapshot)
        .where(TurnSnapshot.game_id == game_id)
        .order_by(TurnSnapshot.turn_index.asc(), TurnSnapshot.id.asc())
    )
    rows = db.execute(stmt).scalars().all()
    return [
        SnapshotResponse(
            turn_index=s.turn_index,
            player_action=s.player_action,
            ai_response=s.ai_response,
            created_at=to_iso(s.created_at),
        )
        for s in rows
    ]


@router.post("/games/{game_id}/turn", response_model=GameDetailResponse)
async def play_turn(game_id: str, payload: TurnRequest, db: Session = Depends(get_db)):
    game = db.get(Game, game_id)
    if not game or game.player_id != payload.player_id:
        raise HTTPException(status_code=404, detail="Game not found")

    history_stmt = (
        select(TurnSnapshot)
        .where(TurnSnapshot.game_id == game_id)
        .order_by(TurnSnapshot.turn_index.desc(), TurnSnapshot.id.desc())
        .limit(10)
    )
    history = list(reversed(db.execute(history_stmt).scalars().all()))

    output_max = min(settings.turn_output_max_tokens, settings.turn_token_budget)
    ai_result = None
    for keep_turns in range(len(history), -1, -1):
        selected = history[-keep_turns:] if keep_turns > 0 else []
        history_text = "\n".join(
            f"Turn {h.turn_index} | player: {h.player_action} | ai: {h.ai_response}"
            for h in selected
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Advance this SLG one turn. Return JSON with keys: "
                    "narrative, events, resource_changes, diplomacy_changes, risks, state_summary, next_options.\n"
                    f"Preferences: {game.preferences}\n"
                    f"Current state: {game.world_state}\n"
                    f"Recent history: {history_text}\n"
                    f"Player action this turn: {payload.action}"
                ),
            },
        ]
        try:
            enforce_turn_budget(messages, output_max)
        except HTTPException:
            continue
        ai_result = await call_openai_chat(messages, max_tokens=output_max)
        break

    if ai_result is None:
        raise HTTPException(
            status_code=400,
            detail="Turn context is too large for budget; please shorten action text.",
        )

    game.turn_count += 1
    game.world_state = {
        **game.world_state,
        "state_summary": ai_result.get("state_summary", game.world_state.get("state_summary", "")),
        "suggested_actions": ai_result.get("next_options", game.world_state.get("suggested_actions", [])),
        "last_turn": ai_result,
    }

    snapshot = TurnSnapshot(
        game_id=game.id,
        turn_index=game.turn_count,
        player_action=payload.action,
        ai_response=ai_result,
    )

    db.add(snapshot)
    db.add(game)
    db.commit()
    db.refresh(game)

    return GameDetailResponse(
        id=game.id,
        player_id=game.player_id,
        title=game.title,
        turn_count=game.turn_count,
        preferences=game.preferences,
        world_state=game.world_state,
        created_at=to_iso(game.created_at),
        updated_at=to_iso(game.updated_at),
    )
