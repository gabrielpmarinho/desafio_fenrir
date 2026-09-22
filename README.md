# Terminal Fenrir — LIMFIE UFRJ

Plataforma do Desafio Fenrir: simulação de gestão de carteira para treinar novos
membros da liga fora da temporada de desafios externos (JGP, Safra, Ágora).

Reescrita de 2026. A versão anterior (Streamlit + Google Sheets) está preservada
em `../Desafio_Limfie` apenas como referência — **não use como base de código**:
o motor de liquidação dela aplicava cada ordem duas vezes.

## Estado atual

| Camada | Situação |
|---|---|
| `core/` — motor puro | ✅ pronto e testado (47 testes) |
| `desafio/` — models, admin, comandos | ✅ pronto e testado |
| Integração de preços (yfinance/BCB) | ✅ pronto (sem teste de rede) |
| Telas do participante | ✅ login, carteira, ordens, extrato, ranking |
| Mural de avisos da Diretoria | ✅ model + admin, aparece na carteira |
| Gráfico da cota contra CDI/IBOV/S&P | ✅ base 100, com abas |
| Ranking semanal | ✅ congela no fechamento da sexta |
| Agendamento dos comandos | ⬜ a fazer |
| Deploy | ⬜ a fazer |

Testes: **47** no motor (pytest) + **33** de integração (Django).

## Arquitetura

O motor (`core/`) não tem dependência de framework, banco ou rede. Recebe o
ledger e devolve o estado. Três decisões sustentam isso:

1. **Ledger append-only** — toda ordem executada vira uma linha imutável com
   preço, câmbio e data.
2. **Estado derivado, nunca mutado** — caixa e posições são *calculados* a partir
   do ledger. Aplicar a mesma ordem duas vezes exigiria duas linhas visíveis.
3. **Preços persistidos** — o histórico nunca depende de uma chamada ao vivo.

## Regras implementadas

- Patrimônio inicial R$ 100.000.000,00; cota base 100,00 (1.000.000 de cotas).
- Caixa livre rende CDI em dias úteis, **capitalizado** — operar não zera juros.
- Sem alavancagem: `|comprado| + |vendido| <= patrimônio` (regra do JGP).
- Ativos em dólar convertidos para BRL no momento da execução.
- Whitelist fechada de 30 ativos (`core/universo.py`).
- Calendário de feriados nacionais com móveis por computus da Páscoa.
- **Só preço de fechamento.** Ordens do fim de semana liquidam na segunda, ao
  fechamento da segunda. A cota muda uma vez por dia útil, após o mercado fechar.
- **Aluguel de short**: 0,4% a.m., 1/20 por dia útil, linear no tamanho da
  posição (regra do JGP). Vira lançamento auditável no ledger.
- **A cota do próprio grupo é diária; a dos outros, semanal.** O ranking e a
  comparação entre fundos congelam no último dia útil da semana. Ansiedade com o
  próprio número leva a operar demais; com o número alheio, muda postura — e para
  isso não precisa ser diário.

## A fazer

Lista viva — o que sai daqui vai para o registro no fim do arquivo.

| # | Item | Observação |
|---|---|---|
| 1 | **Agendamento dos comandos** | `puxar_precos` → `liquidar_semana` (segundas) → `fechar_dia`, nessa ordem, todo dia útil. Falta decidir o mecanismo (Task Scheduler, cron do host, ou um comando único que orquestre). |
| 2 | **Deploy** | `settings.py` ainda em SQLite e `DEBUG`; `psycopg` já está no `requirements.txt`, então o alvo presumido é Postgres. Falta host, `ALLOWED_HOSTS`, `SECRET_KEY` fora do código e arquivos estáticos. |
| 3 | **CDI do BCB** | Hoje é taxa diária constante. Se o desafio passar de 3 meses, puxar a série do BCB (**série 12** — a 11 é Selic). |
| 4 | **Regulamento desatualizado** | Preço de execução, cota diária e aluguel de short já estão no código, mas não no texto do `REGULAMENTO.md`. |
| 5 | **Integração de preços sem teste** | `desafio/servicos/precos.py` fala com yfinance e BCB e não tem teste — nem com rede, nem com resposta gravada. Vale agora também para `puxar_benchmarks`. |
| 6 | **Primeira semana do desafio** | Antes da primeira sexta, o ranking mostra a apuração mais recente (recuo do `data_do_ranking`). Decidir se a tela deve avisar que aquela foto ainda é parcial. |

## Configuração

Nada de segredo em arquivo versionado. Tudo vem do ambiente:

| Variável | Padrão | Para que serve |
|---|---|---|
| `DJANGO_SECRET_KEY` | — | Obrigatória fora de desenvolvimento. Em `DEBUG`, o projeto gera uma na primeira execução e guarda em `.secret_key` (ignorado pelo git). |
| `DJANGO_DEBUG` | `1` | `0` em produção. Com `0` e sem `DJANGO_SECRET_KEY`, o servidor se recusa a subir. |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Lista separada por vírgula. |

```bash
git clone git@github.com:gabrielpmarinho/desafio_fenrir.git
cd desafio_fenrir
pip install -r requirements.txt
python manage.py migrate
python manage.py semear_demo --dias 40   # dados de demonstração, só com DEBUG
python manage.py runserver
```

## Rodando os testes

```bash
pip install -r requirements.txt

python -m pytest -q          # motor (sem Django)
python manage.py test desafio  # integração (banco + comandos)
```

