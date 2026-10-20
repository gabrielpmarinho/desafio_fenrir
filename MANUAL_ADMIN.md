# Manual da Mesa — Terminal Fenrir

Documento da diretoria: descreve como a Mesa opera o desafio. É público junto
com o repositório — não guarde senha, chave nem dado de participante aqui.
Substitui o `Manual_do_Administrador_de_Desafio_FENRIR___LIMFIE.pdf`, que
descreve a versão antiga (Streamlit + Google Sheets) e **não vale mais**.

> **Status:** motor, banco, Mesa, comandos, telas do participante e rotina
> diária prontos e testados. O host está decidido (Render + Neon + GitHub
> Actions, §8); falta criar as contas e subir.

---

## 1. Arquitetura

| Camada | Tecnologia | Papel |
|---|---|---|
| `core/` ✅ | Python puro, sem dependências | Toda a economia do desafio |
| `desafio/` ✅ | Django | Models, Mesa (admin) e comandos |
| Telas do participante ✅ | Django | Carteira, ordens, extrato, ranking |
| Banco ✅ | SQLite local; Postgres do Neon em produção (`DATABASE_URL`) | Ledger, fechamentos, cadastro. Cópia diária com `backup_banco` (SQLite) ou artefato cifrado do workflow (Neon) |
| Preços ✅ | yfinance + API do BCB | Fechamento diário e CDI |
| Rotina diária ✅ | `rotina_diaria`: Agendador do Windows no PC, GitHub Actions em produção | Puxa preços, liquida, apura |
| Deploy 🟨 | Render (site) + Neon (banco) + GitHub Actions (rotina), tudo grátis | Decidido em 19/10/2026; falta criar as contas (§8) |

A regra de ouro: **`core/` não importa Django, não acessa rede e não conhece
banco**. Se você precisar mudar uma regra do desafio, ela está em `core/`, e o
teste correspondente falha se você errar. Foi a ausência dessa separação que
quebrou a versão anterior.

### Por que o ledger é append-only

Caixa e posições **não são armazenados**. São calculados a partir do histórico
de eventos. Consequência prática para você, administrador:

- Nunca "corrija" uma posição editando um número. Lance um evento de ajuste.
- Um erro de liquidação se conserta com um lançamento contrário, não apagando
  linha. O histórico tem que continuar batendo.
- Se a mesma ordem for liquidada duas vezes, aparecem duas linhas no ledger —
  visível e reversível. Na versão antiga isso acontecia silenciosamente.

---

## 2. Regras econômicas (como estão implementadas)

| Regra | Valor | Onde |
|---|---|---|
| Patrimônio inicial | R$ 100.000.000,00 | `models.Fundo` |
| Cotas emitidas | 1.000.000 | `models.Fundo` |
| Cota inicial | 100,00 | derivada |
| CDI sobre caixa livre | capitalizado por dia útil, cada dia à taxa vigente nele | `engine.caixa`, `core/cdi.py` |
| Alavancagem | proibida: \|comprado\| + \|vendido\| ≤ patrimônio | `engine.executar` |
| Aluguel de short | 0,4% a.m., 1/20 por dia útil (0,02% a.d.) | `custos.py` |
| Câmbio | convertido no momento da execução | `models.Trade` |
| Universo | whitelist fechada de 30 ativos | `core/universo.py` |

### 2.1 Preço de execução — **regra oficial**

Só se usa **preço de fechamento**. O sistema não olha preço intradiário em
momento nenhum.

- Ordens são enviadas pelos fundos **durante o fim de semana**.
- São liquidadas **na segunda-feira, ao preço de fechamento da segunda**.
- Se a segunda não for dia útil, usa-se o primeiro dia útil da semana.

Isso resolve o pior defeito da versão anterior, onde a ordem executava ao preço
do instante em que o administrador clicava no botão — ou seja, o resultado do
aluno dependia do horário em que você lembrava de rodar a mesa.

### 2.2 Cota diária

A cota muda **uma vez por dia útil**, depois do fechamento do mercado. Não há
cota intradiária. A rotina de fechamento (§3.2) grava uma foto imutável por
fundo por dia, e é essa série que alimenta ranking, gráfico, volatilidade e
Sharpe.

### 2.3 Aluguel do short

