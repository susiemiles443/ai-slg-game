const state = {
  playerId: null,
  currentGameId: null,
};

function setStatus(text) {
  document.getElementById("status").textContent = text;
}

function getOrCreatePlayerId() {
  const key = "slg_player_id";
  let id = localStorage.getItem(key);
  if (!id) {
    if (window.crypto && window.crypto.randomUUID) {
      id = window.crypto.randomUUID();
    } else {
      id = "p-" + Date.now() + "-" + Math.floor(Math.random() * 1000000);
    }
    localStorage.setItem(key, id);
  }
  return id;
}

async function api(path, options = {}) {
  const resp = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new Error(data.detail || `HTTP ${resp.status}`);
  }
  return data;
}

function renderGameInfo(game) {
  const box = document.getElementById("gameInfo");
  const suggested = Array.isArray(game.world_state?.suggested_actions)
    ? game.world_state.suggested_actions
    : [];
  box.textContent =
    `战局: ${game.title}\n` +
    `ID: ${game.id}\n` +
    `回合数: ${game.turn_count}\n\n` +
    `局势摘要:\n${game.world_state?.state_summary || "(暂无)"}\n\n` +
    `建议行动:\n- ${suggested.join("\n- ") || "(暂无)"}`;
}

function renderSnapshots(rows) {
  const wrap = document.getElementById("snapshots");
  wrap.innerHTML = "";
  rows.forEach((s) => {
    const div = document.createElement("div");
    div.className = "snap";
    const pretty = JSON.stringify(s.ai_response, null, 2);
    div.innerHTML = `
      <h3>Turn ${s.turn_index} | ${new Date(s.created_at).toLocaleString()}</h3>
      <pre>玩家操作: ${s.player_action}\n\nAI 输出:\n${pretty}</pre>
    `;
    wrap.appendChild(div);
  });
}

async function loadGames() {
  setStatus("正在加载存档...");
  const rows = await api(`/api/games?player_id=${encodeURIComponent(state.playerId)}`);
  const ul = document.getElementById("gamesList");
  ul.innerHTML = "";

  rows.forEach((g) => {
    const li = document.createElement("li");
    const meta = document.createElement("div");
    meta.textContent = `${g.title} | Turn ${g.turn_count}`;
    const btn = document.createElement("button");
    btn.textContent = "载入";
    btn.addEventListener("click", () => loadGame(g.id));
    li.appendChild(meta);
    li.appendChild(btn);
    ul.appendChild(li);
  });

  setStatus(`存档数量: ${rows.length}`);
}

async function loadGame(gameId) {
  state.currentGameId = gameId;
  setStatus(`正在载入战局 ${gameId} ...`);
  const game = await api(`/api/games/${gameId}?player_id=${encodeURIComponent(state.playerId)}`);
  const snaps = await api(`/api/games/${gameId}/snapshots?player_id=${encodeURIComponent(state.playerId)}`);
  renderGameInfo(game);
  renderSnapshots(snaps);
  setStatus(`已载入战局 ${game.title}`);
}

async function createGame(evt) {
  evt.preventDefault();
  setStatus("正在创建战局...");
  const payload = {
    player_id: state.playerId,
    title: document.getElementById("title").value.trim(),
    preferences: {
      faction_style: document.getElementById("factionStyle").value.trim(),
      strategy_style: document.getElementById("strategyStyle").value.trim(),
      narrative_style: document.getElementById("narrativeStyle").value.trim(),
      extra_notes: document.getElementById("extraNotes").value.trim(),
    },
  };
  const game = await api("/api/games", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  await loadGames();
  await loadGame(game.id);
}

async function playTurn(evt) {
  evt.preventDefault();
  if (!state.currentGameId) {
    alert("请先选择或创建战局");
    return;
  }
  const action = document.getElementById("turnAction").value.trim();
  if (!action) {
    alert("请填写回合指令");
    return;
  }

  setStatus("正在推进回合...");
  await api(`/api/games/${state.currentGameId}/turn`, {
    method: "POST",
    body: JSON.stringify({
      player_id: state.playerId,
      action,
    }),
  });
  document.getElementById("turnAction").value = "";
  await loadGame(state.currentGameId);
}

async function bootstrap() {
  state.playerId = getOrCreatePlayerId();
  document.getElementById("playerId").textContent = state.playerId;

  document.getElementById("createGameForm").addEventListener("submit", async (evt) => {
    try {
      await createGame(evt);
    } catch (err) {
      setStatus(`创建失败: ${err.message}`);
    }
  });

  document.getElementById("playTurnForm").addEventListener("submit", async (evt) => {
    try {
      await playTurn(evt);
    } catch (err) {
      setStatus(`回合执行失败: ${err.message}`);
    }
  });

  document.getElementById("refreshGamesBtn").addEventListener("click", async () => {
    try {
      await loadGames();
    } catch (err) {
      setStatus(`刷新失败: ${err.message}`);
    }
  });

  try {
    await loadGames();
  } catch (err) {
    setStatus(`初始化失败: ${err.message}`);
  }
}

bootstrap();
