(function () {
  'use strict';

  const SELECTOR = 'select.aero-select:not(.scx-visually-hidden)';
  let dropdownSequence = 0;
  let activeDropdown = null;

  function closeDropdown(dropdown) {
    if (!dropdown) return;
    dropdown.classList.remove('is-open');
    const trigger = dropdown.querySelector('.aero-dropdown-trigger');
    if (trigger) trigger.setAttribute('aria-expanded', 'false');
    if (activeDropdown === dropdown) activeDropdown = null;
  }

  function closeAll(except = null) {
    document.querySelectorAll('.aero-dropdown.is-open').forEach(dropdown => {
      if (dropdown !== except) closeDropdown(dropdown);
    });
  }

  function optionText(option) {
    return option.textContent.trim() || option.value || 'Selecionar';
  }

  function setupSelect(select) {
    if (!(select instanceof HTMLSelectElement) || select.dataset.aeroDropdownReady === 'true') return;
    if (select.closest('.aero-dropdown') || select.classList.contains('scx-visually-hidden')) return;

    const dropdown = document.createElement('div');
    dropdown.className = `aero-dropdown${select.classList.contains('ideal-strategy-select') ? ' is-strategy' : ''}`;
    dropdown.dataset.aeroDropdown = 'true';

    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'aero-dropdown-trigger';
    trigger.id = `${select.id || 'aero-select'}-trigger-${++dropdownSequence}`;
    trigger.setAttribute('aria-haspopup', 'listbox');
    trigger.setAttribute('aria-expanded', 'false');
    trigger.setAttribute('aria-label', select.getAttribute('aria-label') || select.id || 'Selecionar uma opção');

    const value = document.createElement('span');
    value.className = 'aero-dropdown-value';
    const chevron = document.createElement('i');
    chevron.className = 'fas fa-chevron-down aero-dropdown-chevron';
    chevron.setAttribute('aria-hidden', 'true');
    trigger.append(value, chevron);

    const menu = document.createElement('div');
    menu.className = 'aero-dropdown-menu';
    menu.setAttribute('role', 'listbox');
    menu.id = `${trigger.id}-menu`;
    trigger.setAttribute('aria-controls', menu.id);

    dropdown.append(trigger, menu);
    select.parentNode.insertBefore(dropdown, select);
    dropdown.appendChild(select);
    select.dataset.aeroDropdownReady = 'true';
    select.tabIndex = -1;
    select.setAttribute('aria-hidden', 'true');

    const linkedLabel = select.id ? document.querySelector(`label[for="${CSS.escape(select.id)}"]`) : null;
    if (linkedLabel) linkedLabel.htmlFor = trigger.id;

    function renderOptions() {
      menu.replaceChildren();
      Array.from(select.options).forEach(option => {
        const item = document.createElement('button');
        item.type = 'button';
        item.className = 'aero-dropdown-option';
        item.dataset.value = option.value;
        item.setAttribute('role', 'option');
        item.textContent = optionText(option);
        item.disabled = option.disabled;
        item.setAttribute('aria-selected', option.value === select.value ? 'true' : 'false');
        item.addEventListener('click', event => {
          event.preventDefault();
          if (item.disabled) return;
          select.value = option.value;
          select.dispatchEvent(new Event('change', { bubbles: true }));
          sync();
          closeDropdown(dropdown);
          trigger.focus();
        });
        menu.appendChild(item);
      });
      sync();
    }

    function sync() {
      const selected = select.options[select.selectedIndex];
      value.textContent = selected ? optionText(selected) : 'Selecionar';
      trigger.disabled = select.disabled;
      menu.querySelectorAll('.aero-dropdown-option').forEach(item => {
        const selectedOption = item.dataset.value === select.value;
        item.classList.toggle('is-selected', selectedOption);
        item.setAttribute('aria-selected', selectedOption ? 'true' : 'false');
      });
    }

    trigger.addEventListener('click', event => {
      event.preventDefault();
      if (trigger.disabled) return;
      const willOpen = !dropdown.classList.contains('is-open');
      closeAll(dropdown);
      dropdown.classList.toggle('is-open', willOpen);
      trigger.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
      activeDropdown = willOpen ? dropdown : null;
    });
    trigger.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        closeDropdown(dropdown);
        return;
      }
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        trigger.click();
      }
    });
    select.addEventListener('change', sync);

    const optionsObserver = new MutationObserver(renderOptions);
    optionsObserver.observe(select, { childList: true, subtree: true, attributes: true, attributeFilter: ['disabled'] });
    renderOptions();
  }

  function init(root = document) {
    root.querySelectorAll?.(SELECTOR).forEach(setupSelect);
    if (root.matches?.(SELECTOR)) setupSelect(root);
  }

  document.addEventListener('click', event => {
    if (!event.target.closest('.aero-dropdown')) closeAll();
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') closeAll();
  });

  function boot() {
    init();
    const observer = new MutationObserver(mutations => {
      mutations.forEach(mutation => mutation.addedNodes.forEach(node => {
        if (node.nodeType === Node.ELEMENT_NODE) init(node);
      }));
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
  window.AeroDropdowns = { init };
})();
