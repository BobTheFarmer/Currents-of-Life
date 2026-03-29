using UnityEngine;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine.Rendering.Universal;
using System.IO;

public static class SceneSetup
{
    static readonly string ProjectRoot = Path.GetDirectoryName(Application.dataPath);

    [MenuItem("Build4Good/Setup Ocean Scene")]
    public static void SetupScene()
    {
        if (UnityEditor.EditorApplication.isPlaying)
        {
            Debug.LogError("[Build4Good] Stop Play mode before running Setup Ocean Scene.");
            return;
        }

        // ── Clear scene ──────────────────────────────────────────────────────
        foreach (var go in Object.FindObjectsByType<GameObject>(FindObjectsSortMode.None))
            Object.DestroyImmediate(go);

        // ── Camera ───────────────────────────────────────────────────────────
        var camGO = new GameObject("Main Camera");
        camGO.tag = "MainCamera";
        var cam = camGO.AddComponent<Camera>();
        cam.orthographic      = true;
        cam.orthographicSize  = 6f;
        cam.backgroundColor   = new Color(0.08f, 0.25f, 0.45f);
        cam.clearFlags        = CameraClearFlags.SolidColor;
        cam.depth             = -1;
        camGO.AddComponent<AudioListener>();
        camGO.transform.position = new Vector3(0, 0, -10f);

        var follow = camGO.AddComponent<CameraFollow>();
        follow.smoothSpeed = 4f;

        // ── Ocean background ──────────────────────────────────────────────────
        // OceanBackground.Awake() is fully self-bootstrapping:
        // it creates its own MeshFilter, MeshRenderer, RenderTextures, and
        // loads NASA data from StreamingAssets at runtime.
        // Ocean is fixed in world space — boat and camera move through it.
        // 80x40 world units: ~44s to sail from center to east/west edge at default speed.
        var oceanGO = new GameObject("Ocean");
        oceanGO.AddComponent<OceanBackground>();
        oceanGO.transform.position   = new Vector3(0, 0, 2f);
        oceanGO.transform.localScale = new Vector3(80f, 40f, 1f);

        // ── Boat ─────────────────────────────────────────────────────────────
        var boatGO = new GameObject("Boat");
        boatGO.transform.position = Vector3.zero;

        var hullSR = boatGO.AddComponent<SpriteRenderer>();
        hullSR.sprite       = CreateBoatSprite();
        hullSR.sortingOrder = 2;

        var rb = boatGO.AddComponent<Rigidbody2D>();
        rb.gravityScale   = 0f;
        rb.freezeRotation = false;

        var controller = boatGO.AddComponent<BoatController>();
        boatGO.AddComponent<BoatInput>();
        controller.moveSpeed   = 1.5f;   // world units/s at ortho 3.5 — ~27s to reach edge
        controller.turnSpeed   = 55f;
        controller.turnInertia = 0.12f;

        // Wake particles
        var wakeGO = new GameObject("Wake");
        wakeGO.transform.SetParent(boatGO.transform);
        wakeGO.transform.localPosition = new Vector3(0f, -0.55f, 0f);
        wakeGO.AddComponent<ParticleSystem>();
        wakeGO.AddComponent<WaterWake>();          // WaterWake.Awake() configures the PS
        wakeGO.GetComponent<ParticleSystemRenderer>().sortingOrder = 1;
        controller.wakeParticles = wakeGO.GetComponent<ParticleSystem>();

        // Runtime logger
        var loggerGO = new GameObject("RuntimeLogger");
        loggerGO.AddComponent<RuntimeLogger>();

        // Camera target
        follow.target = boatGO.transform;

        // ── Mark dirty & log ─────────────────────────────────────────────────
        EditorSceneManager.MarkSceneDirty(
            UnityEngine.SceneManagement.SceneManager.GetActiveScene());
        Selection.activeGameObject = boatGO;

        string msg = $"[Build4Good] Scene setup complete at {System.DateTime.Now:HH:mm:ss}.\n" +
                     $"  Objects: Camera, Ocean, Boat, Wake, RuntimeLogger\n" +
                     $"  Hit Play to sail. Steer with A/D or Left/Right arrows.\n";
        Debug.Log(msg);
        File.AppendAllText(Path.Combine(ProjectRoot, "compile_status.txt"), "\n" + msg);
    }

    // ── Unit quad mesh (1x1, centered) ──────────────────────────────────────

