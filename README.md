# Terminal Fenrir — LIMFIE UFRJ

Plataforma do **Desafio Fenrir**, a competição interna da Liga de Mercado
Financeiro da UFRJ. Cada grupo de novos membros recebe um fundo fictício de
R$ 100 milhões e o gere por uma temporada: envia ordens no fim de semana, vê a
cota ser apurada todo dia útil e disputa um ranking com os outros grupos. Serve
para treinar a turma nova fora da temporada dos desafios externos (JGP, Safra,
Ágora), com as mesmas regras que eles vão encontrar lá fora.

O sistema faz três coisas: **recebe as boletas** dos participantes, **liquida e
apura** as cotas a partir de preços reais de mercado, e **mostra** a carteira, o
extrato e o ranking. Quem opera isso é a Mesa — a diretoria do desafio.

Django 5.2 + SQLite (outro banco por `DATABASE_URL`), preços via yfinance e CDI
via API do Banco Central. Sem dependência paga e sem serviço externo além dessas
duas fontes de dados.

## Para quem está assumindo o projeto

Este repositório foi escrito para ser **entregue a outra pessoa**. Se você é o
próximo diretor de competições, comece por aqui.

**Rodando em cinco minutos** — veja *Configuração* abaixo. O comando
`semear_demo` cria quatro fundos fictícios com histórico, para você navegar pelas
telas com conteúdo de verdade antes de encostar em qualquer coisa.

**Os quatro documentos e para que serve cada um:**

| Documento | Responde |
|---|---|
| `README.md` (este) | O que é o sistema, como rodar, o que falta fazer, o que já mudou |
| `REGULAMENTO.md` | As regras do desafio, do ponto de vista do **participante** |
| `MANUAL_ADMIN.md` | Como a **Mesa** opera: rotina diária, nova edição, troubleshooting |
| `git log` | O que mudou linha a linha, e o *Registro de mudanças* no fim deste arquivo diz por quê |

**O ciclo de uma edição**, em ordem: cadastrar a edição e os grupos
(`MANUAL_ADMIN.md` §4) → rodar a rotina diária enquanto o desafio corre
(*Rotina da Mesa*, abaixo) → encerrar e apurar o resultado final
(`MANUAL_ADMIN.md` §3.3).

**O que você herda junto:** a lista *A fazer* logo abaixo é real e priorizada —
o primeiro item (subir o deploy, já decidido e preparado) é o que separa o
sistema de rodar sozinho. Nada ali é dívida escondida; está tudo escrito.

### Decisões que parecem estranhas e não são

Se você for mexer, leia isto antes — são escolhas deliberadas que já custaram
caro para serem descobertas:

- **O ledger é append-only.** `Trade` e `Lancamento` nunca são editados nem
  apagados. Erro se corrige com lançamento contrário, não com `UPDATE`. A versão
  anterior mutava o estado e **aplicava cada ordem duas vezes** na liquidação;
  foi esse bug que motivou a reescrita.
- **Só preço de fechamento.** Nada de preço intradiário, nem de "preço do dia
  anterior" para tapar buraco. Preencher lacuna com preço velho falsifica cota.
- **A cota do próprio grupo é diária; a dos outros, semanal.** Não é limitação
  técnica: ansiedade com o próprio número leva a operar demais, e é justamente o
  vício que o desafio quer curar.
- **Segredo nenhum no repositório.** A versão anterior vazou uma chave de service
  account porque o `.gitignore` estava vazio. Hoje a `SECRET_KEY` vem do
  ambiente e, sem ela, o servidor de produção se recusa a subir.
- **A versão antiga (Streamlit + Google Sheets) está em `../Desafio_Limfie`.**
  É referência histórica, **não** base de código — o motor de liquidação dela é
  justamente o que estava errado.

## Estado atual

| Camada | Situação |
|---|---|
| `core/` — motor puro | ✅ pronto e testado (55 testes) |
| `desafio/` — models, admin, comandos | ✅ pronto e testado |
| Integração de preços (yfinance/BCB) | ✅ pronto (sem teste de rede) |
| Telas do participante | ✅ login, carteira, ordens, extrato, ranking |
| Mural de avisos da Diretoria | ✅ model + admin, aparece na carteira |
| Gráfico da cota contra CDI/IBOV/S&P | ✅ base 100, com abas |
| Ranking semanal | ✅ congela no fechamento da sexta |
| Rotina diária (`rotina_diaria`) | ✅ Agendador do Windows no PC; GitHub Actions em produção |
| Deploy | 🟨 decidido e preparado (Render + Neon + GitHub Actions); falta criar as contas |