## Rotina da Mesa

```bash
python manage.py puxar_precos --data 2026-10-05     # todo dia útil, após o fechamento
python manage.py liquidar_semana --data 2026-10-05  # segundas, depois do puxar_precos
python manage.py fechar_dia --data 2026-10-05       # todo dia útil, por último
```

Use `--simular` em `liquidar_semana` para ver o resultado sem gravar.

## Documentos

- `MANUAL_ADMIN.md` — manual da mesa (atual).
- `../Desafio_Limfie/Documentos/` — regulamento vigente e manual antigo. O
  manual antigo descreve a versão Streamlit e está obsoleto; o regulamento
  precisa das atualizações listadas acima.

## Registro de mudanças

Uma entrada por sessão de trabalho, com **o que mudou** e **o que ficou pendente**.
Mantido a pedido do Gabriel (21/09/2026) para que o contexto não se perca entre sessões.
Desde 22/09/2026 o projeto também está sob git: o `git log` conta o que mudou linha a
linha, e este registro conta **por quê** — as duas coisas se completam, nenhuma substitui
a outra.

### 2026-09-22 (tarde) — seis adições nas telas

Pedido do Gabriel depois de navegar pelo site. Plano aprovado em
`~/.claude/plans/algumas-coisas-no-site-jiggly-codd.md`.

**Carteira**
- Célula **"Avisos do Diretor de Competições"**: model `Aviso` (título, mensagem, `ativo`,
  `vigente_ate`, autor), criado pelo **admin do Django** — sem UI nova. Aviso vencido ou
  desativado some sozinho da tela.
- Célula com a **cota dos últimos 7 dias**, com a variação diária.
- **Gráfico da cota contra CDI, IBOV e S&P**, tudo em base 100 no primeiro fechamento do
  fundo. As "abas" são botões que ligam/desligam séries no **mesmo** gráfico
  (`setDatasetVisibility`) — três `<canvas>` em `div` escondida renderizam com tamanho zero,
  que é o bug clássico do Chart.js. Dá para ver duas referências ao mesmo tempo.

**Ordens**
- Novo status **CANCELADA** e botão de cancelar na boleta pendente (POST + CSRF). Cancelar
  não apaga: a linha fica no histórico, com etiqueta cinza riscada, distinta de "pendente".
- `liquidar_semana` não precisou mudar — já filtrava `status=PENDENTE`.

**Extrato**
- A Astra Capital (fundo da demo) ganhou uma perna vendida (`MGLU3.SA`, 900 mil) em
  `semear_demo`, para o aluguel de short aparecer na tela: 40 lançamentos no histórico.

**Ranking**
- Passa a ser **semanal**: `core/calendario.ultimo_dia_util_da_semana()` fecha a semana na
  sexta, recuando se for feriado, e nunca devolve data futura. A tabela e o gráfico
  comparativo congelam juntos — o gráfico também esconde a semana em aberto, senão daria a
  espiada diária na cota alheia que a regra quer evitar.
- **Recuo deliberado:** se nenhuma semana fechou ainda (primeiros dias do desafio), mostra a
  apuração mais recente em vez de deixar a tela vazia. Isso apareceu porque um teste existente
  quebrou — ele apurava numa segunda e esperava ver o ranking.

**Dados e infra**
- Model `Benchmark` (IBOV, S&P), separado de `PrecoFechamento` de propósito: `precos_do_dia()`
  monta o dicionário da apuração com tudo que existe na tabela de preços, e índice não é ativo
  investível. `puxar_precos` agora grava os dois índices junto.
- Migration `0002_alter_ordem_status_aviso_benchmark`.
- Demo re-semeada com `--limpar --dias 40` (8 sextas no histórico, contra 4 do padrão).

**Testes:** 47 no motor (4 novos de calendário) e 33 de integração (8 novos: cancelamento,
mural, série comparada, congelamento do ranking). `desafio/tests.py` ganhou a base
`TelaTestCase` — as classes novas herdavam `TestTelas` e re-executavam os testes dela.

### 2026-09-22 — recapitulação, sem mudança de código

- Levantada a estrutura completa (ver *Arquitetura* e o mapa de arquivos abaixo).
- Os dois suites rodados e verdes: **43 passed** (pytest, 0,05 s) e **25 OK** (Django).
  Ambiente: Python 3.11.9, Django 5.2.17.
- README reorganizado: "Decisões ainda em aberto" virou a tabela **A fazer**
  (5 itens, numerados) e passou a existir este registro.
- Nenhum arquivo de código foi tocado.

### Mapa de arquivos

```
core/          motor puro, sem Django   engine · models · custos · metricas · calendario · universo
desafio/       app Django               models · admin · views · forms · adapters · urls
  servicos/    carteira (visão, série de cotas, ranking) · precos (yfinance/BCB)
  management/  puxar_precos · liquidar_semana · fechar_dia · semear_demo
config/        settings · urls · asgi/wsgi
templates/     base + dashboard · ordens · extrato · ranking · login
tests/         test_engine · test_custos · test_metricas · test_calendario   (motor)
desafio/tests.py                                                            (integração)
```

Modelos do banco: `Fundo` · `Participante` · `Ordem` · `Trade` · `Lancamento` ·
`PrecoFechamento` · `Cotacao` · `TaxaCDI` · `Fechamento`.
No motor, os equivalentes são dataclasses congeladas, mais `Rejeicao` e os enums
`Moeda`, `Direcao` e `TipoLancamento`.
