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
APK instrumentado → treinamento (is_coverage=true) → broadcast dump → coleta .ec → report:
  1. Busca jacococli.jar em inputs/tools/
  2. Busca classfiles em inputs/classfiles/{package_name}/
  3. Merge dos .ec files coletados
  4. jacococli report → CSV + HTML → percentuais no report.html
```

### Fluxo de coleta em tempo de execucao

```
Agente executa acao
  → adb shell am broadcast -n {pkg}/.CoverageReceiver -a {pkg}.DUMP_COVERAGE
  → CoverageReceiver chama JaCoCo RT.getAgent().getExecutionData()
  → Escreve em context.getFilesDir()/coverage.ec
  → adb exec-out run-as {pkg} cat files/coverage.ec > coverage.ec
  → Copia com timestamp para output/.../coverage/coverage_{timestamp}.ec
```

---

## Setup automatizado (recomendado)

Desde a v0.1.8, o RLMobTest automatiza todo o setup do JaCoCo.

### Prerequisitos no sistema

```bash
# JDK
sudo apt install default-jdk  # Ubuntu/Debian
java -version

# Android SDK
export ANDROID_HOME="$HOME/android-sdk"
mkdir -p "$ANDROID_HOME"
# Baixar command-line tools: https://developer.android.com/studio#command-tools
sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0"
```

### Configurar settings.json

```json
[
  {
    "apk_name": "moneytracker.apk",
    "package_name": "com.blogspot.e_kanivets.moneytracker",
    "source_code": "open_money_tracker-dev",
    "is_coverage": true,
    "time": 300
  }
]
```

O campo `source_code` deve apontar para um diretorio ou `.zip` em `inputs/source_codes/`.

### Executar setup

```bash
# Setup isolado (build APK, copiar classfiles, baixar jacococli)
rlmobtest setup

# Setup de app especifico
rlmobtest setup --app com.blogspot.e_kanivets.moneytracker

# Forcar rebuild
rlmobtest setup --force
```

O setup:
1. Resolve o source code (extrai ZIP se necessario)
2. Roda `./gradlew assembleFreeDebug` (fallback: `assembleDebug`)
3. Copia APK para `inputs/apks/{apk_name}`
4. Copia classfiles para `inputs/classfiles/{package_name}/`
5. Baixa `jacococli.jar` para `inputs/tools/`

### Pipeline completo

```bash
# O pipeline roda o setup automaticamente como Step 0
rlmobtest pipeline --app com.blogspot.e_kanivets.moneytracker
```

O Step 0 e executado quando `is_coverage: true` e `source_code` esta configurado.

---

## Setup manual (alternativa)

Se preferir configurar manualmente ou se o setup automatizado falhar:

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

### 2. Preparar o source code do app

#### 2.1 Habilitar JaCoCo no build.gradle

Editar o `app/build.gradle`:

```gradle
apply plugin: 'jacoco'

android {
    buildTypes {
        debug {
            testCoverageEnabled true
        }
    }

    testOptions {
        animationsDisabled true
        unitTests.all {
            jacoco {
                includeNoLocationClasses = true
            }
        }
        unitTests.returnDefaultValues = true
    }
}

jacoco {
    toolVersion = "0.8.12"
}
```

#### 2.2 Adicionar CoverageReceiver

Criar `app/src/main/java/{package}/CoverageReceiver.java`:

```java
package com.example.myapp;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;
import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStream;

public class CoverageReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        try {
            Class<?> rtClass = Class.forName("org.jacoco.agent.rt.RT");
            Object agent = rtClass.getMethod("getAgent").invoke(null);
            byte[] data = (byte[]) agent.getClass()
                    .getMethod("getExecutionData", boolean.class)
                    .invoke(agent, false);
            File coverageFile = new File(context.getFilesDir(), "coverage.ec");
            OutputStream out = new FileOutputStream(coverageFile);
            out.write(data);
            out.close();
            Log.i("CoverageReceiver", "Coverage dumped (" + data.length + " bytes)");
        } catch (Exception e) {
            Log.e("CoverageReceiver", "Failed to dump coverage", e);
        }
    }
}
```

Registrar no `AndroidManifest.xml`:

```xml
<receiver android:name=".CoverageReceiver" android:exported="true">
    <intent-filter>
        <action android:name="com.example.myapp.DUMP_COVERAGE" />
    </intent-filter>
</receiver>
```

#### 2.3 Google Services (Firebase)

Se o app usa Firebase, e necessario um `google-services.json` valido (ou dummy) em `app/`.
Um arquivo dummy esta disponivel em `docs/build_gradle/money_tracker/google-services.json`.

#### 2.4 Compilar

```bash
export ANDROID_HOME="$HOME/android-sdk"

cd inputs/source_codes/nome-do-projeto/
./gradlew assembleFreeDebug  # ou assembleDebug
```

O APK instrumentado estara em:
```
app/build/outputs/apk/free/debug/app-free-debug.apk
```

Os classfiles compilados estarao em:
```
app/build/intermediates/javac/freeDebug/classes/
```

#### 2.5 Copiar para o RLMobTest

```bash
PACKAGE="com.example.myapp"
RLMOBTEST="/caminho/para/rlmobtest-icomp"

