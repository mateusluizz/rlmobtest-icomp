# RLMobTest — RL-based Android Testing with JaCoCo Coverage

## Project Overview

CLI tool (`rlmobtest`) for automated Android app testing using reinforcement learning (DQN).
Includes JaCoCo code coverage instrumentation, build automation, and test case transcription.

## Key Commands

```bash
rlmobtest setup          # Build APKs + copy classfiles + download jacococli (uses build agent)
rlmobtest setup --no-agent  # Setup without autonomous build agent
rlmobtest check          # Pre-validate Java/Gradle/SDK prerequisites
rlmobtest pipeline       # Full pipeline: exploration → requirements → guided → transcription
rlmobtest train          # Train DQN agent on a single app
```

## Project Structure

```
rlmobtest/
  cli/             # Typer CLI commands (setup, check, pipeline, train, etc.)
  config/          # settings.json — app configurations
  constants/       # paths.py (APKS_DIR, CLASSFILES_DIR, etc.), actions.py
  training/        # DQN training, agents, report generation
  transcription/   # CrewAI-based test case transcription
  utils/
    build_agent.py    # Rule-based autonomous build agent (fallback)
    jacoco_setup.py   # JaCoCo instrumentation, APK building, classfiles copying
    jacoco.py         # Coverage processing (merge .ec, generate CSV/HTML)
    config_reader.py  # Settings parser (Pydantic models)
    app_context.py    # App context extraction for LLM
inputs/
  apks/            # Built APKs
  classfiles/      # Compiled .class files per package
  source_codes/    # Source code archives and extracted projects
  tools/           # jacococli.jar
```

## Build Agent (slash command)

Use `/setup-build <package_name>` to run the Claude Code build agent.
It autonomously builds any Android project (old AGP 1.x to new AGP 8.x) with JaCoCo.

## Important Conventions

- APK build uses only `assembleDebug` (no other variants)
- AGP version determines Gradle + Java compatibility (see table in build_agent.py)
- `google()` requires Gradle 4.0+; use `maven { url 'https://maven.google.com' }` for older
- `sdkmanager` always requires Java 17+, independent of project Java version
- Old AGP (1.x-2.x): classfiles at `intermediates/classes/debug/`
- Modern AGP (3.x+): classfiles at `intermediates/javac/debug/classes/`
- Version management: asdf (Java, Gradle)
- Settings: `rlmobtest/config/settings.json` (array of app configs)
