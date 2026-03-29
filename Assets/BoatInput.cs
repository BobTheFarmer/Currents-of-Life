using UnityEngine;
using UnityEngine.InputSystem;

/// <summary>
/// Reads keyboard input and pushes turnInput to BoatController.
/// Lives in Assembly-CSharp (no asmdef) so UnityEngine.InputSystem
/// resolves automatically — no assembly reference wrangling needed.
/// Auto-attaches to any BoatController in the scene at startup.
/// </summary>
public class BoatInput : MonoBehaviour
{
    BoatController _boat;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void AutoAttach()
    {
        var boat = Object.FindFirstObjectByType<BoatController>();
        if (boat == null) return;
        if (boat.GetComponent<BoatInput>() == null)
            boat.gameObject.AddComponent<BoatInput>();
    }

    void Awake() => _boat = GetComponent<BoatController>();

    void Update()
    {
        if (_boat == null) return;
        _boat.turnInput = 0f;
        if (Keyboard.current == null) return;
        if (Keyboard.current.aKey.isPressed || Keyboard.current.leftArrowKey.isPressed)
            _boat.turnInput += 1f;
        if (Keyboard.current.dKey.isPressed || Keyboard.current.rightArrowKey.isPressed)
            _boat.turnInput -= 1f;
    }
}