Testes: **55** no motor (pytest) + **50** de integração (Django).

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
- Caixa livre rende CDI em dias úteis, **capitalizado** — operar não zera juros. Cada dia
  rende a taxa vigente nele (`core/cdi.py`): mudar o CDI hoje não refaz o rendimento de ontem.
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
| 1 | **Subir o deploy** | Host **decidido em 19/10/2026: Render (site) + Neon (banco) + GitHub Actions (rotina e backup)**, tudo grátis. Código e configuração prontos (`render.yaml`, `.github/workflows/rotina_diaria.yml`). Falta o que só o dono das contas faz: criar Neon e Render, cadastrar os segredos no GitHub e o superusuário — passo a passo em `MANUAL_ADMIN.md` §8. Plano B pago no mesmo lugar. |
| 2 | **Fonte alternativa de CDI** | Desde out/2026 a API SGS do BCB devolve página de erro (de qualquer lugar); o CDI entra pelo admin quando o Copom muda a taxa. Se o BCB voltar, a rotina grava sozinha. Vale achar outra fonte (B3, Anbima) para não depender do cadastro manual. |
| 3 | **Integração de preços com pouco teste** | `desafio/servicos/precos.py`: o `puxar_cdi` tem teste com resposta simulada; yfinance (preços, câmbio, índices) continua só com o teste de fumaça manual `teste_fontes.yml` no GitHub Actions. |
| 4 | **Licença do repositório** | Sem `LICENSE`, o código é "todos os direitos reservados" por padrão — nem outro membro da liga pode reusar legalmente. Decisão da diretoria; MIT é o usual em projeto acadêmico. |
| 5 | **Primeira semana do desafio** | Antes da primeira sexta, o ranking mostra a apuração mais recente (recuo do `data_do_ranking`). Decidir se a tela deve avisar que aquela foto ainda é parcial. |

## Configuração

Nada de segredo em arquivo versionado. Tudo vem do ambiente:

| Variável | Padrão | Para que serve |
|---|---|---|
| `DJANGO_SECRET_KEY` | — | Obrigatória fora de desenvolvimento. Em `DEBUG`, o projeto gera uma na primeira execução e guarda em `.secret_key` (ignorado pelo git). |
| `DJANGO_DEBUG` | `1` | `0` em produção. Com `0` e sem `DJANGO_SECRET_KEY`, o servidor se recusa a subir. |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Lista separada por vírgula. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | vazio | Em produção, o endereço com `https://` (ex. `https://fenrir.exemplo.org`). Sem ele, login e boleta dão erro 403. |
| `DATABASE_URL` | SQLite em `db.sqlite3` | Banco do host, ex. `postgres://usuario:senha@host:5432/fenrir`. Tem senha: só no ambiente. |
| `DJANGO_SSL_REDIRECT` | `1` | Com `DEBUG=0`, manda HTTP para HTTPS. `0` só se o host já fizer isso e der loop. |
| `DJANGO_HSTS_SECONDS` | `0` | HSTS desligado até o HTTPS estar estável no domínio definitivo; depois, `31536000`. O navegador memoriza a regra, por isso não se liga no primeiro dia. |
| `RENDER_EXTERNAL_HOSTNAME` | — | Definida pelo próprio Render; o endereço entra sozinho em `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS`. |

**Produção oficial: Render + Neon + GitHub Actions**, passo a passo em `MANUAL_ADMIN.md` §8.
O `render.yaml` já define build, start e variáveis.

Subindo em outro host: definir as variáveis acima com `DJANGO_DEBUG=0`, depois
`pip install -r requirements.txt` → `python manage.py migrate` → `python manage.py collectstatic --noinput`
→ `python manage.py createsuperuser` → `python manage.py check --deploy` (o único aviso aceitável é o
HSTS enquanto `DJANGO_HSTS_SECONDS=0`). Servidor web: `gunicorn config.wsgi` (ou o WSGI do próprio
host, como no PythonAnywhere). Agendar `rotina_diaria` e, logo depois, `backup_banco`.

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

Um comando só faz o dia inteiro, e é ele que o agendador chama:

