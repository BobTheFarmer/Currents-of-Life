using UnityEngine;

/// <summary>
/// Emits particles that drift with the ocean current behind the boat.
/// Particles flow roughly eastward (matching the Kuroshio/LIC texture)
/// with organic spread — not a rigid V-wake.
/// Automatically scales with boat world size.
/// </summary>
[RequireComponent(typeof(ParticleSystem))]
public class WaterWake : MonoBehaviour
{
    [Tooltip("Signed distance from boat pivot to spawn point along transform.up.")]
    public float sternOffset = 1.365f;

    [Tooltip("Set to -1 to reverse the direction particles move away from the boat.")]
    public float particleDirection = 1f;

    ParticleSystem _ps;
    Rigidbody2D    _rb;
    Transform      _boat;
    float          _timer;

    // Ocean current direction in world space (matches the LIC texture flow)
    // Mostly eastward with slight northward component — Kuroshio Extension
    static readonly Vector2 CurrentDir = new Vector2(0.85f, 0.22f);

    void Awake()
    {
        _ps   = GetComponent<ParticleSystem>();
        _boat = transform.parent;
        _rb   = _boat != null ? _boat.GetComponent<Rigidbody2D>() : null;
        Configure();
    }

    float BoatScale() => _boat != null ? Mathf.Max(_boat.lossyScale.x, 0.01f) : 1f;

    void Configure()
    {
        float s = BoatScale();

        var rend = _ps.GetComponent<ParticleSystemRenderer>();
        var mat  = new Material(Shader.Find("Universal Render Pipeline/Particles/Unlit")
                             ?? Shader.Find("Sprites/Default"));
        mat.SetColor("_BaseColor", Color.white);
        rend.material      = mat;
        rend.sortingOrder  = 1;

        var emission = _ps.emission;
        emission.enabled = false;

        var main = _ps.main;
        main.loop            = true;
        main.playOnAwake     = false;
        main.simulationSpace = ParticleSystemSimulationSpace.World;
        main.startLifetime   = new ParticleSystem.MinMaxCurve(2.5f, 4.5f);
        main.startSpeed      = 0f;
        main.startSize       = new ParticleSystem.MinMaxCurve(0.04f * s, 0.12f * s);
        main.startColor      = new Color(1f, 1f, 1f, 0.85f);
        main.maxParticles    = 400;
        main.gravityModifier = 0f;

        // Fade out slowly — like foam diffusing into the current
        var col = _ps.colorOverLifetime;
        col.enabled = true;
        var grad = new Gradient();
        grad.SetKeys(
            new[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(Color.white, 1f) },
            new[] { new GradientAlphaKey(0.9f, 0f), new GradientAlphaKey(0f, 1f) }
        );
        col.color = new ParticleSystem.MinMaxGradient(grad);

        var size = _ps.sizeOverLifetime;
        size.enabled = true;
        size.size = new ParticleSystem.MinMaxCurve(1f,
            new AnimationCurve(new Keyframe(0f, 0.3f), new Keyframe(0.15f, 1f), new Keyframe(1f, 0.1f)));

        _ps.Play();
    }

    void Update()
    {
        if (_boat == null) return;

        _timer += Time.deltaTime;
        if (_timer < 0.18f) return;
        _timer = 0f;

        float s     = BoatScale();
        float turb  = _rb != null ? Mathf.Abs(_rb.angularVelocity) * 0.002f : 0f;

        // Use actual rigidbody velocity — no _boat.up ambiguity.
        Vector2 vel      = _rb != null ? _rb.linearVelocity : -(Vector2)_boat.up;
        float   speed    = vel.magnitude;
        // "Behind" = opposite of movement direction
        Vector2 trailDir = speed > 0.05f ? -vel.normalized : -(Vector2)_boat.up;

        // Spawn offset along trail direction. sternOffset controls distance+sign.
        Vector3 stern = _boat.position + (Vector3)(trailDir * Mathf.Abs(sternOffset) * s);

        int count = Mathf.Max(1, Mathf.RoundToInt(speed * 0.6f));
        var ep = new ParticleSystem.EmitParams();

        for (int i = 0; i < count; i++)
        {
            ep.position = stern + (Vector3)(Random.insideUnitCircle * 0.12f * s);

            // particleDirection: 1 = trail behind boat, -1 = shoot forward
            Vector2 trail   = trailDir * particleDirection * Random.Range(0.3f, 0.7f) * s;
            Vector2 current = CurrentDir.normalized * Random.Range(0.03f, 0.08f) * s;
            Vector2 noise   = Random.insideUnitCircle * (0.06f + turb) * s;

            ep.velocity      = (Vector3)(trail + current + noise);
            ep.startSize     = Random.Range(0.04f, 0.12f) * s;
            ep.startLifetime = Random.Range(2.5f, 4.5f);
            ep.startColor    = new Color(1f, 1f, 1f, Random.Range(0.5f, 0.9f));
            _ps.Emit(ep, 1);
        }
    }
}
