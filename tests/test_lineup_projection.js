const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const context = { window: {}, console: { log() {}, warn() {} } };
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(__dirname, '../static/js/escalacao_ideal.js'), 'utf8'), context);

(async () => {
    const calculator = new context.window.EscalacaoIdeal({ patrimonio: 200, posicao_capitao: 'atacantes' });
    const counts = { goleiros: 1, zagueiros: 2, laterais: 2, meias: 3, atacantes: 3, treinadores: 1 };
    const starters = {};
    let id = 1;
    for (const [position, count] of Object.entries(counts)) {
        starters[position] = Array.from({ length: count }, () => ({ atleta_id: id++, apelido: position, pontuacao: 10 }));
    }
    calculator.getPontuacao = player => player.pontuacao;
    calculator.tentarEscalacao = () => ({ titulares: starters, reservas: {}, custoTotal: 120 });
    calculator.aplicarHackGoleiro = () => {};
    calculator.selecionarReservas = () => {};
    const result = await calculator.calcular();
    assert.equal(Object.values(result.titulares).flat().filter(player => player.eh_capitao).length, 1);
    assert.equal(result.pontuacaoTotal, 130, 'A projeção inicial deve incluir o mesmo bônus do capitão usado na edição manual');
    console.log('Lineup projection: passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