```bash
python manage.py rotina_diaria                    # hoje
python manage.py rotina_diaria --data 2026-10-05  # um dia específico
python manage.py rotina_diaria --desde 2026-10-01 # reprocessa um intervalo
```

Para cada dia útil pendente ele roda `puxar_precos` → `liquidar_semana` (só no 1º dia útil
da semana, regulamento §2.1) → `fechar_dia`. Em dia não útil não faz nada, então pode ser
agendado de segunda a domingo. **Recupera dias perdidos:** se o PC ficou desligado, a próxima
execução apura os dias úteis desde o último fechamento, em ordem (teto de 10 dias úteis;
acima disso para e pede `--desde`, porque é sinal de problema maior). Erro em qualquer etapa
interrompe e sai com código 1; o que já foi gravado fica, e a próxima execução retoma.

**Agendamento.** Horário: **21h de Brasília**, depois do fechamento americano (18h, ou 19h
fora do horário de verão de lá).

- *Windows (enquanto não há deploy):* `agendamento/rotina_diaria.bat` roda o comando e anexa a
  saída em `logs/rotina_AAAA-MM.log` (ignorado pelo git). Para registrar a tarefa, num
  terminal **cmd**:
  ```
  schtasks /Create /SC DAILY /ST 21:00 /TN "Fenrir rotina diaria" /TR "\"C:\GABRIEL\UFRJ ECON\LIMFIE\Fenrir_Terminal\agendamento\rotina_diaria.bat\""
  ```
  Remover: `schtasks /Delete /TN "Fenrir rotina diaria" /F`. Só roda com o PC ligado; o dia
  perdido é recuperado na execução seguinte.
- *Produção (GitHub Actions):* o workflow `.github/workflows/rotina_diaria.yml` roda às
  **19h30 de Brasília** (22h30 UTC) contra o banco do Neon e guarda um backup cifrado.
  Mais cedo que no PC de propósito: o agendador do GitHub atrasa às vezes, e a rotina
  precisa terminar antes da meia-noite, senão `date.today()` vira o dia seguinte. Para
  reprocessar: *Actions → Rotina diária → Run workflow*, com o campo `desde`.

Os comandos avulsos continuam valendo para correção e conferência:

```bash
python manage.py puxar_precos --data 2026-10-05
python manage.py liquidar_semana --data 2026-10-05 --simular  # vê sem gravar
python manage.py fechar_dia --data 2026-10-05 --refazer       # reapura um dia
```

## Registro de mudanças

Uma entrada por sessão de trabalho, com **o que mudou** e **o que ficou pendente**.
Mantido a pedido do Gabriel (21/09/2026) para que o contexto não se perca entre sessões.
Desde 22/09/2026 o projeto também está sob git: o `git log` conta o que mudou linha a
linha, e este registro conta **por quê** — as duas coisas se completam, nenhuma substitui
a outra.

### 2026-10-20 — CDI no motor: cada dia à sua taxa (antigo item 2)

- **O defeito:** `engine.caixa` rendia todo o histórico do caixa com **uma** taxa, a do dia da
  apuração. Na primeira mudança do Copom, o rendimento passado de todos os fundos seria refeito
  com a taxa nova e a cota saltaria — em cotas já publicadas no ranking.
- **A correção:** `core/cdi.py` com a `CurvaCDI`. Cada registro de `TaxaCDI` vale **da sua data
  até o registro seguinte**; o dia útil d rende de d para o seguinte à taxa vigente em d (mesma
  convenção do `dias_uteis`). Serve tanto para a série diária do BCB quanto para o cadastro
  manual, que só lança uma linha quando o Copom muda a taxa. O motor recebe a curva em vez de um
  número (`caixa`, `executar`, `executar_lote`, `fechar`, `apurar_dia`); o `adapters.curva_cdi`
  monta a curva com o que está no banco.
- **Sem CDI não há rendimento inventado:** dia sem taxa vigente (antes do primeiro registro) é
  erro (`CDIIndisponivel`), e o `fechar_dia`/`liquidar_semana` param com a mensagem, em vez de
  render zero.
- **O passado não se reescreve:** o admin recusa taxa com data anterior à última apuração (a cota
  de F rendeu com as taxas dos dias antes de F) e taxa fora de 0 a 0,002 ao dia — barra o erro
  mais provável, digitar a porcentagem (0,0508) no lugar da fração (0,000508). O campo ganhou
  texto de ajuda com a fórmula. Migração `0003_taxacdi_vigencia` (só texto de ajuda).