    static Mesh CreateQuadMesh()
    {
        var mesh = new Mesh { name = "OceanQuad" };
        mesh.vertices  = new Vector3[] {
            new(-0.5f, -0.5f, 0f),
            new( 0.5f, -0.5f, 0f),
            new(-0.5f,  0.5f, 0f),
            new( 0.5f,  0.5f, 0f),
        };
        mesh.uv = new Vector2[] {
            new(0f, 0f), new(1f, 0f),
            new(0f, 1f), new(1f, 1f),
        };
        mesh.triangles = new int[] { 0, 2, 1, 2, 3, 1 };
        mesh.RecalculateNormals();
        return mesh;
    }

    // ── Ocean texture: 128x128 tileable water ────────────────────────────────

    static Texture2D CreateOceanTexture()
    {
        int w = 128, h = 128;
        var tex = new Texture2D(w, h, TextureFormat.RGBA32, false);
        tex.filterMode = FilterMode.Bilinear;
        tex.wrapMode   = TextureWrapMode.Repeat;

        Color deep  = new Color(0.05f, 0.18f, 0.35f);
        Color light = new Color(0.16f, 0.42f, 0.60f);
        Color foam  = new Color(0.80f, 0.93f, 1.00f);

        for (int y = 0; y < h; y++)
        for (int x = 0; x < w; x++)
        {
            float fx = x / (float)w;
            float fy = y / (float)h;

            // Three overlapping diagonal bands — no vertical stripes
            float w1 = Mathf.Sin((fx * 6.3f + fy * 3.1f) * Mathf.PI * 2f) * 0.5f + 0.5f;
            float w2 = Mathf.Sin((fx * 2.7f - fy * 5.3f) * Mathf.PI * 2f) * 0.5f + 0.5f;
            float w3 = Mathf.Sin((fx * 9.1f + fy * 1.7f) * Mathf.PI * 2f) * 0.5f + 0.5f;
            float wave = w1 * 0.5f + w2 * 0.3f + w3 * 0.2f;

            Color c = Color.Lerp(deep, light, wave * 0.65f);

            int hash = (x * 1619 + y * 31337) & 0xFFFF;
            if (wave > 0.82f && hash % 18 == 0)
                c = Color.Lerp(c, foam, 0.7f);

            tex.SetPixel(x, y, c);
        }

        tex.Apply();
        return tex;
    }

    // ── Boat sprite: 16x28 pixel art, top-down view ──────────────────────────

    static Sprite CreateBoatSprite()
    {
        int w = 16, h = 28;
        var tex = new Texture2D(w, h, TextureFormat.RGBA32, false);
        tex.filterMode = FilterMode.Point;
        tex.wrapMode   = TextureWrapMode.Clamp;

        Color clear  = Color.clear;
        Color hull   = new Color(0.85f, 0.80f, 0.65f);
        Color deck   = new Color(0.50f, 0.35f, 0.20f);
        Color cabin  = new Color(0.92f, 0.88f, 0.78f);
        Color dark   = new Color(0.18f, 0.14f, 0.10f);
        Color shadow = new Color(0.30f, 0.24f, 0.16f);

        for (int y = 0; y < h; y++)
            for (int x = 0; x < w; x++)
                tex.SetPixel(x, y, clear);

        // Hull shape: bow at top (y=27), stern at bottom (y=0)
        // Each row: (xLeft, xRight)
        (int, int)[] rows = {
            (7,8),(7,8),(6,9),(6,9),          // stern  0-3
            (5,10),(5,10),(5,10),(4,11),       // 4-7
            (4,11),(4,11),(4,11),(4,11),       // 8-11
            (4,11),(4,11),(4,11),(4,11),       // 12-15
            (5,10),(5,10),(5,10),(5,10),       // 16-19
            (5,10),(6,9),(6,9),(7,8),          // 20-23
            (7,8),(7,8),(7,7),(7,7),           // 24-27 bow
        };

        for (int y = 0; y < rows.Length; y++)
        {
            (int xl, int xr) = rows[y];
            for (int x = xl; x <= xr; x++)
            {
                bool isEdge   = (x == xl || x == xr);
                bool isCabin  = (y >= 10 && y <= 18 && x >= 5 && x <= 10);
                bool isDeck   = (y >= 4  && y <= 22);

                Color c;
                if      (isEdge)   c = dark;
                else if (isCabin)  c = (x == 5 || x == 10 || y == 10 || y == 18) ? shadow : cabin;
                else if (isDeck)   c = deck;
                else               c = hull;

                tex.SetPixel(x, y, c);
            }
        }

        tex.Apply();
        return Sprite.Create(tex, new Rect(0, 0, w, h), new Vector2(0.5f, 0.22f), 16f);
    }

}
