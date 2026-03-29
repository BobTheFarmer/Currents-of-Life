using UnityEngine;

/// <summary>
/// Always moves forward. A/D or Left/Right arrows steer.
/// Turn input is pushed by BoatInput.cs (which lives in Assembly-CSharp
/// so it can freely use UnityEngine.InputSystem without asmdef issues).
/// </summary>
[RequireComponent(typeof(Rigidbody2D))]
public class BoatController : MonoBehaviour
{
    [Header("Movement")]
    public float moveSpeed    = 1.5f;   // world units/s — SceneSetup overrides this
    public float turnSpeed    = 55f;
    public float turnInertia  = 0.12f;
    [Tooltip("How slowly turning bleeds off after releasing the key (lower = more drift)")]
    public float turnDecay    = 0.001f;

    [Header("Wake")]
    public ParticleSystem wakeParticles;

    [HideInInspector] public float turnInput;   // written each frame by BoatInput.cs

    Rigidbody2D _rb;

    void Awake()
    {
        _rb = GetComponent<Rigidbody2D>();
        _rb.gravityScale           = 0f;
        _rb.angularDamping         = 2.5f;
        _rb.interpolation          = RigidbodyInterpolation2D.Interpolate;
        _rb.collisionDetectionMode = CollisionDetectionMode2D.Continuous;
    }

    void FixedUpdate()
    {
        _rb.linearVelocity  = -transform.up * moveSpeed;   // sprite bow faces -Y local
        float t = turnInput != 0f ? turnInertia : turnDecay;
        _rb.angularVelocity = Mathf.Lerp(_rb.angularVelocity, -turnInput * turnSpeed, t);
    }
}