- **`puxar_cdi` reproduzível:** antes pedia "o último valor" ao BCB e o gravava **na data da
  consulta** — rodar com atraso gravava a taxa errada no dia errado. Agora consulta uma janela
  de 10 dias até a véspera, grava cada valor **na data a que se refere**, valida a taxa e pula
  dias anteriores à última apuração.
- **Gráfico:** a linha do CDI usa a mesma curva do caixa (um fundo parado em caixa acompanha a
  linha exatamente). Sem CDI cadastrado desde o primeiro fechamento, a linha fica vazia em vez
  de taxa zero.
- Testes novos: `tests/test_cdi.py` (8: taxa muda no meio do período, passado intacto, taxa
  lançada no fim de semana, falta de CDI, porcentagem no lugar da fração, data repetida) e 7 de
  integração (`TestCurvaCDI`, `TestPuxarCDI`, este com resposta do BCB simulada). Total:
  **55 + 50**, verdes.

**Pendente aqui:** nada do item. A fonte alternativa de CDI virou o item 2 do *A fazer*.

### 2026-10-19 — host decidido, deploy preparado, documentação acertada

- **Commit atrasado:** o trabalho das três sessões de 01/10 ainda não estava no git. Foi
  commitado e enviado (`f8d1116`), a pedido do Gabriel.
- **Host decidido (antigo item 1, agora "subir o deploy"):** a gestão pediu a melhor opção
  grátis, aberta a qualquer pessoa, com teto de R$ 30–50/mês se o grátis não servisse. Ficou
  **Render (site) + Neon (banco) + GitHub Actions (rotina e backup)**. Condições conferidas hoje:
  - Render Free: dorme após 15 min sem acesso (~1 min para acordar), 750 h/mês; o Postgres
    grátis deles **expira em 30 dias** e não tem plano grátis de cron, por isso só o site fica lá.
  - Neon Free: Postgres permanente, sem cartão, 1 GB, 100 CU-h/mês, dorme após 5 min.
  - GitHub Actions: ilimitado em repositório público. Era a dúvida que decidia tudo, e foi
    **testada**: o workflow manual `teste_fontes.yml` rodou o `puxar_precos` real num runner e
    o Yahoo entregou os 30 preços, os 2 índices e o dólar de 16/10.
  - Descartados: PythonAnywhere grátis (sem acesso ao Yahoo, sem tarefa agendada), VMs
    grátis da Oracle/Google (pedem cartão e alguém que administre Linux).
  - **Plano B pago:** PythonAnywhere Developer, US$ 10/mês ou US$ 100/ano (~R$ 43/mês), com
    tudo num lugar só. O plano de US$ 5 de antes não existe mais.
- **Preparado para o deploy:** `render.yaml` (blueprint), `settings.py` lê
  `RENDER_EXTERNAL_HOSTNAME`, e o workflow `rotina_diaria.yml` roda às 19h30 com `TZ` de
  Brasília (sem isso `date.today()` adiantaria um dia), salva um backup `dumpdata` **cifrado**
  (artefato de repositório público é baixável por qualquer conta do GitHub) e reabilita a si
  mesmo, porque o GitHub desliga agendamentos após 60 dias sem atividade. Sem o segredo
  `DATABASE_URL` ele só avisa, para não mandar e-mail de erro toda noite antes do deploy. O ciclo
  de backup e restauração (dumpdata → gpg → loaddata) foi testado no banco de demonstração e as
  contagens bateram. Passo a passo em `MANUAL_ADMIN.md` §8.
- **A API do BCB está quebrada:** toda consulta ao SGS (séries 11, 12 e 4389, com ou sem
  intervalo de datas) devolve, depois de ~30 s, uma página "Requisição inválida!" com status
  200. Falha do GitHub **e** do PC; o último CDI gravado no banco local é de 01/10. O código já
  tratava isso (usa o último CDI gravado). O CDI passa a entrar pelo admin quando o Copom mudar a
  taxa; a fórmula está no manual.
- **Inconsistências corrigidas:**
  - o item "Regulamento desatualizado" saiu: o `REGULAMENTO.md` já cobria preço de execução
    (§4.1), cota diária (§3.4) e aluguel (§4.3);
  - *Estado atual* marcava o agendamento como "a fazer" e dizia 33 testes de integração (são 43);
  - o `MANUAL_ADMIN.md` dizia 43 testes no motor (são 47) e ainda tratava o deploy como "a
    definir".
