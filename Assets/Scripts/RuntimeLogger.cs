using UnityEngine;
using System.IO;
using System;

/// <summary>
/// Writes game state to runtime_log.txt in the project root every second.
/// Attach to any GameObject (SceneSetup adds it automatically).
/// Claude can read this file to see what the game is doing while it runs.
/// </summary>
public class RuntimeLogger : MonoBehaviour
{
    static readonly string LogFile = Path.Combine(
        Path.GetDirectoryName(Application.dataPath), "runtime_log.txt");

    BoatController _boat;
    Rigidbody2D    _rb;
    float          _timer;
    int            _frame;
    float          _startTime;

    void Start()
    {
        _boat      = FindFirstObjectByType<BoatController>();
        _rb        = _boat ? _boat.GetComponent<Rigidbody2D>() : null;
        _startTime = Time.time;

        File.WriteAllText(LogFile,
            $"=== Runtime Log started {DateTime.Now:yyyy-MM-dd HH:mm:ss} ===\n");
    }

    static readonly string ShotFile = Path.Combine(
        Path.GetDirectoryName(Application.dataPath), "screenshot.png");

    void Update()
    {
        _timer += Time.deltaTime;
        _frame++;

        if (_timer < 1f) return;
        _timer = 0f;

        string entry = $"[t={Time.time - _startTime:F1}s  frame={_frame}]\n";

        if (_boat != null)
        {
            entry += $"  Boat pos:      {_boat.transform.position:F2}\n";
            entry += $"  Boat rotation: {_boat.transform.eulerAngles.z:F1} deg\n";
            entry += $"  Velocity:      {(_rb ? _rb.linearVelocity.magnitude : 0f):F2} u/s\n";
            entry += $"  Angular vel:   {(_rb ? _rb.angularVelocity : 0f):F1} deg/s\n";
            entry += $"  Move speed:    {_boat.moveSpeed}\n";
            entry += $"  Turn inertia:  {_boat.turnInertia}\n";
        }
        else
        {
            entry += "  WARNING: No BoatController found in scene!\n";
        }

        entry += "\n";
        File.AppendAllText(LogFile, entry);
    }

    void OnApplicationQuit()
    {
        File.AppendAllText(LogFile,
            $"=== Session ended {DateTime.Now:HH:mm:ss} (ran {Time.time - _startTime:F0}s) ===\n");
    }
}
