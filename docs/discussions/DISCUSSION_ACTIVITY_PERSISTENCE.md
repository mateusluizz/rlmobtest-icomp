# Discussao: Persistencia de Activities Descobertas

**Data:** 2026-02-01
**Status:** Em discussao
**Arquivo relacionado:** `rlmobtest/__main__.py`

---

## Contexto

Durante o treinamento do agente RL, o sistema rastreia activities (telas) descobertas no aplicativo Android. Atualmente, ao retomar um treinamento de um checkpoint, a mensagem "New activity discovered" aparece novamente para activities ja vistas em execucoes anteriores.

## Comportamento Atual

### Como funciona

```python
# Linha 1115 - Inicio de cada episodio
activities = [activity_actual]  # Lista reiniciada

# Linha 1182-1184 - Durante o episodio
if activity not in activities:
    reward += 10  # Bonus de exploracao
    activities.append(activity)
```

### Caracteristicas

- A lista `activities` e reiniciada no inicio de **cada episodio**
- Activities descobertas **nao sao salvas** no checkpoint
- O bonus de +10 e dado toda vez que uma activity e visitada pela primeira vez **no episodio atual**

### O que e salvo no checkpoint

```python
checkpoint = {
    "episode": episode,
    "steps_done": steps_done,
    "model_state_dict": model.state_dict(),
    "optimizer_state_dict": optimizer.state_dict(),
    "metrics": {...},
    "feature_size": feature_size,
    # activities NAO e salvo
}
```

---

## Proposta de Mudanca

Persistir a lista de activities descobertas globalmente, tanto entre episodios quanto entre execucoes (via checkpoint).

### Implementacao necessaria

1. Salvar `discovered_activities` no checkpoint
2. Carregar ao retomar treinamento
3. Manter lista global durante toda a sessao de treinamento

---

## Analise Comparativa

| Aspecto | Comportamento Atual | Com Persistencia |
|---------|---------------------|------------------|
| **Bonus de exploracao** | +10 a cada episodio para activities "novas" | +10 apenas na primeira descoberta absoluta |
| **Incentivo a explorar** | Constante em todos os episodios | Diminui com o tempo |
| **Memoria do agente** | Policy aprende, mas nao ha registro explicito | Registro explicito de cobertura |
| **Complexidade** | Simples | Requer gerenciamento de estado adicional |

---

## Argumentos a Favor do Comportamento Atual

1. **Incentivo continuo de exploracao**
   - O agente sempre tem motivacao para visitar diferentes telas
   - Evita que o agente fique "preso" em um padrao apos muitos episodios

2. **Consistencia com RL classico**
   - Em RL, cada episodio e tipicamente tratado como independente
   - A policy (rede neural) e quem "lembra" o conhecimento, nao uma lista externa

3. **Simplicidade**
   - Menos estado para gerenciar
   - Menos pontos de falha ao retomar checkpoints

4. **Robustez a mudancas no app**
   - Se o app mudar (nova versao), nao ha lista obsoleta

---

## Argumentos a Favor da Persistencia

1. **Cobertura real do app**
   - Permite medir quantas activities unicas foram descobertas no total
   - Metrica mais precisa de exploracao

2. **Foco em novidade real**
   - Agente so recebe bonus por descobertas genuinamente novas
   - Pode acelerar convergencia para politica otima

3. **Continuidade entre execucoes**
   - Retomar treinamento mantem contexto completo
   - Logs mais informativos sobre progresso real

4. **Analise pos-treinamento**
   - Lista de activities descobertas serve como documentacao
   - Facilita analise de cobertura do app

---

## Perguntas para Discussao

1. **Objetivo principal do treinamento**
   - Maximizar cobertura de activities?
   - Encontrar bugs/crashes?
   - Aprender navegacao eficiente?

2. **Duracao esperada do treinamento**
   - Poucos episodios: persistencia pode nao fazer diferenca
   - Muitos episodios: persistencia muda significativamente os rewards

3. **Metricas de sucesso**
   - Como medimos se o agente esta "aprendendo bem"?
   - A lista de activities faz parte dessa metrica?

4. **Comportamento desejado do agente treinado**
   - Deve continuar explorando ou focar em caminhos conhecidos?

---

## Opcoes de Implementacao (se decidido persistir)

### Opcao A: Persistencia total
- Salvar todas as activities no checkpoint
- Manter entre episodios e entre execucoes
- Bonus de +10 apenas para descobertas absolutamente novas

### Opcao B: Persistencia por sessao
- Manter lista durante uma execucao (entre episodios)
- Reiniciar ao carregar checkpoint
- Compromise entre exploracao e novidade

### Opcao C: Sistema hibrido
- Bonus menor (+5) para activities ja vistas globalmente
- Bonus maior (+10) para activities nunca vistas
- Mantem incentivo mas valoriza novidade real

---

## Proximos Passos

- [ ] Discutir com equipe
- [ ] Definir objetivo principal do treinamento
- [ ] Decidir abordagem
- [ ] Implementar se necessario
- [ ] Validar com experimentos comparativos

---

## Referencias

- Codigo: `rlmobtest/__main__.py` linhas 1115, 1182-1188
- Checkpoint: `rlmobtest/__main__.py` linhas 395-410
