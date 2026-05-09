# Aero Cartola — Design System

## Conceito: **Glass Neon Dark**
Tema futurista com vidro translúcido, bordas neon ciano/azul sobre fundo deep space.
Estética de interfaces tech sofisticadas (HUD, holográfico) com elegância contida.

---

## 1. Paleta de Cores

### Backgrounds (Deep Space)
| Token | Hex | Uso |
|---|---|---|
| `bg-root` | `#060B14` | Fundo da página |
| `bg-primary` | `#0B1120` | Cards, sidebar |
| `bg-secondary` | `#111B2E` | Elementos sobrepostos |
| `bg-tertiary` | `#182338` | Hover states |
| `bg-glass` | `rgba(11,17,32,0.45)` | Painéis de vidro |

### Neon / Acentos
| Token | Hex | Uso |
|---|---|---|
| `neon-cyan` | `#00E5FF` | Bordas, glow principal |
| `neon-blue` | `#4494FF` | Links, ativo, destaque |
| `neon-purple` | `#A855F7` | Destaque secundário |
| `neon-green` | `#00FF88` | Sucesso, confirmado |
| `neon-amber` | `#F59E0B` | Avisos, pendente |
| `neon-red` | `#EF4444` | Erro, perigo |

### Texto
| Token | Hex | Uso |
|---|---|---|
| `text-primary` | `#EDF2FA` | Texto principal |
| `text-secondary` | `#94A3B8` | Texto secundário |
| `text-muted` | `#64748B` | Texto auxiliar |

---

## 2. Tipografia

| Uso | Fonte | Pesos |
|---|---|---|
| Corpo | **Inter** | 300, 400, 500, 600, 700 |
| Dados/Números | **JetBrains Mono** | 400, 500, 600 |

Escala: `xs(12px) sm(14px) base(16px) lg(18px) xl(20px) 2xl(24px) 3xl(30px) 4xl(36px)`

---

## 3. Componentes

### Glass Panel
```
bg-[rgba(11,17,32,0.45)] backdrop-blur-xl
border border-[rgba(0,229,255,0.10)]
rounded-2xl
shadow-[0_0_30px_rgba(0,229,255,0.04)]
```

### Neon Border (com glow)
```
border border-[rgba(0,229,255,0.20)]
shadow-[0_0_15px_rgba(0,229,255,0.08),inset_0_0_15px_rgba(0,229,255,0.02)]
```

### Botões
- **Primário**: `bg-gradient-to-r from-[#0066CC] to-[#0099FF]` + glow hover
- **Secundário**: `bg-transparent border border-[rgba(0,229,255,0.2)]` + neon hover
- **Ghost**: `hover:bg-[rgba(0,229,255,0.06)] text-neon-cyan`

### Inputs
```
bg-[rgba(17,27,46,0.5)] backdrop-blur
border border-[rgba(255,255,255,0.06)]
focus:border-[#00E5FF] focus:shadow-[0_0_15px_rgba(0,229,255,0.10)]
text-white placeholder:text-[#475569]
rounded-xl px-4 py-3
```

### Cards de Módulo
Glass panel + hover:scale-[1.01] + ícone gradiente por posição + status badge com glow.

### Tabelas
Header: `bg-[rgba(17,27,46,0.7)] sticky top-0 backdrop-blur`
Linhas: `hover:bg-[rgba(0,229,255,0.03)]` transição suave
Bordas: `border-b border-[rgba(255,255,255,0.03)]`

### Sidebar
```
bg-[rgba(6,11,20,0.88)] backdrop-blur-2xl
border-r border-[rgba(0,229,255,0.08)]
Links: active com left-border neon + bg glow sutil
```

### Badges
| Status | Classes |
|---|---|
| Sucesso | `bg-[rgba(0,255,136,0.10)] text-[#00FF88] border-[rgba(0,255,136,0.25)]` |
| Pendente | `bg-[rgba(245,158,11,0.10)] text-[#F59E0B] border-[rgba(245,158,11,0.25)]` |
| Erro | `bg-[rgba(239,68,68,0.10)] text-[#EF4444] border-[rgba(239,68,68,0.25)]` |
| Info | `bg-[rgba(0,229,255,0.10)] text-[#00E5FF] border-[rgba(0,229,255,0.25)]` |

### Modais
```
bg-[rgba(6,11,20,0.92)] backdrop-blur-2xl
border border-[rgba(0,229,255,0.12)]
shadow-[0_0_60px_rgba(0,229,255,0.06)]
```

---

## 4. Efeitos

| Efeito | Descrição |
|---|---|
| Glow pulse | `shadow-[0_0_5px]` → `shadow-[0_0_18px]` (2s) |
| Fade in up | `opacity:0 translateY(6px)` → visível (0.4s) |
| Hover lift | `scale-[1.01]` + sombra aumenta |
| Grid bg | Grid 1px em `rgba(0,229,255,0.025)` a cada 48px |
| Neon scan | Linha horizontal sutil no hover dos cards |
| Glass shimmer | Reflexo no vidro ao carregar página |

---

## 5. Estratégia de Implementação

**O que NÃO será alterado:**
- Nenhum `.py` (app, models, routes, calculos)
- Nenhum `.js` em `static/js/`
- Nenhum `id`, `data-*`, `onclick`, scripts inline de lógica
- Nenhuma estrutura de formulários/endpoints

**O que SERÁ alterado:**
- `base.html`: tailwind.config, sidebar, footer, flash messages, body
- Templates: classes Tailwind (cores, glass, bordas, botões, tabelas)
- `static/css/aero-theme.css`: CSS customizado (grid, glass, neon, scrollbar, animações)
- Adicionar Google Fonts (Inter + JetBrains Mono)
