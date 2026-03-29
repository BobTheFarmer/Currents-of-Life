using NUnit.Framework;
using UnityEngine;

/// <summary>
/// EditMode tests — run via Window > General > Test Runner > EditMode.
/// These verify script logic without needing Play mode.
/// </summary>
public class BoatControllerTests
{
    GameObject _go;

    [SetUp]
    public void SetUp()
    {
        _go = new GameObject("TestBoat");
        _go.AddComponent<Rigidbody2D>();
    }

    [TearDown]
    public void TearDown()
    {
        Object.DestroyImmediate(_go);
    }

    [Test]
    public void BoatController_DefaultMoveSpeed_IsPositive()
    {
        var boat = _go.AddComponent<BoatController>();
        Assert.Greater(boat.moveSpeed, 0f, "moveSpeed must be > 0 to move forward");
    }

    [Test]
    public void BoatController_DefaultTurnSpeed_IsPositive()
    {
        var boat = _go.AddComponent<BoatController>();
        Assert.Greater(boat.turnSpeed, 0f, "turnSpeed must be > 0 to allow steering");
    }

    [Test]
    public void BoatController_TurnInertia_IsInValidRange()
    {
        var boat = _go.AddComponent<BoatController>();
        Assert.GreaterOrEqual(boat.turnInertia, 0f, "turnInertia cannot be negative");
        Assert.Less(boat.turnInertia, 1f, "turnInertia of 1 would mean boat never turns");
    }

    [Test]
    public void BoatController_RequiresRigidbody2D()
    {
        // GameObject already has Rigidbody2D from SetUp — adding BoatController should work
        var boat = _go.AddComponent<BoatController>();
        Assert.IsNotNull(boat);
        Assert.IsNotNull(_go.GetComponent<Rigidbody2D>(),
            "BoatController needs a Rigidbody2D on the same GameObject");
    }

    [Test]
    public void CameraFollow_DefaultSmoothSpeed_IsPositive()
    {
        var camGO = new GameObject("TestCamera");
        camGO.AddComponent<Camera>();
        var follow = camGO.AddComponent<CameraFollow>();
        Assert.Greater(follow.smoothSpeed, 0f, "smoothSpeed must be > 0");
        Object.DestroyImmediate(camGO);
    }
}
