# Regulamento Oficial — Desafio FENRIR

**LIMFIE — Liga de Mercado Financeiro do Instituto de Economia da UFRJ**

Documento oficial contendo as normas de participação, regras de operação e
critérios de avaliação do Desafio Fenrir. O ato de inscrição implica na
concordância integral com este regulamento.

*Versão 2 — atualizada para o Terminal Fenrir reescrito. Substitui a versão
anterior em PDF.*

---

## 1. Objetivo e Propósito

O Desafio Fenrir é uma jornada gamificada que simula o ambiente de uma gestora
de investimentos (Asset Management) em um universo controlado. O objetivo é
educar os participantes a respeito das dificuldades e desafios enfrentados por
gestores no exercício de suas funções.

Os participantes deverão administrar uma carteira de investimentos teórica,
alocando recursos de forma embasada. O Desafio busca incentivar a integração
entre os núcleos de **Macro e Data Science**, **Risco e Backoffice** e **Equity
Research**, exigindo que os grupos desenvolvam análises profundas para a escolha
de ativos, hedge e proteção de capital.

## 2. Elegibilidade e Formação dos Grupos

### 2.1. Participantes

A participação no Desafio Fenrir é exclusiva para membros e alumnis da LIMFIE.

- Cada grupo representa uma "Gestora" e deve criar um Fundo de Investimento
  fictício, cujo nome deve ser aprovado pela gestão.
- O número de membros em um grupo pode variar, porém o grupo deve ser formado
  por pelo menos 1 membro de cada núcleo.

## 3. Dinâmica do Desafio e Plataforma

### 3.1. O Terminal Fenrir

A competição será realizada através do Terminal FENRIR, no qual os participantes
farão o envio de ordens e o acompanhamento de suas carteiras.

### 3.2. Capital e Alocação

- Todo fundo iniciará com um patrimônio fictício de **R$ 100.000.000,00** (cem
  milhões de reais). A Cota Original de cada Fundo receberá o valor simbólico de
  **100,00**.
- O Capital que não estiver sendo utilizado na compra de ativos (Caixa Livre)
  será automaticamente considerado como aplicado e renderá a **taxa do CDI**,
  capitalizada a cada dia útil. O rendimento é incorporado ao próprio caixa e
  **não se perde ao operar**.
- Os Fundos **não podem se alavancar**. Posições compradas e vendidas são
  somadas **em módulo** e precisam ser menores ou iguais ao patrimônio do fundo.

### 3.3. Universo de Ativos

Os grupos poderão investir exclusivamente na lista fechada de ativos (Whitelist)
disponibilizada no Terminal. Ativos internacionais estão sujeitos ao risco
cambial (FX), sendo convertidos automaticamente para o Real (BRL) pela Mesa de
Operações, pela cotação vigente no momento da execução.

**ETFs disponíveis:** SPY (S&P 500) · QQQ (Nasdaq 100) · BOVA11.SA (Ibovespa) ·
MCHI (Bolsa da China) · TLT (Títulos EUA 20+ anos) · USO (Petróleo) · GLD (Ouro)
· IMAB11.SA (Renda Fixa/Inflação BR) · XFIX11.SA (Fundos Imobiliários BR) · VNQ
(Imóveis EUA) · XLV (Saúde EUA) · IBIT (Bitcoin) · NLR (Energia Nuclear) · BOTZ
(IA e Robótica) · PAVE (Infraestrutura EUA) · XLK (Tecnologia EUA) · XLF
(Financeiro EUA)

**Ações disponíveis (B3):** PETR4.SA (Petrobras) · VALE3.SA (Vale) · ITUB4.SA
(Itaú) · BBAS3.SA (Banco do Brasil) · WEGE3.SA (WEG) · ELET3.SA (Eletrobras) ·
RENT3.SA (Localiza) · RADL3.SA (Raia Drogasil) · SUZB3.SA (Suzano) · JBSS3.SA
(JBS) · B3SA3.SA (B3) · ABEV3.SA (Ambev) · MGLU3.SA (Magazine Luiza)

### 3.4. Apuração da Cota

**O Desafio Fenrir opera exclusivamente com preços de fechamento.** Não há
apuração intradiária em nenhuma etapa da competição.

- A cota de cada Fundo é apurada **uma vez por dia útil**, após o fechamento do
  mercado, e permanece inalterada até a apuração seguinte.
- A apuração marca todas as posições a mercado pelo preço de fechamento do dia,
  soma o Caixa Livre com o CDI do período e divide pelo número de cotas.
- Cada apuração é registrada de forma definitiva. O histórico de cotas não é
  recalculado a posteriori, ainda que os preços sejam posteriormente revisados
  pela fonte de dados.

## 4. Operações e Envio de Ordens

As ordens responsáveis pelos investimentos dos Fundos serão passadas
semanalmente, **exclusivamente aos finais de semana**, através do Terminal
Fenrir.

- Cada Fundo deve designar os responsáveis pelo envio das ordens.
- Todas as ordens devem conter, de forma clara, o ativo alvo, a direção (compra
  ou venda) e a quantidade de cotas.
- O não envio de ordens em uma semana significa que o fundo optou por manter a
  carteira inalterada.