- O item 2 (CDI) foi reescrito: o problema real é o motor render todo o histórico de caixa com
  uma taxa só.
- **Banco local** atualizado com `rotina_diaria --desde 2026-10-02` até 16/10. O 19/10 falhou
  porque a rotina rodou de manhã, antes do fechamento, como esperado.
- Testes: 47 + 43, verdes. `check --deploy` com ambiente de Render só avisa do HSTS.

**Pendente aqui:** o Gabriel criar as contas e seguir o `MANUAL_ADMIN.md` §8. Depois, rodar o
workflow à mão uma vez e conferir o site.

### 2026-10-01 (noite) — tickers trocados na whitelist (antigo item 7)

- `ELET3.SA` e `JBSS3.SA` não existem mais no Yahoo. Conferido no yfinance em 01/10/2026:
  - **`ELET3.SA` → `AXIA3.SA`**: a Eletrobras virou AXIA Energia; ação ordinária, ~13 mi
    ações/dia.
  - **`JBSS3.SA` → `JBSS32.SA`**: a JBS N.V. levou a listagem principal para Nova York e na
    B3 ficou o BDR. Escolha do Gabriel: o BDR, que mantém o papel em reais e na lista de
    ações B3, como no regulamento (a alternativa era a `JBS` da NYSE, em dólar).
- Trocados em `core/universo.py`, `REGULAMENTO.md` §3.3 e nos preços-base do `semear_demo`.
- Banco local: preços dos dois códigos novos completados de 23/09 a 01/10 com `puxar_precos`.
  Nenhuma ordem nem trade usava os códigos antigos.
- Testes: 47 + 43, verdes.

**Atenção para o futuro:** código de ação muda (fusão, troca de nome, migração de bolsa). Se o
log da rotina mostrar `Sem preço para:` em dia útil por mais de um dia seguido, é esse o
primeiro suspeito.

### 2026-10-01 (tarde) — código pronto para produção; hospedagem em aberto

- **Hospedagem é o gargalo, e não é técnico:** a LIMFIE não gere dinheiro, e até ~R$25/mês
  sairia do bolso de membros que em geral não trabalham. O Gabriel vai levar a decisão à
  gestão; as opções gratuitas e a paga mais simples estão no item 1 de *A fazer*.
- Adiantado o que não depende do host:
  - `DATABASE_URL` (`dj-database-url`): SQLite por padrão, Postgres/MySQL só trocando a variável.
  - Arquivos estáticos com `whitenoise` + `STATIC_ROOT` (`staticfiles/`, já ignorado). Antes, com
    `DEBUG=0`, o site subia sem CSS.
  - Com `DEBUG=0`: redireciona para HTTPS, cookies seguros, `SECURE_PROXY_SSL_HEADER`,
    `DJANGO_CSRF_TRUSTED_ORIGINS`; HSTS por variável, desligado de início.
  - `gunicorn` no `requirements.txt` (fora do Windows, onde não roda).
  - **Novo comando `backup_banco`**: cópia consistente do SQLite (API de backup, segura com o
    site no ar) em `backups/` (ignorado), guardando as 14 mais recentes. O `.bat` da rotina já
    chama depois do `rotina_diaria`. Com Postgres o comando recusa e manda usar o backup do
    provedor.
- Validado com `DEBUG=0`: `check --deploy` só com o aviso de HSTS (intencional), `collectstatic`
  com 127 arquivos, CSS do admin servido (200), HTTP → HTTPS (301), host desconhecido recusado
  (400). Testes: 47 + 43, verdes.

**Pendente aqui:** escolher o host (gestão). Depois disso: subir, testar `puxar_precos` no
servidor, agendar `rotina_diaria` + `backup_banco`, e só então ligar o HSTS.

### 2026-10-01 — agendamento da rotina diária (antigo item 1)

- **Novo comando `rotina_diaria`**, que orquestra `puxar_precos` → `liquidar_semana`
  (1º dia útil da semana) → `fechar_dia` e recupera dias perdidos (ver *Rotina da Mesa*).
  Escolha do Gabriel: um comando único + script pronto, **sem registrar tarefa no sistema**.
  O mesmo comando serve para o Agendador do Windows agora e para o cron do servidor depois do
  deploy; só muda quem dispara.
