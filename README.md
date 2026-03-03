# 💻 SaaS AeroCartola - Portal Web 🚀

Aplicação Front-End/Back-End Server-Side em Flask do serviço SaaS **Cartola Aero**. Atua como o centro de exibição do usuário, contendo painéis, gerência de dados e a interface visual oficial de todo o ecossistema SaaS.

## 📋 Sobre o Projeto
Essa aplicação foi desenhada com componentes visuais usando arquiteturas nativas Server-Side (`templates/` e rotas parametrizadas no diretório `routes/`).
Tem a responsabilidade de apresentar de forma mastigada os cálculos provenientes do backend/motor principal do Cartola Aero, traduzindo probabilidade de SG (Saldo de Gols), Pesos Táticos de cada equipe, análises comparativas e planilhas dinâmicas criadas em `html`.

## ⚙️ Principais Funcionalidades
- **Gestão de Planos & Assinaturas**: Integra regras de acesso, contendo rotinas de banco ativas para checar credenciais pagas (visíveis nos módulos `init_plans.py`, `setup_planos.py`, `aplicar_planos_usuarios.py`).
- **Lógica e UI para Escalação**: Fornece um assistente UI contendo `calculo_escalacao_ideal.py` integrado à web para que os usuários calculem o provável time dos sonhos.
- **Painéis e Rankings Dinâmicos (Web Pages)**: Modelos renderizados dinamicamente pelo Flask que trazem visões gerenciais, além do serviço automatizado de limpeza e sincronização `limpar_rankings.py`.
- **Comunicação por E-mail Sensível**: Contém um helper/config de e-mail integrado e focado no Brevo (`BREVO_CONFIG.md`) acionado dinamicamente pela aplicação.

## 📦 Infraestrutura & Dependências
- **Database Centralizado**: Migrações baseadas em Python via `init_database.py` e validação com `verificar_banco.py`.
- **Servidor Leve e Modularizado**: Organizado no root com `docker-compose.yml`, podendo ser testado ou deployado sob `WSGI/Gunicorn`.

## 🛠️ Como rodar o projeto de Desenvolvimento

1. Entre no diretório de ambiente/virtualenv local.
2. Instale:
```bash
pip install -r requirements.txt
```
3. Garanta que o banco foi migrado/criado se rodando em máquina virgem:
```bash
python init_database.py && python setup_planos.py
```
4. Aponte para o app.py ou wsgi:
```bash
python app.py
```
O portal estará no ar para receber interações. Acesse o browser via http://localhost:5000 (ou o listener configurado).