Copiado do Desafio JGP: **0,4% ao mês sobre o financeiro da posição vendida,
cobrado 1/20 por dia**. É linear — dobrar a posição dobra o custo.

- Incide por dia útil em que a posição vendida está aberta no fechamento,
  inclusive o dia em que foi montada.
- É marcado pelo preço de fechamento do próprio dia.
- Vira um `Lancamento` do tipo `ALUGUEL_SHORT` no ledger, com descrição dizendo
  sobre quais ativos incidiu. Fica auditável.

> ⚠️ A tabela progressiva por faixa de financeiro (0,1% a 0,4%) que aparece no
> regulamento do JGP **não é aluguel** — é slippage de ordens STOP/ON STOP. O
> Fenrir só tem ordem a mercado, então não se aplica. A função existe em
> `custos.custo_execucao_progressivo` caso o regulamento mude, mas hoje não é
> chamada por ninguém.

---

## 3. Rotina operacional

**No dia a dia ninguém precisa rodar nada.** O agendador chama o
`python manage.py rotina_diaria`, que faz 3.1 e 3.2 na ordem certa, só em dia útil,
e recupera sozinho os dias que ficaram para trás.

- **Em produção:** o workflow *Rotina diária* do GitHub Actions, às 19h30 de
  Brasília. O log é o da execução, na aba *Actions* do repositório; falha chega
  por e-mail ao dono do repositório.
- **No PC (desenvolvimento):** o Agendador do Windows com
  `agendamento/rotina_diaria.bat`, às 21h; log em `logs/rotina_AAAA-MM.log`. Como
  registrar está no README, seção *Rotina da Mesa*.

Os comandos abaixo continuam valendo para conferir (`--simular`), corrigir
(`--refazer`) ou reprocessar um dia à mão.

### 3.1 Segunda-feira — liquidar as ordens da semana ✅

```bash
python manage.py puxar_precos --data AAAA-MM-DD
python manage.py liquidar_semana --data AAAA-MM-DD --simular   # confere
python manage.py liquidar_semana --data AAAA-MM-DD             # grava
```

O `--simular` mostra o que aconteceria sem tocar no banco. **Use sempre antes**,
principalmente na primeira semana de uma edição nova.

As boletas são processadas por fundo, na ordem de chegada. Cada fundo é uma
transação isolada: rejeição num fundo não afeta outro.

Ordens são rejeitadas, nunca ajustadas, quando: o ticker está fora da whitelist,
falta preço, ou a operação estouraria o limite de alavancagem. Duas ordens
individualmente válidas podem estourar o limite juntas — a segunda é barrada, e
isso é intencional.

### 3.2 Todo dia útil, após o fechamento — apurar as cotas ✅

```bash
python manage.py puxar_precos --data AAAA-MM-DD
python manage.py fechar_dia --data AAAA-MM-DD
```

Sem `--data`, os comandos usam o dia de hoje. Em dia não útil eles avisam e não
fazem nada, então pode agendar de segunda a domingo sem medo.

Para cada fundo, grava o fechamento do dia e, se o fundo estiver vendido, o
lançamento de aluguel — **na mesma transação**, para o custo nunca se perder.

**É idempotente.** Rodar duas vezes no mesmo dia não cobra aluguel em dobro: o
comando detecta a apuração existente e pula, e o banco ainda tem uma constraint
(`aluguel_unico_por_dia`) como segunda trava. Se precisar mesmo refazer um dia,
use `--refazer`, que apaga a apuração e o aluguel daquele dia antes de recalcular.

### 3.3 Fim do desafio

Ranking final = composição do regulamento §6.2: retorno acumulado, métricas de
risco (`metricas.sharpe` e `metricas.volatilidade_anualizada`, anualizadas por
252) e a nota da apresentação ao comitê.

---

## 4. Cadastro de uma nova edição ✅

Tudo pelo admin, em `/admin`. Nada disso exige mexer em código:

1. Criar os fundos no admin (nome, data de início, caixa inicial).
2. Criar os usuários e vinculá-los aos fundos.
3. Conferir a whitelist em `core/universo.py` — esta sim é código, e é
   proposital: mudar o universo de ativos é decisão de regulamento.

Na versão antiga os nomes dos fundos e as senhas ficavam escritos no fonte, e
receber uma turma nova exigia editar o arquivo e refazer o deploy.

