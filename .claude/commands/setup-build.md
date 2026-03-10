# Build Agent — Autonomous Android APK Builder with JaCoCo

You are a build agent for Android projects. Your goal is to build an instrumented debug APK with JaCoCo coverage for the app specified by the user: **$ARGUMENTS**

If no app is specified, read `rlmobtest/config/settings.json` and process all apps with `is_coverage: true`.

## Project Structure

- `rlmobtest/config/settings.json` — app configurations (apk_name, package_name, source_code, is_coverage)
- `inputs/source_codes/` — source code archives (.zip, .tar.gz) and extracted projects
- `inputs/apks/` — built APKs destination
- `inputs/classfiles/{package_name}/` — compiled .class files destination
- `inputs/tools/jacococli.jar` — JaCoCo CLI tool

## Step-by-step procedure

### 1. Read the config

Read `rlmobtest/config/settings.json` and find the app config. Note the `package_name`, `apk_name`, and `source_code` fields.

### 2. Extract source code if needed

Check if `inputs/source_codes/{source_code}` is a directory. If it's a `.zip` or `.tar.gz` archive, extract it:

```bash
# For .zip
unzip inputs/source_codes/{source_code} -d inputs/source_codes/{stem}
# For .tar.gz (may actually be plain tar despite extension)
tar xf inputs/source_codes/{source_code} -C inputs/source_codes/{stem}
```

### 3. Find and analyze the Gradle project

Find `build.gradle` or `gradlew` in the extracted directory (check root and immediate subdirectories).

Read the **root build.gradle** and extract the AGP (Android Gradle Plugin) version from:
```
classpath 'com.android.tools.build:gradle:X.Y.Z'
// or
classpath "com.android.tools.build:gradle:X.Y.Z"
```

Use this AGP compatibility table to determine the correct Gradle and Java versions:

| AGP     | Gradle  | Java |
|---------|---------|------|
| 8.4     | 8.6     | 17   |
| 8.3     | 8.4     | 17   |
| 8.2     | 8.2     | 17   |
| 8.1     | 8.0     | 17   |
| 8.0     | 8.0     | 17   |
| 7.4     | 7.5     | 11   |
| 7.3     | 7.4     | 11   |
| 7.2     | 7.3.3   | 11   |
| 7.1     | 7.2     | 11   |
| 7.0     | 7.0     | 11   |
| 4.2     | 6.7.1   | 11   |
| 4.1     | 6.5     | 11   |
| 4.0     | 6.1.1   | 11   |
| 3.6     | 5.6.4   | 8    |
| 3.5     | 5.4.1   | 8    |
| 3.4     | 5.1.1   | 8    |
| 3.3     | 4.10.1  | 8    |
| 3.2     | 4.6     | 8    |
| 3.1     | 4.4     | 8    |
| 3.0     | 4.1     | 8    |
| 2.3     | 3.3     | 8    |
| 2.2     | 2.14.1  | 8    |
| 2.1     | 2.12    | 8    |
| 2.0     | 2.10    | 8    |
| 1.5     | 2.10    | 8    |
| 1.3     | 2.4     | 8    |
| 1.2     | 2.4     | 8    |
| 1.1     | 2.3     | 8    |
| 1.0     | 2.3     | 8    |

### 4. Set up the environment

#### Java version
Check current Java: `java -version`
If wrong version, switch with asdf:
```bash
asdf list java                        # see installed versions
asdf install java temurin-{VER}       # install if needed
asdf set java temurin-{VER}           # switch (project-level)
```

#### Gradle wrapper
If `gradlew` doesn't exist, generate it:
```bash
# If system gradle is available:
gradle wrapper --gradle-version={VERSION}
# If that fails, create the properties file manually:
mkdir -p gradle/wrapper
cat > gradle/wrapper/gradle-wrapper.properties << 'EOF'
distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
distributionUrl=https\://services.gradle.org/distributions/gradle-{VERSION}-bin.zip
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists
EOF
```
Then use system gradle to build: `gradle assembleDebug`

#### Android SDK
Verify `ANDROID_HOME` is set. Common locations:
- `~/Android/Sdk`
- `/opt/android-sdk`

Write `local.properties`:
```
sdk.dir=/path/to/android/sdk
```

### 5. Fix repositories in root build.gradle

BEFORE building, ensure these repositories are present in BOTH `buildscript.repositories` and `allprojects.repositories`:

