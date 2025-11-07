-- Popular tabela acf_destaques com dados dos atletas mais pontuados
-- Isso simula os jogadores mais escalados

INSERT INTO acf_destaques (atleta_id, escalacoes)
SELECT 
    atleta_id,
    FLOOR(pontos_num * 1000)::INTEGER as escalacoes
FROM acf_atletas
WHERE pontos_num > 0 AND status_id = 7
ORDER BY pontos_num DESC
LIMIT 100
ON CONFLICT (atleta_id) DO UPDATE 
SET escalacoes = EXCLUDED.escalacoes;

-- Verificar
SELECT COUNT(*) as total_destaques FROM acf_destaques;
SELECT atleta_id, escalacoes FROM acf_destaques ORDER BY escalacoes DESC LIMIT 10;
