using System.Diagnostics;
using System.Text;

namespace LirinFeatureLauncher;

public sealed class ProcessExecutor
{
    public async Task<ProcessExecutionResult> RunAsync(ProcessStartInfo startInfo, Action<ProcessOutputLine> onOutput, TimeSpan timeout, CancellationToken cancellationToken = default)
    {
        using Process process = new() { StartInfo = startInfo };
        StringBuilder stdout = new();
        StringBuilder stderr = new();
        TaskCompletionSource stdoutClosed = new(TaskCreationOptions.RunContinuationsAsynchronously);
        TaskCompletionSource stderrClosed = new(TaskCreationOptions.RunContinuationsAsynchronously);

        process.OutputDataReceived += (_, eventArgs) =>
        {
            if (eventArgs.Data is null)
            {
                stdoutClosed.TrySetResult();
                return;
            }

            lock (stdout) { stdout.AppendLine(eventArgs.Data); }
            onOutput(new(false, eventArgs.Data));
        };
        process.ErrorDataReceived += (_, eventArgs) =>
        {
            if (eventArgs.Data is null)
            {
                stderrClosed.TrySetResult();
                return;
            }

            lock (stderr) { stderr.AppendLine(eventArgs.Data); }
            onOutput(new(true, eventArgs.Data));
        };

        if (!process.Start())
        {
            throw new InvalidOperationException($"Failed to start {startInfo.FileName}.");
        }

        process.BeginOutputReadLine();
        process.BeginErrorReadLine();

        using CancellationTokenSource timeoutSource = new(timeout);
        using CancellationTokenSource linkedSource = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken, timeoutSource.Token);
        bool timedOut = false;
        try
        {
            await process.WaitForExitAsync(linkedSource.Token).ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (timeoutSource.IsCancellationRequested && !cancellationToken.IsCancellationRequested)
        {
            timedOut = true;
            TryKill(process);
            await process.WaitForExitAsync(CancellationToken.None).ConfigureAwait(false);
        }
        catch (OperationCanceledException)
        {
            TryKill(process);
            await process.WaitForExitAsync(CancellationToken.None).ConfigureAwait(false);
            throw;
        }

        await Task.WhenAll(stdoutClosed.Task, stderrClosed.Task).ConfigureAwait(false);
        return new(process.ExitCode, timedOut, ReadLocked(stdout), ReadLocked(stderr));
    }

    private static void TryKill(Process process)
    {
        try
        {
            if (!process.HasExited)
            {
                process.Kill(entireProcessTree: true);
            }
        }
        catch (Exception exception) when (exception is InvalidOperationException or System.ComponentModel.Win32Exception)
        {
        }
    }

    private static string ReadLocked(StringBuilder builder)
    {
        lock (builder) { return builder.ToString(); }
    }
}
