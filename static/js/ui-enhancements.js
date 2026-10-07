/* Responsive panel controls; all original form IDs and handlers are preserved. */
document.addEventListener('DOMContentLoaded', () => {
  const page = document.getElementById('escalacaoIdealPage');
  if (!page) return;
  const mobile = window.matchMedia('(max-width: 767px)');
  page.querySelectorAll('.ideal-sidebar section, #consolePanel').forEach((panel, index) => {
    const head = panel.querySelector('.ideal-panel-head, .ideal-console-head');
    const title = head?.querySelector('h2, h3');
    if (!title || !/Estratégia|Disponibilidade|Prioridades|Logs de cálculo/.test(title.textContent)) return;
    const body = document.createElement('div');
    body.id = `ideal-panel-content-${index}`;
    while (head.nextSibling) body.append(head.nextSibling);
    panel.append(body);
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'ideal-panel-expand';
    button.setAttribute('aria-controls', body.id);
    const setOpen = (open) => {
      body.hidden = !open;
      button.setAttribute('aria-expanded', String(open));
      button.innerHTML = open ? '<i class="fas fa-chevron-up" aria-hidden="true"></i>' : '<i class="fas fa-chevron-down" aria-hidden="true"></i>';
      button.setAttribute('aria-label', `${open ? 'Recolher' : 'Expandir'} ${title.textContent.trim()}`);
      button.title = `${open ? 'Recolher' : 'Expandir'} ${title.textContent.trim()}`;
    };
    button.addEventListener('click', () => setOpen(body.hidden));
    head.append(button);
    setOpen(!mobile.matches);
    mobile.addEventListener('change', () => setOpen(!mobile.matches));
  });
});