---

## 5. Segurança

- **Nunca** commitar credencial. O `.gitignore` já bloqueia `*.json`, `.env` e
  `credenciais*`. A versão antiga tinha `.gitignore` vazio e a chave do service
  account ficou solta na pasta do projeto.
- Segredos vão em variável de ambiente, nunca em arquivo versionado.
- Senha de usuário é responsabilidade do Django (hash), nunca escrita em código.
- A chave antiga do projeto `desafio-fenrir` no Google Cloud deve ser
  **revogada** — o Google Sheets não é mais o banco.

---

## 6. Troubleshooting

| Sintoma | O que verificar |
|---|---|
| Cota não mudou hoje | O `fechar_dia` rodou? Era dia útil? O calendário tem esse feriado? Veja `logs/rotina_AAAA-MM.log` |
| Fundo vendido sem custo de aluguel | O `Lancamento` do dia foi persistido no ledger? |
| Aluguel cobrado em dobro | O `fechar_dia` rodou duas vezes para o mesmo dia |
| Ordem rejeitada sem motivo claro | A mensagem em `Rejeicao.motivo` traz o número; conferir contra o patrimônio do fundo |
| Preço faltando no fechamento | yfinance falhou para o ticker; a apuração do dia não pode rodar pela metade. Se persistir por dias, o código pode ter mudado (ex.: ELET3 → AXIA3 em 2026): atualizar `core/universo.py` e o regulamento |
| Posição com sinal invertido | Ler o ledger: quantidade positiva é compra, negativa é venda |
| Aluno não consegue enviar ordem | A janela só abre sábado e domingo (regulamento §4) |
| Aluno logou e tomou 404 | Usuário sem `Participante` vinculado a um fundo |
| "CDI indisponível no BCB" no log | Esperado desde out/2026: a API SGS do BCB devolve uma página "Requisição inválida!" depois de ~30 s, de qualquer lugar (testado do GitHub e de um PC no Brasil em 19/10/2026). Cada taxa gravada vale até a seguinte, então a rotina segue com o último CDI. Quando o Copom mudar a taxa, cadastrar o novo CDI no admin (§8, passo 6) |
| "Nenhuma taxa CDI cadastrada" | Banco novo sem CDI: cadastrar no admin (§8, passo 6) |
| "Sem CDI vigente em dd/mm/aaaa" | A primeira taxa cadastrada é posterior ao início do fundo. Cadastrar uma com data igual ou anterior ao início |
| Admin recusa a taxa: "Já há cota apurada até…" | De propósito: taxa com data anterior à última apuração mudaria cotas já publicadas. Use a data indicada ou depois |
| Site demora ~1 min para abrir | Render grátis dorme após 15 min sem acesso; o primeiro acesso acorda. Não é erro |
| Rotina parou de rodar sozinha | Workflow desabilitado (aba *Actions* → *Rotina diária* → *Enable workflow*); depois rodar à mão com `desde` = dia seguinte ao último fechamento |

Antes de mexer em qualquer regra, rode `python -m pytest -q`. São 55 testes e
levam menos de um décimo de segundo. Quatro deles reproduzem exatamente os bugs
que quebraram a versão anterior — se algum falhar, você reintroduziu um deles.

---

## 7. Pendências

- [x] ~~Agendamento dos comandos~~ — `rotina_diaria`; no PC pelo
      `agendamento/rotina_diaria.bat`, em produção pelo workflow do GitHub Actions
- [ ] Deploy — host decidido (Render + Neon + GitHub Actions, §8); falta criar
      as contas e subir
- [x] ~~Telas do participante~~
- [x] ~~Regulamento atualizado~~ — ver `REGULAMENTO.md` (versão 2)
- [x] ~~Comandos operacionais~~
- [x] ~~Integração de preços e CDI~~ (série 12 do SGS; a versão antiga usava a
      11, que é Selic). Desde out/2026 a API do BCB está falhando; o CDI entra
      pelo admin (§8, passo 6)
- [x] ~~CDI dia a dia no motor~~ — cada dia rende a taxa vigente nele
      (`core/cdi.py`, 20/10/2026); o passado não é refeito quando o CDI muda

---

