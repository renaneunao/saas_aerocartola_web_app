-- Script de verificação para testar as queries de replicação de pesos
-- Execute este script para verificar se as estruturas estão corretas

-- 1. Verificar estrutura da tabela acw_posicao_weights
SELECT 
    constraint_name,
    constraint_type,
    table_name
FROM information_schema.table_constraints
WHERE table_name = 'acw_posicao_weights'
AND constraint_type = 'UNIQUE';

-- Verificar as colunas da constraint UNIQUE
SELECT 
    tc.constraint_name,
    kcu.column_name,
    tc.table_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
WHERE tc.table_name = 'acw_posicao_weights'
AND tc.constraint_type = 'UNIQUE'
ORDER BY kcu.ordinal_position;

-- 2. Verificar estrutura da tabela acw_weight_configurations
SELECT 
    constraint_name,
    constraint_type,
    table_name
FROM information_schema.table_constraints
WHERE table_name = 'acw_weight_configurations'
AND constraint_type = 'UNIQUE';

-- Verificar as colunas da constraint UNIQUE
SELECT 
    tc.constraint_name,
    kcu.column_name,
    tc.table_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
WHERE tc.table_name = 'acw_weight_configurations'
AND tc.constraint_type = 'UNIQUE'
ORDER BY kcu.ordinal_position;

-- 3. Verificar se existe o time 'aero-rbsv'
SELECT id, user_id, team_name
FROM acw_teams
WHERE team_name = 'aero-rbsv';

-- 4. Verificar quantos pesos por posição existem para o time 'aero-rbsv'
SELECT 
    t.id as team_id,
    t.user_id,
    t.team_name,
    COUNT(pw.posicao) as total_posicoes
FROM acw_teams t
LEFT JOIN acw_posicao_weights pw ON t.id = pw.team_id AND t.user_id = pw.user_id
WHERE t.team_name = 'aero-rbsv'
GROUP BY t.id, t.user_id, t.team_name;

-- 5. Verificar quais posições têm pesos para o time 'aero-rbsv'
SELECT 
    pw.posicao,
    pw.weights_json
FROM acw_teams t
JOIN acw_posicao_weights pw ON t.id = pw.team_id AND t.user_id = pw.user_id
WHERE t.team_name = 'aero-rbsv'
ORDER BY pw.posicao;

-- 6. Verificar configuração de peso de jogo e peso de saldo de gols
SELECT 
    wc.name,
    wc.perfil_peso_jogo,
    wc.perfil_peso_sg,
    wc.is_default
FROM acw_teams t
JOIN acw_weight_configurations wc ON t.id = wc.team_id AND t.user_id = wc.user_id
WHERE t.team_name = 'aero-rbsv';

-- 7. Verificar outros times do mesmo usuário
SELECT 
    t.id,
    t.team_name,
    COUNT(pw.posicao) as posicoes_com_pesos,
    CASE WHEN wc.id IS NOT NULL THEN 'Sim' ELSE 'Não' END as tem_configuracao
FROM acw_teams t
LEFT JOIN acw_posicao_weights pw ON t.id = pw.team_id AND t.user_id = pw.user_id
LEFT JOIN acw_weight_configurations wc ON t.id = wc.team_id AND t.user_id = wc.user_id
WHERE t.user_id = (SELECT user_id FROM acw_teams WHERE team_name = 'aero-rbsv' LIMIT 1)
AND t.team_name != 'aero-rbsv'
GROUP BY t.id, t.team_name, wc.id
ORDER BY t.team_name;

-- 8. Teste de UPSERT para acw_posicao_weights (não executa, apenas mostra a query)
-- Esta query será usada no script Python:
/*
INSERT INTO acw_posicao_weights (user_id, team_id, posicao, weights_json, updated_at)
VALUES (?, ?, ?, ?::jsonb, CURRENT_TIMESTAMP)
ON CONFLICT (user_id, team_id, posicao)
DO UPDATE SET
    weights_json = EXCLUDED.weights_json,
    updated_at = CURRENT_TIMESTAMP;
*/

-- 9. Teste de UPSERT para acw_weight_configurations (não executa, apenas mostra a query)
-- Esta query será usada no script Python:
/*
INSERT INTO acw_weight_configurations (user_id, team_id, name, perfil_peso_jogo, perfil_peso_sg, is_default, updated_at)
VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
ON CONFLICT (user_id, team_id)
DO UPDATE SET
    name = EXCLUDED.name,
    perfil_peso_jogo = EXCLUDED.perfil_peso_jogo,
    perfil_peso_sg = EXCLUDED.perfil_peso_sg,
    is_default = EXCLUDED.is_default,
    updated_at = CURRENT_TIMESTAMP;
*/


