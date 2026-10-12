using System;
using System.Linq;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEngine;

/// 명령줄 빌드. kit.config.json 의 deploy.channels.android.build 가 `-executeMethod KitBuild.AndroidAab` 로 부른다.
/// 실패하면 0 이 아닌 값으로 끝나서 deploy 도구가 멈춘다.
public static class KitBuild
{
    const string Output = "build/android/game.aab";

    /// Google Play 에 올릴 AAB. Play 는 64비트를 요구한다 — IL2CPP + ARM64.
    /// 서명은 환경 변수로 받는다 (KIT_KEYSTORE · KIT_KEYSTORE_PASS · KIT_KEY_ALIAS · KIT_KEY_PASS). 비밀번호는 저장소에 적지 않는다.
    public static void AndroidAab()
    {
        EditorUserBuildSettings.buildAppBundle = true;
        PlayerSettings.SetScriptingBackend(NamedBuildTarget.Android, ScriptingImplementation.IL2CPP);
        PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64;

        string keystore = Environment.GetEnvironmentVariable("KIT_KEYSTORE");
        if (!string.IsNullOrEmpty(keystore))
        {
            PlayerSettings.Android.useCustomKeystore = true;
            PlayerSettings.Android.keystoreName = keystore;
            PlayerSettings.Android.keystorePass = Environment.GetEnvironmentVariable("KIT_KEYSTORE_PASS");
            PlayerSettings.Android.keyaliasName = Environment.GetEnvironmentVariable("KIT_KEY_ALIAS");
            PlayerSettings.Android.keyaliasPass = Environment.GetEnvironmentVariable("KIT_KEY_PASS");
        }
        else
        {
            Debug.LogWarning("KitBuild: KIT_KEYSTORE 가 없다 — 디버그 키로 서명된다. Play 는 이 빌드를 받지 않는다.");
        }

        // Play 는 올릴 때마다 더 큰 versionCode 를 요구한다
        string code = Environment.GetEnvironmentVariable("KIT_VERSION_CODE");
        if (!string.IsNullOrEmpty(code))
            PlayerSettings.Android.bundleVersionCode = int.Parse(code);

        string[] scenes = EditorBuildSettings.scenes.Where(s => s.enabled).Select(s => s.path).ToArray();
        if (scenes.Length == 0)
        {
            Debug.LogError("KitBuild: Build Settings 에 켜진 씬이 없다.");
            EditorApplication.Exit(1);
            return;
        }

        BuildReport report = BuildPipeline.BuildPlayer(scenes, Output, BuildTarget.Android, BuildOptions.None);
        if (report.summary.result != BuildResult.Succeeded)
            EditorApplication.Exit(1);
    }
}
