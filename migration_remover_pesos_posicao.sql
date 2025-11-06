-- Migration: Remover coluna pesos_posicao da tabela acw_weight_configurations
-- Data: 2025-11-06
-- Motivo: A coluna pesos_posicao não é mais utilizada. Os pesos das posições
--         são armazenados na tabela acw_posicao_weights, conforme análise em
--         ANALISE_REMOCAO_PESOS_POSICAO.md

-- IMPORTANTE: Fazer backup do banco antes de executar esta migration!

-- Verificar se a coluna existe antes de tentar remover
DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'acw_weight_configurations' 
        AND column_name = 'pesos_posicao'
    ) THEN
        -- Remover a coluna
        ALTER TABLE acw_weight_configurations DROP COLUMN pesos_posicao;
        RAISE NOTICE 'Coluna pesos_posicao removida com sucesso!';
    ELSE
        RAISE NOTICE 'Coluna pesos_posicao já foi removida anteriormente.';
    END IF;
END $$;

-- Verificar resultado
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'acw_weight_configurations'
ORDER BY ordinal_position;
