using UnityEditor;
using UnityEditor.Compilation;
using UnityEngine;
using System;
using System.IO;
using System.Linq;

/// <summary>
/// Writes compile_status.txt to the project root after every script reload.
/// Clears stale data on each new domain reload so results are always current.
/// </summary>
[InitializeOnLoad]
public static class CompileWatcher
{
    static readonly string ProjectRoot  = Path.GetDirectoryName(Application.dataPath);
    static readonly string StatusFile   = Path.Combine(ProjectRoot, "compile_status.txt");

    static int _errorCount;
    static int _assemblyCount;

    static CompileWatcher()
    {
        // Clear old status and mark start of this compile cycle
        File.WriteAllText(StatusFile,
            $"=== Domain reload at {DateTime.Now:yyyy-MM-dd HH:mm:ss} — compiling... ===\n");

        CompilationPipeline.compilationStarted      += OnCompilationStarted;
        CompilationPipeline.compilationFinished     += OnCompilationFinished;
        CompilationPipeline.assemblyCompilationFinished += OnAssemblyFinished;
    }

    static void OnCompilationStarted(object ctx)
    {
        _errorCount    = 0;
        _assemblyCount = 0;
        File.WriteAllText(StatusFile,
            $"=== Compilation started at {DateTime.Now:HH:mm:ss} ===\n");
    }

    static void OnAssemblyFinished(string assemblyPath, CompilerMessage[] messages)
    {
        _assemblyCount++;
        var errors   = messages.Where(m => m.type == CompilerMessageType.Error).ToArray();
        var warnings = messages.Where(m => m.type == CompilerMessageType.Warning).ToArray();
        _errorCount += errors.Length;

        string asmName = Path.GetFileNameWithoutExtension(assemblyPath);

        if (errors.Length == 0 && warnings.Length == 0) return; // stay quiet on clean assemblies

        string line = $"[{DateTime.Now:HH:mm:ss}] {asmName}: {errors.Length} errors, {warnings.Length} warnings\n";
        foreach (var e in errors)
            line += $"  ERROR   {e.file}({e.line}): {e.message}\n";
        foreach (var w in warnings)
            line += $"  WARN    {w.file}({w.line}): {w.message}\n";

        File.AppendAllText(StatusFile, line);
    }

    static void OnCompilationFinished(object ctx)
    {
        string result = _errorCount == 0
            ? $"✓ BUILD CLEAN — {_assemblyCount} assemblies, 0 errors  [{DateTime.Now:HH:mm:ss}]\n"
            : $"✗ BUILD FAILED — {_errorCount} error(s) across {_assemblyCount} assemblies  [{DateTime.Now:HH:mm:ss}]\n";

        File.AppendAllText(StatusFile, result);
    }
}
