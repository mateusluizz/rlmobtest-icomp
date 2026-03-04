# Configuracao do JaCoCo — RLMobTest

## O que e o JaCoCo?

JaCoCo (Java Code Coverage) mede **quanta parte do codigo-fonte do app Android foi executada** durante os testes do agente RL. Ele fornece 3 metricas principais:

| Metrica | O que mede |
|---------|-----------|
| **Line Coverage** | % de linhas de codigo executadas |
| **Branch Coverage** | % de caminhos de decisao (if/else, switch) percorridos |
| **Method Coverage** | % de metodos/funcoes chamados |

Essas metricas aparecem no relatorio HTML gerado por `rlmobtest report`.

---

## Como funciona no RLMobTest

```
APK instrumentado → treinamento (is_coverage=true) → coleta .ec → report:
  1. Busca jacococli.jar em inputs/tools/
  2. Busca classfiles em inputs/classfiles/{package_name}/
  3. Merge dos .ec files coletados
  4. jacococli report → CSV → parse → percentuais no HTML
```

---

## Passo a passo

### 1. Instalar prerequisitos (JDK + Android SDK via CLI)

#### 1.1 Instalar o JDK

```bash
# Ubuntu/Debian
sudo apt install default-jdk

# Arch Linux
sudo pacman -S jdk-openjdk

# Verificar
java -version
javac -version
```

#### 1.2 Instalar o Android SDK (sem Android Studio)

```bash
# Criar diretorio do SDK
export ANDROID_HOME="$HOME/android-sdk"
mkdir -p "$ANDROID_HOME"

# Baixar command-line tools (verificar versao mais recente em:
# https://developer.android.com/studio#command-tools)
cd /tmp
wget https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip
unzip commandlinetools-linux-*.zip
mkdir -p "$ANDROID_HOME/cmdline-tools"
mv cmdline-tools "$ANDROID_HOME/cmdline-tools/latest"

# Adicionar ao PATH (colocar no ~/.bashrc ou ~/.zshrc)
export PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH"

# Aceitar licencas
yes | sdkmanager --licenses

# Instalar componentes necessarios
sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0"
```

---

### 2. Compilar o APK com JaCoCo

Ha duas formas de compilar: via Android Studio (mais simples) ou via CLI.

#### Opcao A — Via Android Studio

1. Abrir o projeto no Android Studio (`File > Open`)
2. Editar `app/build.gradle` para habilitar JaCoCo (ver secao 2.2 abaixo)
3. Clicar em `Build > Build Bundle(s) / APK(s) > Build APK(s)`
4. O APK estara em `app/build/outputs/apk/debug/app-debug.apk`
5. Os classfiles estarao em `app/build/intermediates/javac/debug/classes/`

#### Opcao B — Via CLI (sem Android Studio)

```bash
# Descompactar o source code
cd /tmp
unzip /caminho/para/source-code.zip
cd nome-do-projeto/
```

Depois seguir os passos 2.2 e 2.3 abaixo.

#### 2.2 Habilitar JaCoCo no build.gradle

Editar o `app/build.gradle` (ou `app/build.gradle.kts`):

**Groovy (`build.gradle`):**
```gradle
android {
    buildTypes {
        debug {
            testCoverageEnabled true
        }
    }
}
```

**Kotlin DSL (`build.gradle.kts`):**
```kotlin
android {
    buildTypes {
        getByName("debug") {
            enableAndroidTestCoverage = true
            enableUnitTestCoverage = true
        }
    }
}
```

#### 2.3 Compilar

```bash
# Garantir que ANDROID_HOME esta definido
export ANDROID_HOME="$HOME/android-sdk"

# Compilar APK debug com instrumentacao JaCoCo
./gradlew assembleDebug
```

O APK instrumentado estara em:
```
app/build/outputs/apk/debug/app-debug.apk
```

Os classfiles compilados estarao em:
```
app/build/intermediates/javac/debug/classes/
```

#### 2.4 Copiar para o RLMobTest

