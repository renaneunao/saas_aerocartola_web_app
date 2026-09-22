(function () {
  'use strict';
  const page = document.getElementById('probablesMappingPage');
  if (!page) return;
  const state = { teams: [], season: null, round: null, busy: false };
  const positions = { 1: 'Goleiro', 2: 'Lateral', 3: 'Zagueiro', 4: 'Meia', 5: 'Atacante', 6: 'Técnico' };
  const $ = (id) => document.getElementById(id);
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#039;', '"': '&quot;' }[char]));
  const initials = (value) => escapeHtml(String(value || '?').trim().slice(0, 2).toUpperCase());
  const feedback = (message, error = false) => { const node = $('mappingFeedback'); node.textContent = message || ''; node.style.color = error ? '#fda4af' : '#86efac'; };

  function filteredTeams() {
    const team = $('mappingTeamFilter')?.value || '';
    const position = $('mappingPositionFilter')?.value || '';
    return state.teams.map((item) => {
      const externos = position ? item.externos.filter((player) => String(player.posicao_id) === position) : item.externos;
      return { ...item, externos };
    }).filter((item) => (!team || item.clube_slug_externo === team) && item.externos.length);
  }

  function officialOptions(team, external) {
    const options = (team.oficiais || []).filter((player) => !external.posicao_id || Number(player.posicao_id) === Number(external.posicao_id));
    if (!team.clube_id) return '<option value="">Vincule o time acima primeiro</option>';
    return '<option value="">Não vincular jogador</option>' + options.map((player) => `<option value="${player.atleta_id}" ${Number(player.atleta_id) === Number(external.atleta_id) ? 'selected' : ''}>${escapeHtml(player.nome)}${player.nome_completo && player.nome_completo !== player.nome ? ` · ${escapeHtml(player.nome_completo)}` : ''}</option>`).join('');
  }

  function render() {
    const target = $('mappingTeams');
    const teams = filteredTeams();
    if (!teams.length) {
      target.innerHTML = '';
      $('mappingEmpty').hidden = false;
      $('mappingEmpty').textContent = state.teams.length ? 'Nenhum jogador atende aos filtros atuais.' : 'Nenhum snapshot externo foi encontrado para a rodada atual.';
      return;
    }
    $('mappingEmpty').hidden = true;
    target.innerHTML = teams.map((team) => `
      <section class="mapping-team" data-club="${escapeHtml(team.clube_id)}">
        <header class="mapping-team-head">
          <strong class="mapping-team-name">${escapeHtml(team.nome_externo)} <span class="mapping-team-count">· ${team.externos.length} externo(s)</span></strong>
          <label class="mapping-team-link"><span>Time oficial</span><select data-team-slug="${escapeHtml(team.clube_slug_externo)}" aria-label="Time oficial para ${escapeHtml(team.nome_externo)}">${officialClubOptions(team)}</select></label>
        </header>
        <div class="mapping-column-head"><span>Provável externo</span><span></span><span>Jogador oficial</span></div>
        ${team.externos.map((external) => `
          <div class="mapping-row">
            <div class="mapping-external">
              <span class="mapping-avatar">${initials(external.nome)}</span>
              <div style="min-width:0"><div class="mapping-name">${escapeHtml(external.nome)}</div><small class="mapping-meta">${escapeHtml(positions[external.posicao_id] || 'Posição não informada')} · ${escapeHtml(external.status)}</small></div>
              <span class="mapping-status ${external.atleta_id ? 'is-mapped' : 'is-pending'}">${external.atleta_id ? 'mapeado' : 'pendente'}</span>
            </div>
            <span class="mapping-arrow" aria-hidden="true"><i class="fas fa-arrow-right"></i></span>
            <label class="mapping-official" title="Salvar vínculo manual">
              <span class="mapping-avatar"><i class="fas fa-user"></i></span>
              <select data-external-id="${escapeHtml(external.id)}" aria-label="Jogador oficial para ${escapeHtml(external.nome)}">${officialOptions(team, external)}</select>
            </label>
          </div>`).join('')}
      </section>`).join('');

    target.querySelectorAll('select[data-external-id]').forEach((select) => {
      select.addEventListener('change', () => save(select.dataset.externalId, select.value || null));
    });
    target.querySelectorAll('select[data-team-slug]').forEach((select) => {
      select.addEventListener('change', () => saveTeam(select.dataset.teamSlug, select.value || null));
    });
  }

  function officialClubOptions(team) {
    const clubs = state.clubes || [];
    return '<option value="">Escolha o time oficial</option>' + clubs.map((club) => `<option value="${club.id}" ${Number(club.id) === Number(team.clube_id) ? 'selected' : ''}>${escapeHtml(club.nome)}${club.abreviacao ? ` · ${escapeHtml(club.abreviacao)}` : ''}</option>`).join('');
  }

  function populateTeamFilter() {
    const select = $('mappingTeamFilter');
    const previous = select.value;
    select.innerHTML = '<option value="">Todos os times</option>' + state.teams.map((team) => `<option value="${escapeHtml(team.clube_slug_externo)}">${escapeHtml(team.nome_externo)}</option>`).join('');
    if ([...select.options].some((option) => option.value === previous)) select.value = previous;
  }

  async function load() {
    if (state.busy) return;
    state.busy = true;
    $('mappingReload').disabled = true;
    feedback('Carregando snapshot…');
    try {
      const response = await fetch('/api/admin/provaveis-mapeamento');
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Não foi possível carregar o mapeamento.');
      state.teams = data.times || [];
      state.clubes = data.clubes_oficiais || [];
      state.season = data.temporada;
      state.round = data.rodada_id;
      $('mappingRound').textContent = `Rodada ${data.rodada_id} · ${data.temporada}`;
      populateTeamFilter();
      render();
      if (data.available === false) {
        feedback(data.message);
      } else {
        const clubCount = state.teams.filter((team) => team.clube_id).length;
        const athleteCount = state.teams.flatMap((team) => team.externos).filter((player) => player.atleta_id).length;
        const totalAthletes = state.teams.reduce((total, team) => total + team.externos.length, 0);
        feedback(`${clubCount}/${state.teams.length} clubes vinculados · ${athleteCount}/${totalAthletes} jogadores vinculados.`);
      }
    } catch (error) {
      feedback(error.message, true);
      $('mappingEmpty').hidden = false;
      $('mappingEmpty').textContent = error.message;
    } finally {
      state.busy = false;
      $('mappingReload').disabled = false;
    }
  }

  async function save(externalId, athleteId) {
    try {
      feedback('Salvando vínculo…');
      const response = await fetch('/api/admin/provaveis-mapeamento', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ temporada: state.season, rodada_id: state.round, atleta_externo_id: externalId, atleta_id: athleteId })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Não foi possível salvar o vínculo.');
      feedback(athleteId ? 'Vínculo salvo.' : 'Vínculo removido.');
      await load();
    } catch (error) {
      await load();
      feedback(error.message, true);
    }
  }

  async function saveTeam(externalSlug, clubId) {
    try {
      feedback('Salvando vínculo do time…');
      const response = await fetch('/api/admin/provaveis-mapeamento', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tipo: 'time', temporada: state.season, rodada_id: state.round, clube_slug_externo: externalSlug, clube_id: clubId })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Não foi possível salvar o vínculo do time.');
      feedback(clubId ? 'Time vinculado. Agora associe os jogadores.' : 'Vínculo do time removido.');
      await load();
    } catch (error) {
      await load();
      feedback(error.message, true);
    }
  }

  $('mappingTeamFilter').addEventListener('change', render);
  $('mappingPositionFilter').addEventListener('change', render);
  $('mappingReload').addEventListener('click', load);
  load();
})();
