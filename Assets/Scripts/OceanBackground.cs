using System.Collections;
using System.IO;
using UnityEngine;

/// <summary>
/// Displays a pre-baked high-resolution LIC ocean texture.
/// Fixed in world space — camera and boat move through it.
/// Loads ocean_lic.png from StreamingAssets/OceanData/.
/// Self-bootstrapping via RuntimeInitializeOnLoadMethod.
/// </summary>
public class OceanBackground : MonoBehaviour
{
    // ── Auto-spawn ────────────────────────────────────────────────────────────

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void AutoSpawn()
    {
        if (FindAnyObjectByType<OceanBackground>() != null) return;

        var go = new GameObject("Ocean [auto]");
        go.transform.position   = new Vector3(0f, 0f, 2f);
        go.transform.localScale = new Vector3(80f, 40f, 1f);
        go.AddComponent<OceanBackground>();
        DontDestroyOnLoad(go);
    }

    // ── Private state ─────────────────────────────────────────────────────────

    MeshRenderer _mr;
    Material     _mat;
    bool         _ready;
    Vector2      _flowOffset;

    // ── Unity lifecycle ───────────────────────────────────────────────────────

    void Awake()
    {
        _mr = GetComponent<MeshRenderer>();
        if (!_mr) _mr = gameObject.AddComponent<MeshRenderer>();
        _mr.sortingOrder = -10;

        // Disable any SpriteRenderer that might conflict
        var sr = GetComponent<SpriteRenderer>();
        if ((bool)sr) sr.enabled = false;
    }

    void Start()
    {
        SetupMesh();
        SetupMaterial();
        StartCoroutine(LoadTexture());
    }

    void Update()
    {
        if (!_ready || _mat == null) return;

        var cam = Camera.main;
        if (cam == null) return;

        // Follow camera so the ocean always fills the screen
        transform.position = new Vector3(cam.transform.position.x,
                                         cam.transform.position.y, 2f);

        // Slow time-based drift in current direction
        float flowSpeed = 0.0004f;
        _flowOffset.x -= 0.85f * flowSpeed * Time.deltaTime;
        _flowOffset.y -= 0.22f * flowSpeed * Time.deltaTime;

        // Camera parallax at half scale — ocean scrolls as you sail but UV stays
        // within [0, 0.5] so the Mirror wrap never shows a hard seam.
        float oceanW = transform.localScale.x;
        float oceanH = transform.localScale.y;
        float camOffX = -cam.transform.position.x / (oceanW * 2f);
        float camOffY = -cam.transform.position.y / (oceanH * 2f);

        _mat.SetVector("_Offset", new Vector4(
            camOffX + _flowOffset.x,
            camOffY + _flowOffset.y,
            0f, 0f));
    }

    // ── Mesh ──────────────────────────────────────────────────────────────────

    void SetupMesh()
    {
        var mf = GetComponent<MeshFilter>();
        if (!mf) mf = gameObject.AddComponent<MeshFilter>();
        mf.mesh = BuildQuad();
    }

    static Mesh BuildQuad()
    {
        var m = new Mesh { name = "OceanQuad" };
        m.vertices  = new[] {
            new Vector3(-0.5f, -0.5f, 0f), new Vector3(0.5f, -0.5f, 0f),
            new Vector3(-0.5f,  0.5f, 0f), new Vector3(0.5f,  0.5f, 0f),
        };
        m.uv        = new[] {
            new Vector2(0,0), new Vector2(1,0),
            new Vector2(0,1), new Vector2(1,1)
        };
        m.triangles = new[] { 0, 2, 1, 2, 3, 1 };
        m.RecalculateNormals();
        return m;
    }

    // ── Material ──────────────────────────────────────────────────────────────

    void SetupMaterial()
    {
        // Use our custom URP shader — guaranteed to exist and render correctly
        var shader = Shader.Find("Build4Good/ScrollingWater")
                  ?? Shader.Find("Universal Render Pipeline/Unlit")
                  ?? Shader.Find("Sprites/Default");

        if (shader == null)
        {
            Debug.LogError("[OceanBackground] No usable shader found.");
            return;
        }

        Debug.Log($"[OceanBackground] Shader: {shader.name}");
        _mat = new Material(shader);

        // Dark ocean fallback while loading — never white
        _mat.SetTexture("_MainTex", BuildDarkTexture());
        _mat.SetTexture("_BaseMap",  BuildDarkTexture());

        _mr.material = _mat;
    }

    void SetTex(Texture tex)
    {
        if (_mat == null || tex == null) return;
        _mat.SetTexture("_MainTex", tex);
        _mat.SetTexture("_BaseMap",  tex);
        _mat.mainTexture = tex;
    }

    // ── Load pre-baked LIC texture ────────────────────────────────────────────

    IEnumerator LoadTexture()
    {
        yield return null;   // let first frame render with dark fallback

        string path = Path.Combine(Application.streamingAssetsPath,
                                   "OceanData", "ocean_lic.png");

        if (!File.Exists(path))
        {
            Debug.LogWarning("[OceanBackground] ocean_lic.png not found — " +
                             "run make_strings2.py to generate it.");
            SetTex(BuildDarkTexture());
            _ready = true;
            yield break;
        }

        var tex = new Texture2D(2, 2, TextureFormat.RGB24, false)
        {
            filterMode = FilterMode.Bilinear,
            wrapMode   = TextureWrapMode.Mirror
        };
        tex.LoadImage(File.ReadAllBytes(path));
        Debug.Log($"[OceanBackground] Loaded ocean_lic.png ({tex.width}×{tex.height})");

        SetTex(tex);
        _ready = true;
    }

    // ── Dark placeholder texture (deep ocean navy) ────────────────────────────

    static Texture2D BuildDarkTexture()
    {
        int cell = 16, size = 128;
        var tex = new Texture2D(size, size, TextureFormat.RGBA32, false)
        {
            filterMode = FilterMode.Point,
            wrapMode   = TextureWrapMode.Repeat
        };
        var bg   = new Color(0.008f, 0.022f, 0.055f);   // deep navy
        var line = new Color(0.012f, 0.035f, 0.080f);
        for (int y = 0; y < size; y++)
        for (int x = 0; x < size; x++)
            tex.SetPixel(x, y, (x % cell == 0 || y % cell == 0) ? line : bg);
        tex.Apply();
        return tex;
    }
}
