(function () {
  const state = { items: [], filter: 'provaveis', sort: 'expected', season: null, round: null, teamId: null };
  const positionNames = { 1: 'Goleiro', 2: 'Lateral', 3: 'Zagueiro', 4: 'Meia', 5: 'Atacante', 6: 'Técnico' };
  const statusColors = { 2: 'text-neon-amber', 3: 'text-neon-red', 5: 'text-neon-red', 6: 'text-neon-red', 7: 'text-neon-green' };

  const $ = (id) => document.getElementById(id);
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#039;', '"': '&quot;' }[char]));
  function feedback(message, kind = 'info') {
    const el = $('availabilityFeedback');
    el.className = `px-4 py-3 text-sm ${kind === 'error' ? 'text-neon-red bg-neon-red/5' : 'text-neon-cyan bg-neon-cyan/5'}`;
    el.textContent = message;
    el.classList.remove('hidden');
    if (kind !== 'error') setTimeout(() => el.classList.add('hidden'), 2600);
  }

  function query() {
    const params = new URLSearchParams();
    const position = $('availabilityPosition').value;
    if (position) params.set('position_id', position);
    if ($('availabilityClub').value) params.set('clube_id', $('availabilityClub').value);
    return params;
  }

  function filteredItems() {
    const search = ($('availabilitySearch')?.value || '').trim().toLocaleLowerCase();
    const scout = $('availabilityScout')?.value || '';
    const filtered = state.items.filter((item) => {
      const status = Number(item.status_id);
      if (state.filter === 'provaveis' && (item.rule === 'poupar' || (status !== 7 && item.rule !== 'cravado'))) return false;
      if (state.filter === 'poupar' && item.rule !== 'poupar') return false;
      if (state.filter === 'cravado' && item.rule !== 'cravado') return false;
      if ($('availabilityClub')?.value && String(item.clube_id) !== $('availabilityClub').value) return false;
      if (search && !`${item.apelido || ''} ${item.nome || ''} ${item.clube_nome || ''}`.toLocaleLowerCase().includes(search)) return false;
      return state.filter !== 'provaveis' || (status !== 6 && item.rule !== 'poupar');
    });
    const sort = $('availabilitySort')?.value || state.sort || 'expected';
    state.sort = sort;
    return filtered.sort((a, b) => {
      if (sort === 'average') return Number(b.media_num || 0) - Number(a.media_num || 0);
      if (sort === 'price_asc') return Number(a.preco_num || 0) - Number(b.preco_num || 0);
      if (sort === 'price_desc') return Number(b.preco_num || 0) - Number(a.preco_num || 0);
      if (sort === 'games') return Number(b.jogos_num || 0) - Number(a.jogos_num || 0);
      if (sort === 'scout') return Number(b.scouts?.[scout] || 0) - Number(a.scouts?.[scout] || 0);
      if (sort === 'name') return String(a.apelido || a.nome || '').localeCompare(String(b.apelido || b.nome || ''), 'pt-BR');
      return Number(b.pontos_num || 0) - Number(a.pontos_num || 0);
    });
  }

  function actionButton(item, rule, label, icon, tone, disabled = false) {
    const active = item.rule === rule;
    return `<button type="button" data-action="${rule}" data-athlete="${item.atleta_id}" ${disabled ? 'disabled' : ''}
      class="rounded-lg px-2.5 py-1.5 text-[11px] border transition ${active ? `${tone} border-current bg-current/10` : 'border-white/10 text-text-secondary hover:text-white hover:border-white/30'} ${disabled ? 'opacity-30 cursor-not-allowed' : ''}">
      <i class="fas ${icon} mr-1"></i>${active ? 'Marcado' : label}</button>`;
  }

  function render() {
    const rows = filteredItems();
    $('availabilityCount').textContent = `${rows.length} jogador(es)`;
    $('availabilityRows').innerHTML = rows.length ? rows.map((item) => {
      const nullStatus = Number(item.status_id) === 6;
      const nonProbable = [2, 3, 5].includes(Number(item.status_id));
      const statusClass = statusColors[item.status_id] || 'text-text-secondary';
      return `<tr class="hover:bg-white/[0.025]">
        <td class="px-4 py-3"><div class="flex items-center gap-3"><div class="w-8 h-8 rounded-full bg-white/5 overflow-hidden flex items-center justify-center">${item.foto ? `<img src="${escapeHtml(item.foto)}" alt="" class="w-full h-full object-cover">` : '<i class="fas fa-user text-text-muted text-xs"></i>'}</div><div><div class="font-semibold text-white">${escapeHtml(item.apelido)}</div><div class="text-[10px] text-text-muted">ID ${item.atleta_id}</div></div></div></td>
        <td class="px-4 py-3 text-text-secondary">${escapeHtml(positionNames[item.posicao_id] || '—')}</td>
        <td class="px-4 py-3 text-text-secondary">${escapeHtml(item.clube_abrev || item.clube_nome || '—')}</td>
        <td class="px-4 py-3 text-right text-white">${Number(item.media_num || 0).toFixed(2)}</td>
        <td class="px-4 py-3 text-right text-neon-cyan">${Number(item.pontos_num || 0).toFixed(2)}</td>
        <td class="px-4 py-3 text-right text-neon-green">C$ ${Number(item.preco_num || 0).toFixed(2)}</td>
        <td class="px-4 py-3"><span class="${statusClass} text-xs font-medium">${escapeHtml(item.status_nome || 'Desconhecido')}</span></td>
        <td class="px-4 py-3"><div class="flex justify-end gap-2">${actionButton(item, 'poupar', 'Poupar', 'fa-ban', 'text-neon-red')}${actionButton(item, 'cravado', 'Cravar', 'fa-lock', 'text-neon-green', nullStatus || !nonProbable)}${item.rule ? `<button type="button" data-action="clear" data-athlete="${item.atleta_id}" class="rounded-lg px-2.5 py-1.5 text-[11px] border border-white/10 text-text-muted hover:text-white"><i class="fas fa-xmark mr-1"></i>Limpar</button>` : ''}</div></td>
      </tr>`;
    }).join('') : '<tr><td colspan="8" class="px-4 py-12 text-center text-text-muted">Nenhum jogador encontrado para este filtro.</td></tr>';
  }

  async function load() {
    const response = await fetch(`/api/player-availability/candidates?${query()}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Não foi possível carregar jogadores.');
    state.items = data.items || [];
    state.season = data.season; state.round = data.round_number;
    state.teamId = data.team_id || state.teamId;
    $('availabilityContext').textContent = `Temporada ${data.season} · Rodada ${data.round_number} · Time selecionado`;
    const clubSelect = $('availabilityClub');
    if (clubSelect) {
      const previous = clubSelect.value;
      const clubs = [...new Map(state.items.map((item) => [String(item.clube_id), item.clube_abrev || item.clube_nome || `Clube #${item.clube_id}`])).entries()].sort((a, b) => a[1].localeCompare(b[1]));
      clubSelect.innerHTML = '<option value="">Todos os times</option>' + clubs.map(([id, name]) => `<option value="${escapeHtml(id)}">${escapeHtml(name)}</option>`).join('');
      if (clubs.some(([id]) => id === previous)) clubSelect.value = previous;
    }
    render();
  }

  async function save(athleteId, rule) {
    const response = await fetch('/api/player-availability', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ team_id: state.teamId, athlete_id: athleteId, rule, temporada: state.season, rodada: state.round }) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Não foi possível salvar a regra.');
    feedback(rule === 'poupar' ? 'Jogador marcado para ser poupado.' : 'Jogador cravado como provável para a escalação.', 'info');
    await load();
  }

  async function clear(athleteId) {
    const params = new URLSearchParams({ team_id: state.teamId, temporada: state.season, rodada: state.round });
    const response = await fetch(`/api/player-availability/${athleteId}?${params}`, { method: 'DELETE' });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Não foi possível limpar a regra.');
    feedback('Regra removida.'); await load();
  }

  document.addEventListener('DOMContentLoaded', () => {
    ['availabilityPosition'].forEach((id) => $(id).addEventListener('change', () => load().catch((e) => feedback(e.message, 'error'))));
    $('availabilityClub')?.addEventListener('change', () => render());
    $('availabilitySearch')?.addEventListener('input', () => render());
    ['availabilitySort', 'availabilityScout'].forEach((id) => $(id)?.addEventListener('change', () => render()));
    $('availabilityReload').addEventListener('click', () => load().catch((e) => feedback(e.message, 'error')));
    document.querySelectorAll('.availability-tab').forEach((button) => button.addEventListener('click', () => { document.querySelectorAll('.availability-tab').forEach((b) => b.classList.remove('active')); button.classList.add('active'); state.filter = button.dataset.filter; render(); }));
    $('availabilityRows').addEventListener('click', (event) => { const button = event.target.closest('button[data-action]'); if (!button) return; const action = button.dataset.action; const promise = action === 'clear' ? clear(button.dataset.athlete) : save(button.dataset.athlete, action); promise.catch((e) => feedback(e.message, 'error')); });
    load().catch((e) => feedback(e.message, 'error'));
  });
})();