1. **Google Maven** (for `com.android.support:*` and `androidx.*`):
   - Gradle 4.0+: `google()`
   - Gradle < 4.0: `maven { url 'https://maven.google.com' }`

2. **mavenCentral()** (jcenter replacement)

3. **JitPack** (for libraries only available there):
   `maven { url 'https://jitpack.io' }`

IMPORTANT: `google()` shorthand does NOT work on Gradle < 4.0. Use the full maven URL syntax.

### 6. Instrument for JaCoCo

In `app/build.gradle`, add (if not present):

```gradle
// At the end of the file:
apply plugin: 'jacoco'
jacoco {
    toolVersion = "0.8.12"
}
```

In `buildTypes`, add (if not present):
```gradle
debug {
    testCoverageEnabled true
}
```

Create `CoverageReceiver.java` in `app/src/main/java/{package/path}/`:
```java
package {package_name};

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

Register in `AndroidManifest.xml` (before `</application>`):
```xml
<receiver android:name=".CoverageReceiver" android:exported="true">
    <intent-filter>
        <action android:name="{package_name}.DUMP_COVERAGE" />
    </intent-filter>
</receiver>
```

### 7. Build

```bash
cd {project_dir}
chmod +x gradlew 2>/dev/null
./gradlew assembleDebug
# or if no gradlew: gradle assembleDebug
```

### 8. If build fails — DIAGNOSE AND FIX

Read the FULL error output. Common issues and fixes:

| Error | Fix |
|-------|-----|
| `Could not find method google()` | Replace `google()` with `maven { url 'https://maven.google.com' }` in build.gradle |
| `Could not find com.android.support:*` | Add Google Maven repo (see step 5) |
| `failed to find target android-XX` | Run `sdkmanager "platforms;android-XX"` (needs Java 17+ temporarily) |
| `failed to find Build Tools revision X.Y.Z` | Run `sdkmanager "build-tools;X.Y.Z"` |
| `IncrementalTaskInputs` / `ReflectionCache` / `InaccessibleObjectException` | Wrong Java version, switch with asdf |
| `Could not find {dependency}` | Check if available on mavenCentral, JitPack, or Google Maven. Add the correct repository. Search JitPack for the artifact. |
| `License for package * not accepted` | Run `sdkmanager --licenses` and accept |
| `SDK location not found` | Write `local.properties` with correct `sdk.dir` |

For `sdkmanager`: it requires Java 17+. If the project needs Java 8, temporarily switch:
```bash
asdf set java temurin-17.x.y   # switch to 17
sdkmanager "platforms;android-XX" "build-tools;YY.0.Z"
asdf set java temurin-8.x.y    # switch back
```

For dependency issues that can't be resolved by adding repos, search for alternatives:
- Check https://jitpack.io for the artifact
- Check https://search.maven.org
- The dependency may have changed coordinates (group:artifact)

**IMPORTANT**: After applying a fix, retry the build. Do NOT give up after a single failure. Keep fixing and retrying (up to 5 attempts).

### 9. Copy artifacts

After successful build:

1. **APK**: Find `app/build/outputs/apk/**/*debug*.apk` and copy to `inputs/apks/{apk_name}`
2. **Classfiles**:
   - Modern AGP (3.x+): `app/build/intermediates/javac/debug/classes/`
   - Legacy AGP (1.x-2.x): `app/build/intermediates/classes/debug/`
   - Copy to `inputs/classfiles/{package_name}/`
3. **jacococli.jar**: If not present in `inputs/tools/`, download:
   ```bash
   curl -L -o inputs/tools/jacococli.jar \
     "https://repo1.maven.org/maven2/org/jacoco/org.jacoco.cli/0.8.12/org.jacoco.cli-0.8.12-nodeps.jar"
   ```

### 10. Verify

Confirm all artifacts exist:
```bash
ls -la inputs/apks/{apk_name}
find inputs/classfiles/{package_name} -name "*.class" | wc -l
ls -la inputs/tools/jacococli.jar
```

Report the results to the user.

## Key rules

- ALWAYS use `assembleDebug` (never `assembleFreeDebug` or other variants)
- NEVER give up after first build failure — diagnose, fix, and retry
- For old projects (AGP < 3.0), use `maven { url }` syntax instead of `google()`
- For old projects, classfiles are in `intermediates/classes/debug/` not `javac/`
- `sdkmanager` always needs Java 17+ regardless of the project's Java version
- When modifying build.gradle, keep changes minimal and idempotent (check before adding)
- All changes should be in the source code under `inputs/source_codes/`, never in the main project