- Só existe **ordem a mercado**. O Terminal não aceita ordens com preço
  determinado, stop ou similares.

### 4.1. Preço de Execução

As ordens enviadas durante o final de semana são liquidadas pela Mesa na
**segunda-feira seguinte, pelo preço de fechamento da própria segunda-feira**.
Caso a segunda-feira não seja dia útil, vale o fechamento do primeiro dia útil
da semana.

A regra é a mesma para todos os Fundos e independe do horário em que a ordem foi
enviada ou em que a Mesa processou o lote.

### 4.2. Rejeição de Ordens

A Mesa processa as boletas de cada semana **na ordem de chegada**. Uma ordem é
**rejeitada por inteiro**, nunca ajustada parcialmente, quando:

- o ativo não pertence à Whitelist (§3.3);
- não há preço de fechamento disponível para o ativo na data de liquidação;
- a execução faria a exposição bruta do Fundo (comprado + vendido, em módulo)
  superar o seu patrimônio, violando §3.2.

Duas ordens individualmente válidas podem, somadas, estourar o limite de
exposição. Nesse caso a **segunda a chegar** é rejeitada. Os Fundos são
comunicados das rejeições com o respectivo motivo.

### 4.3. Custos de Operação

Posições **vendidas** (short) incorrem em custo de aluguel de **0,4% ao mês**
sobre o financeiro da posição. Cada dia em uma posição vendida custa **1/20 do
valor mensal**, ou seja, 0,02% por dia útil.

- O custo é **linear**: dobrar o tamanho da posição dobra o custo.
- Incide em todo dia útil em que a posição estiver aberta no fechamento,
  inclusive o dia em que foi montada, e cessa no dia em que for encerrada.
- É calculado sobre o financeiro marcado pelo preço de fechamento do dia e
  debitado diretamente do Caixa Livre do Fundo.
- Aparece de forma discriminada no extrato do Fundo no Terminal.

Não há custo de corretagem, emolumentos ou slippage sobre ordens a mercado.

## 5. Relatórios e Entregáveis Mensais

A gestão de portfólio exige prestação de contas. Cada Fundo participante é
responsável por gerar e enviar uma **Carta ao Investidor** (Relatório Mensal)
para a Banca Julgadora.

### 5.1. A Carta ao Investidor

Este documento deve explicar as decisões tomadas pelos gestores, abordando:

- Situação de mercado e opinião do grupo acerca do cenário macroeconômico.
- Análise breve do mercado acionário brasileiro e americano.
- Justificativas teóricas e práticas para a entrada, manutenção ou saída de
  posições.
- Avaliação do posicionamento da carteira frente a cenários de risco (Hedge).

### 5.2. Penalidades

O atraso no envio do Relatório Mensal acarreta a perda de pontos na nota final
da etapa. A falta reiterada de relatórios provoca a desclassificação sumária do
Fundo e de seus gestores do Desafio.

## 6. Fim do Desafio e Premiação

Os Fundos com melhor classificação ao final do período operacional estipulado
anteriormente ao começo do desafio serão considerados finalistas.

### 6.1. O Comitê Final

Os finalistas deverão realizar uma apresentação (Comitê de Investimentos) para
os outros membros da LIMFIE. O objetivo é defender suas teses de investimento
com base em fatos, evidências e uso de teorias pertinentes.

### 6.2. Critérios de Premiação

A determinação do vencedor se dará pela composição dos seguintes critérios:

- **Resultado Absoluto:** diferença percentual entre a Cota Inicial e a Cota
  Final do fundo.
- **Métricas de Risco:** Índice de Sharpe e volatilidade da carteira, calculados
  sobre a **série diária de cotas de fechamento** (§3.4), anualizados por 252
  dias úteis, usando o CDI do período como taxa livre de risco.
- **Apresentação Final:** clareza, coerência da estratégia e profundidade das
  análises setoriais e macroeconômicas apresentadas à Banca.

Em caso de empate, o Fundo vencedor será aquele que receber a nota mais alta por
sua Apresentação Final.

### 6.3. Premiação

O grupo vencedor ganha:

- Um parabéns de cada membro da liga.
- Direito de se gabar como campeões (até o começo do próximo desafio).
- Uma rodada de bebidas, da escolha de cada membro, no próximo encontro da liga.
  A rodada deve ser paga pelo presidente e vice-presidente vigentes. Caso o
  presidente e/ou o vice-presidente fizerem parte do grupo vencedor, eles terão
  que pagar uma rodada para todos os presentes.

## 7. Regras de Desclassificação

A organização se reserva o direito de desclassificar equipes que não cumprirem
os requisitos estabelecidos. Serão eliminados sumariamente os grupos que:

- Copiarem, total ou parcialmente, relatórios e cartas de outros grupos ou de
  instituições do mercado.
- Utilizarem ou tentarem utilizar informações privilegiadas (insider trading)
  para a constituição de suas carteiras.
- Apresentarem qualquer tipo de conduta inadequada ou fraude operando contra o
  patrimônio de outros grupos e da plataforma.

---

Desejamos a todos um excelente desafio.

**Diretoria LIMFIE UFRJ**
