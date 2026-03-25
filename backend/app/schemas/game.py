from pydantic import BaseModel, Field


class Preferences(BaseModel):
    faction_style: str = Field(..., description="Faction preference")
    strategy_style: str = Field(..., description="Strategy preference")
    narrative_style: str = Field(..., description="Narrative preference")
    extra_notes: str = Field(default="", description="Extra notes")


class GameCreateRequest(BaseModel):
    player_id: str
    title: str = "My Campaign"
    preferences: Preferences


class TurnRequest(BaseModel):
    player_id: str
    action: str


class SnapshotResponse(BaseModel):
    turn_index: int
    player_action: str
    ai_response: dict
    created_at: str


class GameSummaryResponse(BaseModel):
    id: str
    player_id: str
    title: str
    turn_count: int
    created_at: str
    updated_at: str


class GameDetailResponse(BaseModel):
    id: str
    player_id: str
    title: str
    turn_count: int
    preferences: dict
    world_state: dict
    created_at: str
    updated_at: str