# Copiar APK
cp app/build/outputs/apk/free/debug/app-free-debug.apk "$RLMOBTEST/inputs/apks/"

# Copiar classfiles
mkdir -p "$RLMOBTEST/inputs/classfiles/$PACKAGE"
cp -r app/build/intermediates/javac/freeDebug/classes/* \
  "$RLMOBTEST/inputs/classfiles/$PACKAGE/"
```

---

### 3. Obter o jacococli.jar

```bash
mkdir -p inputs/tools

# Download direto (versao 0.8.12)
wget -O inputs/tools/jacococli.jar \
  "https://repo1.maven.org/maven2/org/jacoco/org.jacoco.cli/0.8.12/org.jacoco.cli-0.8.12-nodeps.jar"
```

---

### 4. Atualizar settings.json

```json
{
  "apk_name": "app-free-debug.apk",
  "package_name": "com.example.myapp",
  "source_code": "nome-do-projeto",
  "is_coverage": true,
  "time": 3600
}
```

---

### 5. Executar

```bash
# Pipeline completo (inclui setup automatico)
rlmobtest pipeline --app com.example.myapp

# Ou separadamente:
rlmobtest train --app com.example.myapp
rlmobtest report --app com.example.myapp
```

---

## Relatorios gerados

### report.html (metricas agregadas)

Gerado em `output/{pkg}/{mode}/{YYYY}/{MM}/{DD}/report.html`.
Inclui progress bars com Line, Branch e Method coverage.

### JaCoCo HTML (detalhado)

Gerado em `output/{pkg}/{mode}/{YYYY}/{MM}/{DD}/coverage/jacoco_html/index.html`.
Navegavel por pacote, classe e metodo. Se o `source_code` estiver configurado,
inclui anotacao linha-a-linha do codigo-fonte.

Link para o relatorio detalhado aparece automaticamente no `report.html`.

---

## Estrutura de diretorios

```
inputs/
├── apks/
│   └── moneytracker.apk                   # APK instrumentado
├── classfiles/
│   └── com.blogspot.e_kanivets.moneytracker/
│       └── com/blogspot/.../*.class        # Classes compiladas
├── source_codes/
│   └── open_money_tracker-dev/             # Source code do app
│       ├── app/build.gradle
│       ├── app/src/main/java/...
│       └── gradlew
└── tools/
    └── jacococli.jar                       # JaCoCo CLI

output/
└── com.blogspot.e_kanivets.moneytracker/original/2026/03/03/
    ├── report.html                         # Relatorio principal
    └── coverage/
        ├── coverage_20260303-143052.ec     # Coletado durante treino
        ├── coverage_20260303-143105.ec     # Coletado durante treino
        ├── merged.ec                       # Gerado automaticamente
        ├── coverage_report.csv             # Gerado automaticamente
        └── jacoco_html/                    # Relatorio detalhado
            └── index.html
```

---

## Prerequisitos resumidos

| Item | Obrigatorio | Onde | Automatizado |
|------|------------|------|:---:|
| JDK | Sim | PATH do sistema | Nao |
| Android SDK | Sim (para build) | `$ANDROID_HOME` | Nao |
| APK instrumentado | Sim | `inputs/apks/` | Sim (`rlmobtest setup`) |
| `is_coverage: true` | Sim | `settings.json` | Manual |
| `jacococli.jar` | Sim | `inputs/tools/` | Sim (`rlmobtest setup`) |
| Classfiles | Sim | `inputs/classfiles/{pkg}/` | Sim (`rlmobtest setup`) |
| CoverageReceiver | Sim | No source code do app | Manual (uma vez) |

---

## Troubleshooting

| Problema | Causa | Solucao |
|----------|-------|---------|
| JaCoCo mostra N/A | jacococli.jar nao encontrado | `rlmobtest setup` ou baixe manualmente |
| JaCoCo mostra N/A | Sem classfiles | `rlmobtest setup` ou copie manualmente |
| JaCoCo mostra N/A | Sem arquivos .ec | Verifique se `is_coverage: true` e o APK e instrumentado |
| Erro no merge | Java nao instalado | Instale o JDK |
| Cobertura 0% | APK nao instrumentado | Recompile com `testCoverageEnabled true` |
| `/sdcard/coverage.ec: No such file` | App sem CoverageReceiver | Adicione o BroadcastReceiver ao app |
| `Tcl_AsyncDelete` crash | matplotlib backend TkAgg | Ja corrigido na v0.1.8 (usa Agg) |
| Build falha no setup | `ANDROID_HOME` nao definido | `export ANDROID_HOME=$HOME/android-sdk` |
| Build falha | Sem `google-services.json` | Copie o dummy de `docs/build_gradle/` |
| Metricas imprecisas | Classfiles do dex2jar | Use classfiles do build original |
