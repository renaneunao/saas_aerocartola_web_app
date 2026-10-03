"""Regras puras usadas pela API para opções pagas de escalação."""

DEFAULT_PRIORITIES = 'atacantes,laterais,meias,zagueiros,goleiros,treinadores'


def normalize_priorities(value):
    values = value.split(',') if isinstance(value, str) else value
    if not isinstance(values, (list, tuple)):
        raise ValueError('Prioridades inválidas.')
    normalized = [str(item).strip().replace('tecnicos', 'treinadores') for item in values]
    expected = DEFAULT_PRIORITIES.split(',')
    if len(normalized) != len(expected) or set(normalized) != set(expected):
        raise ValueError('Informe cada posição uma única vez nas prioridades.')
    return ','.join(normalized)


def effective_lineup_config(config, permissions):
    """Desativa opções de um plano anterior quando a conta muda de plano."""
    effective = dict(config)
    for key, feature in (('hack_goleiro', 'hackGoleiro'), ('fechar_defesa', 'fecharDefesa')):
        effective[key] = bool(config.get(key)) if permissions.get(feature) else False
    effective['prioridades'] = (
        normalize_priorities(config.get('prioridades') or DEFAULT_PRIORITIES)
        if permissions.get('reordenarPrioridades') else DEFAULT_PRIORITIES
    )
    return effective


def validate_lineup_options(config, permissions):
    for key, feature, label in (
        ('hack_goleiro', 'hackGoleiro', 'Hack do goleiro'),
        ('fechar_defesa', 'fecharDefesa', 'Fechar defesa'),
    ):
        if not isinstance(config.get(key, False), bool):
            raise ValueError(f'{label}: valor inválido.')
        if config.get(key) and not permissions.get(feature):
            return f'{label} requer o plano Pro.'
    priorities = normalize_priorities(config.get('prioridades') or DEFAULT_PRIORITIES)
    if not permissions.get('reordenarPrioridades') and priorities != DEFAULT_PRIORITIES:
        return 'Reordenar prioridades requer o plano Pro.'
    return None
