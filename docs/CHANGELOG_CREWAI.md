# Changelog - CrewAI Transcriber Integration

## Data: 2026-01-31

### Resumo

Adicionado novo módulo de transcrição baseado em **CrewAI** para geração de test cases a partir de logs de interação mobile. O módulo utiliza agentes inteligentes com suporte a few-shot learning e preparação para processamento multimodal (texto + imagens).

---

## Arquivos Modificados

### `transcription/crew_transcriber.py` (novo)

Novo módulo que implementa transcrição de test cases usando CrewAI.

**Principais componentes:**

| Função/Classe | Descrição |
|---------------|-----------|
| `create_llm()` | Cria instância LLM para CrewAI (Ollama) |
| `create_test_case_agent()` | Cria agente especializado em gerar test cases |
| `transcribe_single()` | Transcreve um único test case |
| `transcribe_folder()` | Processa pasta completa com filtro de similaridade |
| `MultimodalInput` | Classe para suporte futuro a texto + imagens |

**Configuração padrão:**
- Modelo: `ollama/gemma3:4b`
- Base URL: `http://localhost:11434`
- Temperatura: `0.5`

---

### `transcription/__init__.py`

Atualizado para exportar as novas funções do CrewAI:

```python
from transcription.crew_transcriber import (
    create_test_case_agent,
    transcribe_single,
    transcribe_folder,
    MultimodalInput,
)
```

---

### `transcription/transcriber.py`

Correções no módulo original (LangChain):

- **Fix:** Caminhos dos arquivos few-shot corrigidos para usar arquivos existentes
- **Fix:** Adicionado encoding UTF-8 nas operações de arquivo
- **Refactor:** Função `build_few_shot_messages()` agora usa lista de pares configurável

**Arquivos few-shot utilizados:**
- Input: `scripts/TC_.ImportExportActivity_20210401-002546.txt`
- Output: `transcriptions/Output2TC_.ImportExportActivity_20210401-002546.txt`

---

### `requirements.txt`

Adicionada dependência:

```
crewai>=0.80.0
```

---

## Como Usar

### Execução via módulo Python

```bash
python -m transcription.crew_transcriber
```

### Uso programático

```python
from transcription import transcribe_folder
from constants.paths import TEST_CASES_PATH, TRANSCRIPTIONS_PATH

transcribe_folder(
    input_folder=TEST_CASES_PATH,
    output_folder=TRANSCRIPTIONS_PATH,
    model_name="ollama/gemma3:4b",
)
```

### Transcrição individual

```python
from transcription import transcribe_single
from transcription.crew_transcriber import create_llm

llm = create_llm()
result = transcribe_single(
    input_text="clicked android.widget.Button bounds:[0,0][100,50]",
    llm=llm
)
print(result)
```

---

## Arquitetura

```
transcription/
├── __init__.py           # Exports do módulo
├── crew_transcriber.py   # Novo: CrewAI agent
├── transcriber.py        # Original: LangChain
└── similarity_filter.py  # Filtro de documentos similares
```

---

## Próximos Passos

- [ ] Implementar suporte multimodal completo (imagens)
- [ ] Adicionar mais exemplos few-shot
- [ ] Testar com diferentes modelos Ollama
- [ ] Integrar com pipeline principal do rlmobtest
