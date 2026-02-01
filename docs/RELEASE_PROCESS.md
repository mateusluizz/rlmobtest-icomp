# Processo de Release

Guia para criar novas versoes do rlmobtest.

---

## Versionamento Semantico

Usamos **SemVer**: `MAJOR.MINOR.PATCH`

| Tipo | Quando incrementar | Exemplo |
|------|-------------------|---------|
| **MAJOR** | Mudancas incompativeis (breaking changes) | 1.0.0 → 2.0.0 |
| **MINOR** | Nova funcionalidade (retrocompativel) | 0.1.0 → 0.2.0 |
| **PATCH** | Correcao de bugs | 0.1.0 → 0.1.1 |

---

## Checklist de Release

### 1. Preparacao

```bash
# Verificar que esta na branch main
git checkout main
git pull origin main

# Verificar que todos os testes passam (se houver)
python -m pytest

# Verificar que nao ha mudancas pendentes
git status
```

### 2. Atualizar Versao

**Arquivo:** `pyproject.toml`

```toml
[project]
version = "0.2.0"  # Atualizar aqui
```

### 3. Atualizar CHANGELOG.md

Mover itens de `[Unreleased]` para a nova versao:

```markdown
## [Unreleased]

(vazio ou proximas mudancas)

## [0.2.0] - 2026-02-15

### Added
- (mover itens de Unreleased para ca)

### Changed
- ...

### Fixed
- ...
```

### 4. Commit da Release

```bash
git add pyproject.toml CHANGELOG.md
git commit -m "release: v0.2.0"
```

### 5. Criar Tag

```bash
# Criar tag anotada
git tag -a v0.2.0 -m "Release v0.2.0

Principais mudancas:
- Nova feature X
- Correcao do bug Y
- Melhoria em Z"

# Verificar tag criada
git tag -l
git show v0.2.0
```

### 6. Push

```bash
# Push do commit
git push origin main

# Push da tag
git push origin v0.2.0

# Ou push de todas as tags
git push origin --tags
```

---

## Criar Release no GitHub

### Via CLI (gh)

```bash
gh release create v0.2.0 \
  --title "v0.2.0" \
  --notes-file RELEASE_NOTES.md
```

### Via Web

1. Ir para: `https://github.com/seu-usuario/rlmobtest-icomp/releases`
2. Clicar em "Draft a new release"
3. Escolher a tag `v0.2.0`
4. Titulo: `v0.2.0`
5. Descricao: Copiar da secao do CHANGELOG.md
6. Publicar

---

## Comandos Uteis

### Listar todas as tags

```bash
git tag -l
```

### Ver detalhes de uma tag

```bash
git show v0.1.0
```

### Deletar tag local

```bash
git tag -d v0.1.0
```

### Deletar tag remota

```bash
git push origin --delete v0.1.0
```

### Ver commits desde ultima tag

```bash
git log $(git describe --tags --abbrev=0)..HEAD --oneline
```

### Gerar notas de release automaticamente

```bash
# Ver mudancas desde a ultima tag
git log --oneline v0.1.1..HEAD

# Formato mais detalhado
git log --pretty=format:"- %s (%h)" v0.1.1..HEAD
```

---

## Estrutura do CHANGELOG

Cada release deve ter secoes conforme aplicavel:

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- Novas funcionalidades

### Changed
- Mudancas em funcionalidades existentes

### Deprecated
- Funcionalidades que serao removidas em versoes futuras

### Removed
- Funcionalidades removidas

### Fixed
- Correcoes de bugs

### Security
- Correcoes de vulnerabilidades
```

---

## Exemplo Completo

```bash
# 1. Preparar
git checkout main && git pull

# 2. Editar pyproject.toml (version = "0.2.0")
# 3. Editar CHANGELOG.md

# 4. Commit
git add pyproject.toml CHANGELOG.md
git commit -m "release: v0.2.0"

# 5. Tag
git tag -a v0.2.0 -m "Release v0.2.0 - Separacao de outputs por agente"

# 6. Push
git push origin main --tags

# 7. (Opcional) Criar release no GitHub
gh release create v0.2.0 --generate-notes
```

---

## Criar Primeira Tag (Projeto Existente)

Se o projeto ja tem commits mas nenhuma tag:

```bash
# Criar tag para versao atual
git tag -a v0.1.2 -m "Release v0.1.2 - Versao atual do projeto"
git push origin v0.1.2
```

---

## Automacao Futura

Considerar adicionar:

1. **GitHub Actions** para CI/CD
2. **semantic-release** para releases automaticas
3. **commitlint** para padronizar mensagens de commit
4. **bump2version** para atualizar versao automaticamente
