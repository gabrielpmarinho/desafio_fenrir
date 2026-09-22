# Manual da Mesa — Terminal Fenrir

Documento da diretoria: descreve como a Mesa opera o desafio. É público junto
com o repositório — não guarde senha, chave nem dado de participante aqui.
Substitui o `Manual_do_Administrador_de_Desafio_FENRIR___LIMFIE.pdf`, que
descreve a versão antiga (Streamlit + Google Sheets) e **não vale mais**.

> **Status:** motor, banco, Mesa, comandos e telas do participante prontos e
> testados. Faltam o agendamento dos comandos e o deploy. As seções marcadas
> com ⬜ descrevem o que ainda não existe.

---

## 1. Arquitetura

| Camada | Tecnologia | Papel |
|---|---|---|
| `core/` ✅ | Python puro, sem dependências | Toda a economia do desafio |
| `desafio/` ✅ | Django | Models, Mesa (admin) e comandos |
| Telas do participante ✅ | Django | Carteira, ordens, extrato, ranking |
| Banco ✅ | SQLite (dev) / Postgres (produção) | Ledger, fechamentos, cadastro |
| Preços ✅ | yfinance + API do BCB | Fechamento diário e CDI |
| Deploy ⬜ | a definir | Hospedagem paga de baixo custo |

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
| CDI sobre caixa livre | capitalizado por dia útil | `engine.caixa` |
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
| Cota não mudou hoje | O `fechar_dia` rodou? Era dia útil? O calendário tem esse feriado? |
| Fundo vendido sem custo de aluguel | O `Lancamento` do dia foi persistido no ledger? |
| Aluguel cobrado em dobro | O `fechar_dia` rodou duas vezes para o mesmo dia |
| Ordem rejeitada sem motivo claro | A mensagem em `Rejeicao.motivo` traz o número; conferir contra o patrimônio do fundo |
| Preço faltando no fechamento | yfinance falhou para o ticker; a apuração do dia não pode rodar pela metade |
| Posição com sinal invertido | Ler o ledger: quantidade positiva é compra, negativa é venda |
| Aluno não consegue enviar ordem | A janela só abre sábado e domingo (regulamento §4) |
| Aluno logou e tomou 404 | Usuário sem `Participante` vinculado a um fundo |

Antes de mexer em qualquer regra, rode `python -m pytest -q`. São 43 testes e
levam menos de um décimo de segundo. Quatro deles reproduzem exatamente os bugs
que quebraram a versão anterior — se algum falhar, você reintroduziu um deles.

---

## 7. Pendências

- [ ] Agendamento dos comandos (cron ou GitHub Actions)
- [ ] Deploy e banco Postgres
- [x] ~~Telas do participante~~
- [x] ~~Regulamento atualizado~~ — ver `REGULAMENTO.md` (versão 2)
- [x] ~~Comandos operacionais~~
- [x] ~~Integração de preços e CDI~~ (série 12 do SGS; a versão antiga usava a
      11, que é Selic)
