(function () {
  const state = { items: [], filter: 'all', season: null, round: null };
  const positionNames = { 1: 'Goleiro', 2: 'Lateral', 3: 'Zagueiro', 4: 'Meia', 5: 'Atacante', 6: 'Técnico' };
  const statusColors = { 2: 'text-neon-amber', 3: 'text-neon-red', 5: 'text-neon-red', 6: 'text-neon-red', 7: 'text-neon-green' };

  const $ = (id) => document.getElementById(id);
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
    if ($('availabilitySeason').value) params.set('temporada', $('availabilitySeason').value);
    if ($('availabilityRound').value) params.set('rodada', $('availabilityRound').value);
    return params;
  }

  function filteredItems() {
    return state.items.filter((item) => state.filter === 'all' || item.rule === state.filter);
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
        <td class="px-4 py-3"><div class="flex items-center gap-3"><div class="w-8 h-8 rounded-full bg-white/5 overflow-hidden flex items-center justify-center">${item.foto ? `<img src="${item.foto}" alt="" class="w-full h-full object-cover">` : '<i class="fas fa-user text-text-muted text-xs"></i>'}</div><div><div class="font-semibold text-white">${item.apelido}</div><div class="text-[10px] text-text-muted">ID ${item.atleta_id}</div></div></div></td>
        <td class="px-4 py-3 text-text-secondary">${positionNames[item.posicao_id] || '—'}</td>
        <td class="px-4 py-3 text-text-secondary">${item.clube_abrev || item.clube_nome || '—'}</td>
        <td class="px-4 py-3"><span class="${statusClass} text-xs font-medium">${item.status_nome || 'Desconhecido'}</span></td>
        <td class="px-4 py-3"><div class="flex justify-end gap-2">${actionButton(item, 'poupar', 'Poupar', 'fa-ban', 'text-neon-red')}${actionButton(item, 'cravado', 'Cravar', 'fa-lock', 'text-neon-green', nullStatus || !nonProbable)}${item.rule ? `<button type="button" data-action="clear" data-athlete="${item.atleta_id}" class="rounded-lg px-2.5 py-1.5 text-[11px] border border-white/10 text-text-muted hover:text-white"><i class="fas fa-xmark mr-1"></i>Limpar</button>` : ''}</div></td>
      </tr>`;
    }).join('') : '<tr><td colspan="5" class="px-4 py-12 text-center text-text-muted">Nenhum jogador encontrado para este filtro.</td></tr>';
  }

  async function load() {
    const response = await fetch(`/api/player-availability/candidates?${query()}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Não foi possível carregar jogadores.');
    state.items = data.items || [];
    state.season = data.season; state.round = data.round_number;
    if (!$('availabilitySeason').value) $('availabilitySeason').value = data.season;
    if (!$('availabilityRound').value) $('availabilityRound').value = data.round_number;
    $('availabilityContext').textContent = `Temporada ${data.season} · Rodada ${data.round_number} · Time selecionado`;
    render();
  }

  async function save(athleteId, rule) {
    const response = await fetch('/api/player-availability', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ athlete_id: athleteId, rule, temporada: Number($('availabilitySeason').value), rodada: Number($('availabilityRound').value) }) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Não foi possível salvar a regra.');
    feedback(rule === 'poupar' ? 'Jogador marcado para ser poupado.' : 'Jogador cravado como provável para a escalação.', 'info');
    await load();
  }

  async function clear(athleteId) {
    const params = new URLSearchParams({ temporada: $('availabilitySeason').value, rodada: $('availabilityRound').value });
    const response = await fetch(`/api/player-availability/${athleteId}?${params}`, { method: 'DELETE' });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Não foi possível limpar a regra.');
    feedback('Regra removida.'); await load();
  }

  document.addEventListener('DOMContentLoaded', () => {
    ['availabilityPosition', 'availabilitySeason', 'availabilityRound'].forEach((id) => $(id).addEventListener('change', () => load().catch((e) => feedback(e.message, 'error'))));
    $('availabilityReload').addEventListener('click', () => load().catch((e) => feedback(e.message, 'error')));
    document.querySelectorAll('.availability-tab').forEach((button) => button.addEventListener('click', () => { document.querySelectorAll('.availability-tab').forEach((b) => b.classList.remove('active')); button.classList.add('active'); state.filter = button.dataset.filter; render(); }));
    $('availabilityRows').addEventListener('click', (event) => { const button = event.target.closest('button[data-action]'); if (!button) return; const action = button.dataset.action; const promise = action === 'clear' ? clear(button.dataset.athlete) : save(button.dataset.athlete, action); promise.catch((e) => feedback(e.message, 'error')); });
    load().catch((e) => feedback(e.message, 'error'));
  });
})();