```bash
# Exemplo para o app com.example.myapp
PACKAGE="com.example.myapp"
RLMOBTEST="/caminho/para/rlmobtest-icomp"

# Copiar APK
cp app/build/outputs/apk/debug/app-debug.apk "$RLMOBTEST/inputs/apks/"

# Copiar classfiles
mkdir -p "$RLMOBTEST/inputs/classfiles/$PACKAGE"
cp -r app/build/intermediates/javac/debug/classes/* \
  "$RLMOBTEST/inputs/classfiles/$PACKAGE/"
```

#### 2.5 Atualizar settings.json

```json
{
  "apk_name": "app-debug.apk",
  "package_name": "com.example.myapp",
  "is_coverage": true,
  "time": 3600
}
```

---

### 3. Obter o jacococli.jar

Baixe o JaCoCo CLI do Maven Central:

```bash
mkdir -p inputs/tools

# Download direto (versao 0.8.12 recomendada)
wget -O inputs/tools/jacococli.jar \
  "https://repo1.maven.org/maven2/org/jacoco/org.jacoco.cli/0.8.12/org.jacoco.cli-0.8.12-nodeps.jar"
```

Ou acesse manualmente:
- https://repo1.maven.org/maven2/org/jacoco/org.jacoco.cli/
- Baixe o arquivo `org.jacoco.cli-X.X.X-nodeps.jar` (versao `-nodeps` inclui todas as dependencias)
- Renomeie para `jacococli.jar` e coloque em `inputs/tools/`

---

### 4. Classfiles — opcoes alternativas

Se voce nao quer compilar do source code, ha alternativas para obter os classfiles:

**Opcao B — Do JAR pre-compilado:**

```bash
mkdir -p inputs/classfiles/com.example.myapp
cp app/build/libs/app.jar inputs/classfiles/com.example.myapp/
```

**Opcao C — Extrair do APK (dex2jar):**

```bash
# Baixar dex2jar: https://github.com/pxb1988/dex2jar/releases
./d2j-dex2jar.sh app-debug.apk -o classes.jar

mkdir -p inputs/classfiles/com.example.myapp
mv classes.jar inputs/classfiles/com.example.myapp/
```

> **Nota:** Classfiles extraidos via dex2jar podem gerar metricas com pequenas imprecisoes. Prefira classfiles do build original quando possivel.

---

### 5. Executar

Com tudo configurado, o pipeline processa automaticamente:

```bash
# Treinar com coverage habilitado
rlmobtest train --app com.example.myapp

# Gerar relatorio (processa .ec automaticamente)
rlmobtest report --app com.example.myapp
```

---

## Estrutura de diretorios

```
inputs/
├── apks/
│   └── app-debug.apk                    # APK instrumentado
├── classfiles/
│   └── com.example.myapp/               # Classfiles do app
│       ├── com/example/myapp/*.class     # (Opcao A: classes soltas)
│       └── classes.jar                   # (Opcao B/C: JAR)
└── tools/
    └── jacococli.jar                     # JaCoCo CLI

output/
└── com.example.myapp/improved/2026/03/02/
    └── coverage/
        ├── coverage_20260302-143052.ec   # Coletado durante treino
        ├── coverage_20260302-143105.ec   # Coletado durante treino
        ├── merged.ec                     # Gerado automaticamente
        └── coverage_report.csv           # Gerado automaticamente
```

---

## Prerequisitos resumidos

| Item | Obrigatorio | Onde |
|------|------------|------|
| APK instrumentado | Sim | `inputs/apks/` |
| `is_coverage: true` | Sim | `settings.json` |
| Java Runtime | Sim | PATH do sistema |
| `jacococli.jar` | Sim | `inputs/tools/` |
| Classfiles | Sim | `inputs/classfiles/{package_name}/` |

---

## Troubleshooting

| Problema | Causa | Solucao |
|----------|-------|---------|
| JaCoCo mostra N/A | jacococli.jar nao encontrado | Baixe e coloque em `inputs/tools/` |
| JaCoCo mostra N/A | Sem classfiles | Copie para `inputs/classfiles/{pkg}/` |
| JaCoCo mostra N/A | Sem arquivos .ec | Verifique se `is_coverage: true` e o APK e instrumentado |
| Erro no merge | Java nao instalado | Instale o JDK |
| Cobertura 0% | APK nao instrumentado | Recompile com `testCoverageEnabled true` |
| Metricas imprecisas | Classfiles do dex2jar | Use classfiles do build original (Opcao A) |
