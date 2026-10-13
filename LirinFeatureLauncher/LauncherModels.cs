using System.Diagnostics;

namespace LirinFeatureLauncher;

public enum LauncherState
{
    Ready,
    Injecting,
    Injected,
    Failed
}

public sealed record ProcessSnapshot(int Pid, string? ExecutablePath, bool Is64Bit, string WindowTitle, DateTime? StartTime, bool? Responding);

public sealed record GameClientInfo(int Pid, string ExecutablePath, string WindowTitle, DateTime? StartTime, bool? Responding);

public enum DiscoveryIssueKind
{
    AccessDenied,
    Exited,
    Unavailable
}

public sealed record DiscoveryIssue(int? Pid, DiscoveryIssueKind Kind, string Message);

public sealed record DiscoveryResult(IReadOnlyList<GameClientInfo> Clients, IReadOnlyList<DiscoveryIssue> Issues);

public sealed record ProcessValidationResult(bool IsValid, GameClientInfo? Client, string? Error)
{
    public static ProcessValidationResult Valid(GameClientInfo client) => new(true, client, null);
    public static ProcessValidationResult Invalid(string error) => new(false, null, error);
}

public sealed record ProcessOutputLine(bool IsError, string Text);

public sealed record ProcessExecutionResult(int? ExitCode, bool TimedOut, string StandardOutput, string StandardError);

public sealed record StatusPresentation(LauncherState State, string Message)
{
    public static StatusPresentation ForDiscovery(DiscoveryResult result)
    {
        if (result.Clients.Count > 0)
        {
            return new(LauncherState.Ready, $"Ready - {result.Clients.Count} game client(s) found.");
        }

        DiscoveryIssue? accessIssue = result.Issues.FirstOrDefault(issue => issue.Kind == DiscoveryIssueKind.AccessDenied);
        return accessIssue is not null
            ? new(LauncherState.Failed, "Access denied while inspecting Lirin processes. Restart this launcher as administrator.")
            : new(LauncherState.Ready, "Ready - no valid 64-bit Lirin game clients are running.");
    }

    public static StatusPresentation ForExecution(ProcessExecutionResult result)
    {
        if (!result.TimedOut && result.ExitCode == 0)
        {
            return new(LauncherState.Injected, "Injected - the runner confirmed that the Python feature script returned successfully.");
        }

        string detail = result.TimedOut
            ? "The injection runner timed out."
            : $"The injection runner exited with code {result.ExitCode?.ToString() ?? "unknown"}.";
        string stderr = LastNonEmptyLine(result.StandardError);
        if (stderr.Length > 0)
        {
            detail += $" {stderr}";
        }

        return new(LauncherState.Failed, $"Failed - {detail}");
    }

    private static string LastNonEmptyLine(string value) =>
        value.Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries).LastOrDefault() ?? string.Empty;
}

public static class ProcessFilter
{
    public const string ExpectedGamePath = @"C:\Program Files (x86)\Lirin\app\Lirin.exe";

    public static IReadOnlyList<GameClientInfo> ValidGameClients(IEnumerable<ProcessSnapshot> snapshots)
    {
        return snapshots
            .Where(snapshot => snapshot.Is64Bit && PathsEqual(snapshot.ExecutablePath, ExpectedGamePath))
            .Select(snapshot => new GameClientInfo(snapshot.Pid, snapshot.ExecutablePath!, snapshot.WindowTitle, snapshot.StartTime, snapshot.Responding))
            .OrderBy(client => client.Pid)
            .ToArray();
    }

    public static bool PathsEqual(string? left, string? right)
    {
        if (string.IsNullOrWhiteSpace(left) || string.IsNullOrWhiteSpace(right))
        {
            return false;
        }

        try
        {
            return string.Equals(
                Path.GetFullPath(left).TrimEnd(Path.DirectorySeparatorChar),
                Path.GetFullPath(right).TrimEnd(Path.DirectorySeparatorChar),
                StringComparison.OrdinalIgnoreCase);
        }
        catch (Exception exception) when (exception is ArgumentException or NotSupportedException or PathTooLongException)
        {
            return false;
        }
    }
}

public static class SelectionPreserver
{
    public static int? Preserve(int? selectedPid, IEnumerable<GameClientInfo> refreshedClients)
    {
        return selectedPid is not null && refreshedClients.Any(client => client.Pid == selectedPid.Value)
            ? selectedPid
            : null;
    }
}

public static class InjectionCommandBuilder
{
    public static string PowerShellPath => Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Windows), "System32", "WindowsPowerShell", "v1.0", "powershell.exe");

    public static ProcessStartInfo Build(string repositoryRoot, int targetPid)
    {
        if (targetPid <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(targetPid));
        }

        string runner = Path.Combine(repositoryRoot, "run_client_feature.ps1");
        ProcessStartInfo startInfo = new()
        {
            FileName = PowerShellPath,
            WorkingDirectory = repositoryRoot,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true
        };
        startInfo.ArgumentList.Add("-NoProfile");
        startInfo.ArgumentList.Add("-NonInteractive");
        startInfo.ArgumentList.Add("-ExecutionPolicy");
        startInfo.ArgumentList.Add("Bypass");
        startInfo.ArgumentList.Add("-File");
        startInfo.ArgumentList.Add(runner);
        startInfo.ArgumentList.Add("-TargetPid");
        startInfo.ArgumentList.Add(targetPid.ToString(System.Globalization.CultureInfo.InvariantCulture));
        return startInfo;
    }
}