- **`liquidar_semana` só pega boleta enviada antes do dia de liquidação**
  (`enviada_em__date__lt=dia`). Sem isso, recuperar uma segunda atrasada liquidaria ao preço
  dela as boletas do fim de semana seguinte. Na operação normal nada muda (janela sáb/dom).
- Testes: `_boleta` agora fixa `enviada_em` num sábado (03/10/2026). Antes dependia da data
  real e passaria a falhar a partir de 05/10/2026 com o filtro novo. +9 testes
  (`TestRotinaDiaria` e boleta do próprio dia): 47 do motor + 42 de integração, todos verdes.
- `agendamento/rotina_diaria.bat` (log em `logs/`, no `.gitignore`); `.gitattributes`
  mantém `.bat` em CRLF, porque o `eol=lf` geral pode quebrar o script no Windows.
- Teste de fumaça do `.bat` no banco **local** de demonstração: recuperou 7 dias úteis
  (23/09 a 01/10/2026) com preços reais do yfinance/BCB. Revelou `ELET3.SA` e `JBSS3.SA` sem
  preço (resolvido no mesmo dia, ver entrada da noite).
- Itens de *A fazer* renumerados: Deploy virou o item 1.

**Pendente aqui:** registrar a tarefa no Agendador (comando na *Rotina da Mesa*), quando o
Gabriel quiser; no servidor, depende do deploy (item 1).

### 2026-09-22 (noite) — repositório público e README de passagem

- Projeto publicado em **github.com/gabrielpmarinho/desafio_fenrir** (público).
  Primeiro commit com 51 arquivos; `db.sqlite3`, `.secret_key`, `__pycache__/` e
  `.pytest_cache/` confirmados fora do versionamento.
- **A `SECRET_KEY` de desenvolvimento saiu do código.** Estava embutida como fallback no
  `settings.py`, logo abaixo de um comentário dizendo que chave não vai em arquivo
  versionado. Agora: sem `DJANGO_SECRET_KEY` e fora de `DEBUG`, o servidor levanta
  `ImproperlyConfigured` e não sobe; em desenvolvimento a chave é gerada na primeira
  execução e guardada em `.secret_key`, ignorado pelo git. Gerar a cada boot deslogaria
  todo mundo a cada reload do runserver.
- `.gitattributes` com `eol=lf` (escrito no Windows, roda em Linux) e seção
  **Configuração** no README com as variáveis de ambiente.
- README reescrito com a moldura de **passagem de bastão**: o que é o sistema para quem
  nunca viu, o mapa dos quatro documentos, o ciclo de uma edição e a seção *Decisões que
  parecem estranhas e não são* — as escolhas que um sucessor desfaria sem saber o preço.
- `MANUAL_ADMIN.md` deixou de se declarar "de uso restrito": agora é público junto com o
  repositório, com o aviso de não guardar senha nem dado de participante ali.
- Removido o arquivo vazio `VS` (0 bytes, sobra de algum comando).

**Pendente aqui:** licença e topics do repositório (ver *A fazer*).

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
core/          motor puro, sem Django   engine · cdi · models · custos · metricas · calendario · universo
desafio/       app Django               models · admin · views · forms · adapters · urls
  servicos/    carteira (visão, série de cotas, ranking) · precos (yfinance/BCB)
  management/  rotina_diaria · backup_banco · puxar_precos · liquidar_semana · fechar_dia · semear_demo
config/        settings · urls · asgi/wsgi
templates/     base + dashboard · ordens · extrato · ranking · login
agendamento/   rotina_diaria.bat (Agendador do Windows; log em logs/)
.github/       workflows: rotina_diaria (produção) · teste_fontes (Yahoo/BCB, manual)
render.yaml    blueprint do site no Render
tests/         test_engine · test_cdi · test_custos · test_metricas · test_calendario   (motor)
desafio/tests.py                                                            (integração)
```

Modelos do banco: `Fundo` · `Participante` · `Ordem` · `Trade` · `Lancamento` ·
`PrecoFechamento` · `Cotacao` · `TaxaCDI` · `Fechamento`.
No motor, os equivalentes são dataclasses congeladas, mais `Rejeicao` e os enums
`Moeda`, `Direcao` e `TipoLancamento`.
