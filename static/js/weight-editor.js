(function () {
  'use strict';

  function initWeightEditor() {
    const form = document.getElementById('pesosForm');
    const defaultsNode = document.getElementById('idealWeightDefaults');
    if (!form || !defaultsNode) return;

    let defaults = {};
    try { defaults = JSON.parse(defaultsNode.textContent || '{}'); } catch (_) { return; }
    const editable = [...form.querySelectorAll('input[type="number"][name^="FATOR_"]')]
      .filter((input) => !input.disabled);
    if (!editable.length) return;

    const tools = document.createElement('div');
    tools.className = 'weight-editor-tools';
    tools.innerHTML = '<div class="weight-editor-tools-copy"><strong>Ajuste a influência de cada indicador</strong><small>Arraste o controle. Salve e recalcule para aplicar.</small></div><div class="weight-editor-actions"><button type="button" class="weight-editor-reset"><i class="fas fa-wand-magic-sparkles" aria-hidden="true"></i><span>Restaurar padrão</span></button><div class="weight-reset-confirm" role="group" aria-label="Confirmar restauração dos pesos" hidden><span>Restaurar os pesos padrão do Aero-RBSV?</span><button type="button" class="weight-reset-cancel">Cancelar</button><button type="button" class="weight-reset-apply">Restaurar</button></div></div>';
    form.prepend(tools);

    editable.forEach((numberInput) => {
      numberInput.readOnly = true;
      numberInput.inputMode = 'none';
      numberInput.setAttribute('aria-readonly', 'true');
      numberInput.title = 'Altere este valor pelo controle deslizante';
      const wrap = document.createElement('div');
      wrap.className = 'weight-range-wrap';
      const slider = document.createElement('input');
      slider.type = 'range';
      slider.className = 'weight-range';
      slider.min = '-10';
      slider.max = '20';
      slider.step = '0.1';
      slider.setAttribute('aria-label', `Ajustar ${numberInput.name}`);
      const value = document.createElement('output');
      value.className = 'weight-range-value';

      const syncFromNumber = () => {
        const parsed = Number(numberInput.value);
        if (!Number.isFinite(parsed)) return;
        slider.value = String(Math.min(20, Math.max(-10, parsed)));
        value.value = parsed.toLocaleString('pt-BR', { maximumFractionDigits: 2 });
        value.textContent = value.value;
      };
      slider.addEventListener('input', () => {
        numberInput.value = Number(slider.value).toFixed(1);
        numberInput.dispatchEvent(new Event('input', { bubbles: true }));
        value.value = Number(slider.value).toLocaleString('pt-BR', { maximumFractionDigits: 2 });
        value.textContent = value.value;
      });
      numberInput.addEventListener('input', syncFromNumber);
      numberInput.addEventListener('change', syncFromNumber);
      wrap.append(slider, value);
      numberInput.insertAdjacentElement('afterend', wrap);
      syncFromNumber();
    });

    const resetButton = tools.querySelector('.weight-editor-reset');
    const confirmPanel = tools.querySelector('.weight-reset-confirm');
    resetButton?.addEventListener('click', () => {
      resetButton.hidden = true;
      confirmPanel.hidden = false;
    });
    tools.querySelector('.weight-reset-cancel')?.addEventListener('click', () => {
      confirmPanel.hidden = true;
      resetButton.hidden = false;
    });
    tools.querySelector('.weight-reset-apply')?.addEventListener('click', () => {
      editable.forEach((input) => {
        if (!Object.prototype.hasOwnProperty.call(defaults, input.name)) return;
        input.value = String(defaults[input.name]);
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
      });
      confirmPanel.hidden = true;
      resetButton.hidden = false;
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initWeightEditor, { once: true });
  else initWeightEditor();
})();
