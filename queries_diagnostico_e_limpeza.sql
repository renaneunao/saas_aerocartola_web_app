-- ============================================================================
-- QUERIES DE DIAGNÓSTICO E LIMPEZA DE RANKINGS
-- Execute estas queries no seu cliente PostgreSQL (pgAdmin, DBeaver, etc)
-- ============================================================================

-- ============================================================================
-- PARTE 1: DIAGNÓSTICO
-- ============================================================================

-- 1.1 Ver todas as configurações
SELECT 
    id as config_id,
    user_id,
    team_id,
    perfil_peso_jogo,
    perfil_peso_sg,
    created_at,
    updated_at
FROM acw_weight_configurations
ORDER BY id;

-- 1.2 Ver rankings por configuration_id
SELECT 
    configuration_id,
    COUNT(*) as total_rankings
FROM acw_rankings_teams
GROUP BY configuration_id
ORDER BY configuration_id;

-- 1.3 Ver rankings por time (detalhado)
SELECT 
    r.team_id,
    t.team_name,
    r.configuration_id,
    COUNT(*) as total_rankings,
    STRING_AGG(DISTINCT CAST(r.posicao_id AS TEXT), ', ' ORDER BY CAST(r.posicao_id AS TEXT)) as posicoes
FROM acw_rankings_teams r
LEFT JOIN acw_teams t ON r.team_id = t.id
GROUP BY r.team_id, t.team_name, r.configuration_id
ORDER BY r.team_id, r.configuration_id;

-- 1.4 COMPARAR: configuração atual vs rankings salvos
SELECT 
    t.id as team_id,
    t.team_name,
    c.id as config_atual,
    COALESCE(r.config_rankings, 'SEM RANKINGS') as config_nos_rankings,
    CASE 
        WHEN c.id = r.config_rankings THEN '✅ OK'
        WHEN r.config_rankings IS NULL THEN '⚠️  SEM RANKINGS'
        ELSE '❌ INCOMPATÍVEL'
    END as status
FROM acw_teams t
LEFT JOIN acw_weight_configurations c ON t.user_id = c.user_id AND t.id = c.team_id
LEFT JOIN (
    SELECT 
        team_id,
        configuration_id::text as config_rankings
    FROM acw_rankings_teams
    GROUP BY team_id, configuration_id
) r ON t.id = r.team_id AND c.id::text = r.config_rankings
ORDER BY t.id;

-- 1.5 Times sem configuração
SELECT 
    t.id,
    t.team_name
FROM acw_teams t
LEFT JOIN acw_weight_configurations c ON t.user_id = c.user_id AND t.id = c.team_id
WHERE c.id IS NULL;

-- 1.6 Verificar duplicatas de configuração (NÃO DEVERIA EXISTIR)
SELECT 
    user_id,
    team_id,
    COUNT(*) as total
FROM acw_weight_configurations
GROUP BY user_id, team_id
HAVING COUNT(*) > 1;

-- ============================================================================
-- PARTE 2: LIMPEZA (CUIDADO!)
-- ============================================================================

-- ⚠️⚠️⚠️ ATENÇÃO: Estas queries DELETAM dados! Use com cuidado! ⚠️⚠️⚠️

-- 2.1 DELETAR TODOS OS RANKINGS (mantém configurações)
-- Depois disso, você precisará recalcular TODOS os módulos de TODOS os times
-- DELETE FROM acw_rankings_teams;

-- 2.2 DELETAR rankings de um time específico
-- DELETE FROM acw_rankings_teams WHERE team_id = 2;

-- 2.3 DELETAR rankings com configuration_id específico
-- DELETE FROM acw_rankings_teams WHERE configuration_id = 1;

-- 2.4 DELETAR rankings incompatíveis (configuration_id diferente da configuração atual)
-- DELETE FROM acw_rankings_teams r
-- WHERE NOT EXISTS (
--     SELECT 1 FROM acw_weight_configurations c
--     WHERE c.id = r.configuration_id
--       AND c.team_id = r.team_id
--       AND c.user_id = r.user_id
-- );

-- ============================================================================
-- PARTE 3: VERIFICAÇÃO APÓS LIMPEZA
-- ============================================================================

-- 3.1 Contar rankings restantes
SELECT COUNT(*) as total_rankings FROM acw_rankings_teams;

-- 3.2 Verificar se ainda há incompatibilidades
SELECT 
    t.id as team_id,
    t.team_name,
    c.id as config_atual,
    COUNT(r.id) as total_rankings
FROM acw_teams t
LEFT JOIN acw_weight_configurations c ON t.user_id = c.user_id AND t.id = c.team_id
LEFT JOIN acw_rankings_teams r ON r.team_id = t.id AND r.configuration_id = c.id
GROUP BY t.id, t.team_name, c.id
ORDER BY t.id;

-- ============================================================================
-- INSTRUÇÕES DE USO:
-- ============================================================================
--
-- 1. Execute PARTE 1 (DIAGNÓSTICO) para ver o estado atual
-- 2. Analise os resultados, especialmente a query 1.4 (COMPARAR)
-- 3. Se houver incompatibilidades (❌), você tem duas opções:
--    a) Recalcular os módulos do time afetado
--    b) Deletar os rankings e recalcular tudo do zero (PARTE 2)
-- 4. Se escolher PARTE 2, DESCOMENTE a query que deseja usar
-- 5. Execute PARTE 3 para verificar se está tudo OK
--
-- ============================================================================

