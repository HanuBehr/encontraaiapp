# Encontra.ai

Encontra.ai é um MVP de descoberta de leads para buscar empresas públicas por nicho e cidade, revisar a prévia, enriquecer contatos, salvar leads e exportar uma planilha pronta para prospecção.

## Fluxo principal

`search -> preview -> enrich/recover -> save -> leads -> export`

- `search`: digite buscas como `dentistas em São Paulo` ou `restaurantes em Campinas`
- `preview`: revise a prévia antes de salvar qualquer lead
- `enrich/recover`: enriqueça contatos públicos e tente recuperar sites ausentes
- `save`: salve apenas os resultados selecionados
- `leads`: revise, filtre e selecione os leads salvos
- `export`: baixe a planilha Excel pronta para prospecção

## Arquitetura real

- `web/` é a interface principal V2 em Next.js
- `app/` é o backend FastAPI
- `streamlit_app.py` continua no repo apenas como workspace legado/interno

## Subir o backend

```powershell
cd "C:\Users\hanub\OneDrive\Documentos\Work\Encontra.ai\encontraaiapp"
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = (Get-Location).Path
python .\scripts\init_local_db.py
uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --log-level debug
```

URLs padrão:

- [http://127.0.0.1:8000](http://127.0.0.1:8000)
- [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## Subir o frontend

```powershell
cd "C:\Users\hanub\OneDrive\Documentos\Work\Encontra.ai\encontraaiapp\web"
npm install
npm run dev
```

URL padrão:

- [http://localhost:3000](http://localhost:3000)

## Variáveis de ambiente

Backend em `.env`:

- `GOOGLE_API_KEY`
  Obrigatória para descoberta por localização, geocoding e Google Places
- `DATABASE_URL`
  Padrão local: `sqlite:///./data/app.db`
- `SQLITE_JOURNAL_MODE`
  Padrão: `TRUNCATE`

Frontend em `web/.env.local`:

- `API_BASE_URL`
  Deve apontar para o backend FastAPI
  Valor local esperado: `http://127.0.0.1:8000`

Exemplos:

- [`.env.example`](C:/Users/hanub/OneDrive/Documentos/Work/Encontra.ai/encontraaiapp/.env.example)
- [`web/.env.example`](C:/Users/hanub/OneDrive/Documentos/Work/Encontra.ai/encontraaiapp/web/.env.example)

## Quickstart local

```powershell
cd "C:\Users\hanub\OneDrive\Documentos\Work\Encontra.ai\encontraaiapp"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python .\scripts\init_local_db.py

cd web
npm install
Copy-Item .env.example .env.local
```

Depois disso:

1. Suba o backend na porta `8000`
2. Suba o frontend na porta `3000`
3. Abra [http://localhost:3000/discovery](http://localhost:3000/discovery)

## Exportação

- O Excel é o formato principal de exportação
- A exportação baixa uma planilha limpa com os leads selecionados
- O fluxo esperado é salvar em `/leads` e exportar dali

## Troubleshooting

`502` no proxy do Next.js:

- Normalmente significa backend indisponível ou `API_BASE_URL` incorreto
- Confirme que a API está rodando em `http://127.0.0.1:8000`
- Confirme `web/.env.local` com `API_BASE_URL=http://127.0.0.1:8000`

`GOOGLE_API_KEY` ausente:

- A descoberta por localização fica indisponível
- A UI deve mostrar: `Configure GOOGLE_API_KEY no backend para usar a busca por localização.`

Banco local não inicializado:

- Rode `python .\scripts\init_local_db.py` antes de subir a API

Frontend sobe, mas a lista não carrega:

- Verifique backend em `8000`
- Verifique o proxy do Next.js em `web/app/api/backend/[...path]/route.ts`

## Legado Streamlit

```powershell
streamlit run streamlit_app.py
```

Use Streamlit apenas como workspace legado/interno. O produto principal é a aplicação Next.js em `web/`.

## Exemplo de configuração opcional

```powershell
python .\scripts\bootstrap_default_assignment_configuration.py
```

Esse script semeia uma configuração de atribuição de exemplo para demos internas. Não é necessário para a descoberta genérica por nicho + cidade.

## Preparação para limites SaaS futuros

Ainda não há autenticação, billing ou créditos implementados. Mesmo assim, o projeto já está organizado para acomodar limites futuros em torno de:

- buscas executadas
- leads salvos
- exportações geradas
- créditos consumidos por enriquecimento ou descoberta

Hoje isso é apenas preparação de nomenclatura e fluxo. Não existe Stripe, cobrança nem controle de uso em produção neste momento.

## Checks

```powershell
python -m pytest -q
cd web
npm run typecheck
```