## 8. Deploy (Render + Neon + GitHub Actions)

Decidido em 19/10/2026. Tudo no plano gratuito, sem cartão e sem servidor Linux
para administrar. O motivo de cada escolha está no README (registro de 19/10/2026).

| Peça | Serviço | Plano | O que faz |
|---|---|---|---|
| Site | Render | Free | Django + gunicorn em `fenrir-xxxx.onrender.com`, aberto a qualquer um |
| Banco | Neon | Free | Postgres de 1 GB que não expira |
| Rotina e backup | GitHub Actions | grátis (repo público) | `rotina_diaria` às 19h30 + backup cifrado |

**Limitações conhecidas, todas aceitáveis para o desafio:**
- O site dorme após 15 min sem acesso; o primeiro acesso leva ~1 min para acordar.
- A API do BCB está falhando (não é coisa do host: falha também do Brasil). O CDI
  entra pelo admin quando o Copom muda a taxa (passo 6); a rotina usa o último
  CDI gravado.
- O plano grátis do Render não tem terminal: comandos de manutenção
  (`createsuperuser`, reprocessamentos) rodam **do seu PC** apontando para o Neon.

### Passo a passo (uma vez só)

1. **Neon** (neon.com, entrar com o GitHub): criar o projeto `fenrir`, região
   **AWS US East 1 (N. Virginia)**. Copiar a *connection string* **direta** (a sem
   `-pooler` no host). Ela tem senha: não colar em arquivo nem em chat.
2. **Render** (render.com, entrar com o GitHub): *New → Blueprint* → repositório
   `desafio_fenrir`. O Render lê o `render.yaml`, pede o `DATABASE_URL` (colar a
   string do Neon) e gera a `DJANGO_SECRET_KEY` sozinho. O build já roda o
   `migrate`. O endereço aparece no painel (`https://fenrir-xxxx.onrender.com`).
3. **GitHub** → repositório → *Settings → Secrets and variables → Actions*:
   - `DATABASE_URL`: a mesma string do Neon;
   - `BACKUP_SENHA`: senha longa, guardada com a diretoria (sem ela o backup
     não abre).
4. **Superusuário**, do seu PC, num PowerShell na pasta do projeto:
   ```powershell
   $env:DATABASE_URL = "<string do Neon>"
   python manage.py createsuperuser
   ```
   Feche o terminal depois: a variável some com ele.
5. **Edição**: em `https://<endereço>/admin`, cadastrar fundos e usuários (§4).
6. **CDI**: no admin, *Taxas CDI → Adicionar*, com a taxa **diária em fração**:
   `(1 + CDI anual)^(1/252) − 1`. Ex.: CDI de 13,65% a.a. → `1,1365^(1/252) − 1` =
   `0.00050788` (o admin recusa `0.050788`, a porcentagem). A data é o **primeiro dia em que
   a taxa vale**; cada taxa vale até a seguinte, então só se cadastra de novo quando o Copom
   mudar a Selic. No banco novo, a primeira taxa precisa ter data igual ou anterior ao início
   dos fundos. Não dá para cadastrar com data anterior à última apuração: se o Copom mudou a
   taxa e você só viu dias depois, cadastre com a data de hoje.
   (Se a API do BCB voltar, a rotina passa a gravar sozinha e este passo vira só
   conferência.)
7. **Teste**: aba *Actions* → *Rotina diária* → *Run workflow*. O log deve mostrar
   preços gravados e a cota de cada fundo.

### Restaurar um backup

Na execução desejada da *Rotina diária*, baixar o artefato `backup-<número>`
(fica 30 dias), descompactar o zip e, com `DATABASE_URL` apontando para um banco
vazio e migrado:

```bash
gpg -d fenrir.json.gz.gpg > fenrir.json.gz   # pede a BACKUP_SENHA
python manage.py loaddata fenrir.json.gz
```

### Plano B (pago)

Se o plano grátis não aguentar (Yahoo bloquear o GitHub, Render ou Neon mudarem
as regras): **PythonAnywhere Developer**, US$ 10/mês ou US$ 100/ano (~R$ 43/mês no
câmbio de out/2026). Site, banco, internet liberada e tarefa agendada no mesmo
lugar, sem dormir e sem Linux. Aí volta a valer o `backup_banco` com SQLite.
