(function () {
  'use strict';

  const page = document.getElementById('probablesMappingPage');
  if (!page) return;

  const state = { teams: [], clubes: [], season: null, round: null, busy: false };
  const positions = { 1: 'Goleiro', 2: 'Lateral', 3: 'Zagueiro', 4: 'Meia', 5: 'Atacante', 6: 'Técnico' };
  const statusLabels = {
    provavel: 'Provável', duvida: 'Dúvida', improvavel: 'Improvável',
    lesionado: 'Lesionado', suspenso: 'Suspenso', fora: 'Fora', nulo: 'Nulo'
  };
  const $ = (id) => document.getElementById(id);
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>'\"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#039;', '"': '&quot;' }[char]));
  const initials = (value) => escapeHtml(String(value || '?').trim().slice(0, 2).toUpperCase());
  const normalize = (value) => String(value || '').toLocaleLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, ' ').trim();
  const feedback = (message, error = false) => {
    const node = $('mappingFeedback');
    if (node) {
      node.textContent = message || '';
      node.style.color = error ? '#fda4af' : '#86efac';
    }
  };

  function similarity(left, right) {
    const a = normalize(left);
    const b = normalize(right);
    if (!a || !b) return 0;
    if (a === b) return 1000;
    if (a.includes(b) || b.includes(a)) return 850 - Math.abs(a.length - b.length);
    const aTokens = new Set(a.split(' '));
    const bTokens = new Set(b.split(' '));
    const common = [...aTokens].filter((token) => bTokens.has(token)).length;
    let previous = Array.from({ length: b.length + 1 }, (_, index) => index);
    for (let i = 1; i <= a.length; i += 1) {
      const current = [i];
      for (let j = 1; j <= b.length; j += 1) {
        current[j] = Math.min(current[j - 1] + 1, previous[j] + 1, previous[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
      }
      previous = current;
    }
    return common * 100 - previous[b.length];
  }

  function filteredTeams() {
    const teamSlug = $('mappingTeamFilter')?.value || '';
    const status = $('mappingStatusFilter')?.value || '';
    const query = normalize($('mappingNameFilter')?.value || '');
    const hideMapped = Boolean($('mappingHideMapped')?.checked);
    return state.teams.map((team) => {
      const externos = (team.externos || []).filter((player) => {
        if (hideMapped && player.atleta_id) return false;
        if (status && normalize(player.status) !== status) return false;
        if (query) {
          const haystack = normalize(`${player.nome} ${player.mapeado_nome || ''} ${team.nome_externo} ${team.nome || ''}`);
          if (!haystack.includes(query)) return false;
        }
        return true;
      });
      return { ...team, externos };
    }).filter((team) => (!teamSlug || team.clube_slug_externo === teamSlug) && team.externos.length);
  }

  function candidateOptions(team, external) {
    const currentId = Number(external.atleta_id || 0);
    return (team.oficiais || []).slice().sort((left, right) => {
      const score = similarity(external.nome, left.nome);
      const other = similarity(external.nome, right.nome);
      return other - score || String(left.nome).localeCompare(String(right.nome), 'pt-BR');
    }).map((player) => `<option value="${escapeHtml(player.atleta_id)}" ${Number(player.atleta_id) === currentId ? 'selected' : ''}>${escapeHtml(player.nome)} · ${escapeHtml(positions[player.posicao_id] || 'Posição')}</option>`).join('');
  }

  function officialClubOptions(team) {
    return '<option value="">Escolha o time oficial</option>' + state.clubes.map((club) => `<option value="${escapeHtml(club.id)}" ${Number(club.id) === Number(team.clube_id) ? 'selected' : ''}>${escapeHtml(club.nome)}${club.abreviacao ? ` · ${escapeHtml(club.abreviacao)}` : ''}</option>`).join('');
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
      <section class="mapping-team" data-club="${escapeHtml(team.clube_slug_externo)}">
        <header class="mapping-team-head">
          <div><strong class="mapping-team-name">${escapeHtml(team.nome_externo)}</strong><span class="mapping-team-count">· ${team.externos.length} para revisar</span></div>
          <label class="mapping-team-link"><span>Time oficial</span><select data-team-slug="${escapeHtml(team.clube_slug_externo)}" aria-label="Time oficial para ${escapeHtml(team.nome_externo)}">${officialClubOptions(team)}</select>${team.clube_mapeado ? '<b class="mapping-team-state is-confirmed">confirmado</b>' : '<b class="mapping-team-state is-suggested">sugestão</b>'}</label>
        </header>
        <div class="mapping-column-head"><span>Jogador externo · status</span><span></span><span>Oficial mais parecido · posição</span></div>
        ${team.externos.map((external) => `
          <div class="mapping-row" data-external-row="${escapeHtml(external.id)}">
            <div class="mapping-external"><span class="mapping-avatar">${initials(external.nome)}</span><div style="min-width:0"><div class="mapping-name">${escapeHtml(external.nome)}</div><small class="mapping-meta">${escapeHtml(statusLabels[external.status] || external.status || 'Status não informado')} · ${escapeHtml(positions[external.posicao_id] || 'Posição não informada')}</small></div>${external.atleta_id ? '<span class="mapping-status is-mapped">mapeado</span>' : '<span class="mapping-status is-pending">pendente</span>'}</div>
            <span class="mapping-arrow" aria-hidden="true"><i class="fas fa-arrow-right"></i></span>
            <div class="mapping-official"><span class="mapping-avatar"><i class="fas fa-user-check"></i></span><select data-external-select="${escapeHtml(external.id)}" aria-label="Jogador oficial para ${escapeHtml(external.nome)}"><option value="">Escolha o jogador oficial</option>${candidateOptions(team, external)}</select><button type="button" class="mapping-confirm" data-save-external="${escapeHtml(external.id)}" disabled title="Confirmar vínculo"><i class="fas fa-check"></i></button></div>
          </div>`).join('')}
      </section>`).join('');

    target.querySelectorAll('select[data-external-select]').forEach((select) => {
      select.addEventListener('change', () => {
        const button = select.closest('.mapping-official')?.querySelector('button[data-save-external]');
        if (button) button.disabled = !select.value;
      });
    });
    target.querySelectorAll('button[data-save-external]').forEach((button) => {
      button.addEventListener('click', () => {
        const select = button.closest('.mapping-official')?.querySelector('select[data-external-select]');
        save(button.dataset.saveExternal, select?.value || null);
      });
    });
    target.querySelectorAll('select[data-team-slug]').forEach((select) => {
      select.addEventListener('change', () => saveTeam(select.dataset.teamSlug, select.value || null));
    });
  }

  function populateTeamFilter() {
    const select = $('mappingTeamFilter');
    const previous = select.value;
    select.innerHTML = '<option value="">Todos os times</option>' + state.teams.map((team) => `<option value="${escapeHtml(team.clube_slug_externo)}">${escapeHtml(team.nome_externo)}</option>`).join('');
    if ([...select.options].some((option) => option.value === previous)) select.value = previous;
  }

  async function requestMapping(payload) {
    const response = await fetch('/api/admin/provaveis-mapeamento', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Não foi possível salvar o vínculo.');
    return data;
  }

  async function load() {
    if (state.busy) return;
    state.busy = true;
    $('mappingReload').disabled = true;
    feedback('Carregando jogadores da fonte externa…');
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
      if (data.available === false) feedback(data.message);
      else {
        const clubCount = state.teams.filter((team) => team.clube_mapeado).length;
        const athleteCount = state.teams.flatMap((team) => team.externos).filter((player) => player.atleta_id).length;
        const totalAthletes = state.teams.reduce((total, team) => total + team.externos.length, 0);
        feedback(`${clubCount}/${state.teams.length} times confirmados · ${athleteCount}/${totalAthletes} jogadores mapeados.`);
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
    const team = state.teams.find((item) => item.externos.some((player) => String(player.id) === String(externalId)));
    if (!team || !athleteId) return;
    try {
      feedback('Confirmando vínculo…');
      if (!team.clube_mapeado && team.clube_id) await requestMapping({ tipo: 'time', temporada: state.season, rodada_id: state.round, clube_slug_externo: team.clube_slug_externo, clube_id: team.clube_id });
      await requestMapping({ temporada: state.season, rodada_id: state.round, atleta_externo_id: externalId, atleta_id: athleteId });
      await load();
    } catch (error) {
      await load();
      feedback(error.message, true);
    }
  }

  async function saveTeam(externalSlug, clubId) {
    try {
      feedback('Salvando vínculo do time…');
      await requestMapping({ tipo: 'time', temporada: state.season, rodada_id: state.round, clube_slug_externo: externalSlug, clube_id: clubId });
      await load();
    } catch (error) {
      await load();
      feedback(error.message, true);
    }
  }

  async function saveSuggestions() {
    const suggestions = state.teams.filter((team) => !team.clube_mapeado && team.clube_id_sugerido);
    if (!suggestions.length) return feedback('Não há sugestões de times pendentes.');
    try {
      $('mappingConfirmSuggestions').disabled = true;
      feedback(`Confirmando ${suggestions.length} times conhecidos…`);
      for (const team of suggestions) await requestMapping({ tipo: 'time', temporada: state.season, rodada_id: state.round, clube_slug_externo: team.clube_slug_externo, clube_id: team.clube_id_sugerido });
      await load();
    } catch (error) {
      feedback(error.message, true);
      $('mappingConfirmSuggestions').disabled = false;
    }
  }

  $('mappingTeamFilter').addEventListener('change', render);
  $('mappingStatusFilter').addEventListener('change', render);
  $('mappingNameFilter').addEventListener('input', render);
  $('mappingHideMapped').addEventListener('change', render);
  $('mappingReload').addEventListener('click', load);
  $('mappingConfirmSuggestions').addEventListener('click', saveSuggestions);
  load();
})();
