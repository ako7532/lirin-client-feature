using System.Diagnostics;
using LirinFeatureLauncher;

List<(string Name, Func<Task> Body)> tests = new()
{
    ("process filtering accepts only exact x64 game path", TestProcessFiltering),
    ("selection is preserved only while PID remains", TestSelectionPreservation),
    ("PowerShell command uses separate arguments", TestCommandArguments),
    ("fast process exits preserve stdout and stderr", TestFastProcessExitRace),
    ("errors are actionable and visible", TestVisibleErrors)
};

int failures = 0;
foreach ((string name, Func<Task> body) in tests)
{
    try
    {
        await body();
        Console.WriteLine($"PASS: {name}");
    }
    catch (Exception exception)
    {
        failures++;
        Console.Error.WriteLine($"FAIL: {name}");
        Console.Error.WriteLine(exception);
    }
}

Console.WriteLine($"{tests.Count - failures}/{tests.Count} tests passed.");
return failures == 0 ? 0 : 1;

static Task TestProcessFiltering()
{
    ProcessSnapshot[] snapshots =
    {
        new(101, ProcessFilter.ExpectedGamePath, true, "Lirin", DateTime.Now, true),
        new(102, @"C:\Program Files (x86)\Lirin\Lirin.exe", false, "Lirin", DateTime.Now, true),
        new(103, @"C:\Elsewhere\Lirin.exe", true, "Lirin", DateTime.Now, true),
        new(104, ProcessFilter.ExpectedGamePath, false, "Lirin", DateTime.Now, true),
        new(105, ProcessFilter.ExpectedGamePath.ToUpperInvariant(), true, "Lirin", DateTime.Now, true)
    };

    IReadOnlyList<GameClientInfo> clients = ProcessFilter.ValidGameClients(snapshots);
    EqualSequence(new[] { 101, 105 }, clients.Select(client => client.Pid).ToArray());
    True(clients.All(client => !ProcessFilter.PathsEqual(client.ExecutablePath, @"C:\Program Files (x86)\Lirin\Lirin.exe")), "Launcher path leaked through filter.");
    return Task.CompletedTask;
}

static Task TestSelectionPreservation()
{
    GameClientInfo[] clients =
    {
        new(30, ProcessFilter.ExpectedGamePath, "Lirin A", null, true),
        new(20, ProcessFilter.ExpectedGamePath, "Lirin B", null, true)
    };
    Equal(20, SelectionPreserver.Preserve(20, clients));
    Equal<int?>(null, SelectionPreserver.Preserve(99, clients));
    Equal<int?>(null, SelectionPreserver.Preserve(null, clients));
    return Task.CompletedTask;
}

static Task TestCommandArguments()
{
    string root = @"C:\Path With Spaces\lirin-client-feature";
    ProcessStartInfo command = InjectionCommandBuilder.Build(root, 4242);
    Equal(InjectionCommandBuilder.PowerShellPath, command.FileName);
    Equal(root, command.WorkingDirectory);
    True(!command.UseShellExecute && command.RedirectStandardOutput && command.RedirectStandardError, "Output redirection is not configured.");
    EqualSequence(
        new[] { "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", Path.Combine(root, "run_client_feature.ps1"), "-TargetPid", "4242" },
        command.ArgumentList.ToArray());
    return Task.CompletedTask;
}

static async Task TestFastProcessExitRace()
{
    ProcessExecutor executor = new();
    for (int index = 0; index < 12; index++)
    {
        ProcessStartInfo command = new()
        {
            FileName = InjectionCommandBuilder.PowerShellPath,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true
        };
        command.ArgumentList.Add("-NoProfile");
        command.ArgumentList.Add("-NonInteractive");
        command.ArgumentList.Add("-Command");
        command.ArgumentList.Add("[Console]::Out.WriteLine('out'); [Console]::Error.WriteLine('err'); exit 0");
        List<ProcessOutputLine> streamed = new();
        ProcessExecutionResult result = await executor.RunAsync(command, line => { lock (streamed) { streamed.Add(line); } }, TimeSpan.FromSeconds(10));
        Equal(0, result.ExitCode);
        True(!result.TimedOut, "Fast process was incorrectly marked timed out.");
        Contains("out", result.StandardOutput);
        Contains("err", result.StandardError);
        lock (streamed)
        {
            True(streamed.Any(line => !line.IsError && line.Text == "out"), "stdout was not streamed.");
            True(streamed.Any(line => line.IsError && line.Text == "err"), "stderr was not streamed.");
        }
    }
}

static Task TestVisibleErrors()
{
    string absentRoot = Path.Combine(Path.GetTempPath(), $"lirin-launcher-absent-{Guid.NewGuid():N}");
    IReadOnlyList<string> errors = RepositoryPaths.FromRoot(absentRoot).ValidateForInjection();
    True(errors.Any(error => error.Contains("Injection runner missing", StringComparison.Ordinal)), "Missing runner error was not actionable.");
    True(errors.Any(error => error.Contains("Feature loader missing", StringComparison.Ordinal)), "Missing loader error was not actionable.");

    DiscoveryResult denied = new(Array.Empty<GameClientInfo>(), new[] { new DiscoveryIssue(12, DiscoveryIssueKind.AccessDenied, "denied") });
    StatusPresentation discoveryPresentation = StatusPresentation.ForDiscovery(denied);
    Equal(LauncherState.Failed, discoveryPresentation.State);
    Contains("administrator", discoveryPresentation.Message);

    StatusPresentation executionPresentation = StatusPresentation.ForExecution(new ProcessExecutionResult(1, false, string.Empty, "specific runner failure\r\n"));
    Equal(LauncherState.Failed, executionPresentation.State);
    Contains("specific runner failure", executionPresentation.Message);
    return Task.CompletedTask;
}

static void True(bool condition, string message)
{
    if (!condition) { throw new InvalidOperationException(message); }
}

static void Contains(string expected, string actual)
{
    if (!actual.Contains(expected, StringComparison.OrdinalIgnoreCase))
    {
        throw new InvalidOperationException($"Expected '{expected}' in '{actual}'.");
    }
}

static void Equal<T>(T expected, T actual)
{
    if (!EqualityComparer<T>.Default.Equals(expected, actual))
    {
        throw new InvalidOperationException($"Expected '{expected}', got '{actual}'.");
    }
}

static void EqualSequence<T>(IReadOnlyList<T> expected, IReadOnlyList<T> actual)
{
    if (!expected.SequenceEqual(actual))
    {
        throw new InvalidOperationException($"Expected [{string.Join(", ", expected)}], got [{string.Join(", ", actual)}].");
    }
}
