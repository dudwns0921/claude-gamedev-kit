using System;
using System.Linq;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEngine;

/// Command-line build. deploy.channels.android.build in kit.config.json calls it with `-executeMethod KitBuild.AndroidAab`.
/// On failure it exits non-zero, which stops the deploy tool.
public static class KitBuild
{
    const string Output = "build/android/game.aab";

    /// The AAB for Google Play. Play requires 64-bit — IL2CPP + ARM64.
    /// Signing comes from environment variables (KIT_KEYSTORE · KIT_KEYSTORE_PASS · KIT_KEY_ALIAS · KIT_KEY_PASS). Passwords are not written in the repository.
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
            Debug.LogWarning("KitBuild: KIT_KEYSTORE is not set — the build is signed with the debug key. Play does not accept it.");
        }

        // Play requires a larger versionCode on every upload
        string code = Environment.GetEnvironmentVariable("KIT_VERSION_CODE");
        if (!string.IsNullOrEmpty(code))
            PlayerSettings.Android.bundleVersionCode = int.Parse(code);

        string[] scenes = EditorBuildSettings.scenes.Where(s => s.enabled).Select(s => s.path).ToArray();
        if (scenes.Length == 0)
        {
            Debug.LogError("KitBuild: no scene is enabled in Build Settings.");
            EditorApplication.Exit(1);
            return;
        }

        BuildReport report = BuildPipeline.BuildPlayer(scenes, Output, BuildTarget.Android, BuildOptions.None);
        if (report.summary.result != BuildResult.Succeeded)
            EditorApplication.Exit(1);
    }
}
