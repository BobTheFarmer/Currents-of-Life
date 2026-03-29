using UnityEngine;
using UnityEditor;
using System.IO;

/// <summary>
/// Saves a screenshot of the Game view to the project root.
/// Works in Play mode. Press the menu item while the game is running.
/// </summary>
public static class ScreenshotTool
{
    static readonly string OutPath =
        Path.GetFullPath(Path.Combine(Application.dataPath, "..", "screenshot.png"));

    [MenuItem("Build4Good/Take Screenshot (Play mode)")]
    public static void TakeScreenshot()
    {
        if (!Application.isPlaying)
        {
            Debug.LogWarning("[ScreenshotTool] Enter Play mode first, then use this menu item.");
            EditorUtility.DisplayDialog("Screenshot",
                "Enter Play mode first, then use Build4Good → Take Screenshot.", "OK");
            return;
        }

        ScreenCapture.CaptureScreenshot(OutPath, 1);
        Debug.Log($"[ScreenshotTool] Screenshot queued → {OutPath}");
    }

    // ── Auto-screenshot every N seconds during Play mode ─────────────────────
    // Set AUTO_INTERVAL = 0 to disable.
    const float AUTO_INTERVAL = 3f;

    static double _nextShot;

    [InitializeOnLoadMethod]
    static void Init()
    {
        EditorApplication.update += AutoShot;
    }

    static void AutoShot()
    {
        if (AUTO_INTERVAL <= 0f || !Application.isPlaying) return;
        if (EditorApplication.timeSinceStartup < _nextShot) return;
        _nextShot = EditorApplication.timeSinceStartup + AUTO_INTERVAL;

        string path = Path.GetFullPath(Path.Combine(
            Application.dataPath, "..", "screenshot.png"));
        ScreenCapture.CaptureScreenshot(path, 1);
    }
}
