using System.Diagnostics;
using LirinUpdater;

internal static class Program
{
    [STAThread]
    private static void Main(string[] args)
    {
        string? root = null;
        try
        {
            if (args.Length != 5 || args[0] is not ("install" or "recover")) throw new IOException("Invalid helper arguments.");
            root = Path.GetFullPath(args[1]); string stage = Path.GetFullPath(args[2]);
            SafePaths.Installation(root); Installation.ValidateStage(root, stage);
            // Pin process identity before waiting; never kill a process or trust a reused PID.
            try
            {
                using var parent = Process.GetProcessById(int.Parse(args[3]));
                if (parent.StartTime.ToUniversalTime().Ticks != long.Parse(args[4]) ||
                    !string.Equals(parent.MainModule?.FileName, Path.Combine(root, "LirinFeatureLauncher.exe"), StringComparison.OrdinalIgnoreCase))
                    throw new IOException("Launcher process identity changed.");
                if (!parent.WaitForExit(60000)) throw new IOException("Launcher did not exit within 60 seconds. Close it and retry.");
            }
            catch (ArgumentException) { /* Parent already exited. */ }
            using var operation = Installation.Lock(root);
            Installation.NoGame();
            if (args[0] == "recover")
            {
                var pending = Installation.Pending(root);
                if (pending != null)
                {
                    if (Path.GetFileName(pending.Stage) != "payload") throw new IOException("Invalid recovery path.");
                    Installation.ValidateStage(root, Path.GetDirectoryName(pending.Stage)!);
                    SafePaths.AssertProtected(pending.Stage);
                }
                Installation.Rollback(root); StartLauncher(root); return;
            }
            var manifest = Package.Read<ReleaseManifest>(Path.Combine(stage, "manifest.json"));
            // Validate the protected archive again and freshly extract immediately before applying.
            string payload = Path.Combine(stage, "payload");
            var metadata = Package.Extract(Path.Combine(stage, "release.zip"), payload, manifest);
            // Transaction journal points at payload's parent; use payload itself for backups/data.
            try
            {
                Installation.Apply(root, payload, metadata);
                string nonce = Guid.NewGuid().ToString("N");
                using var launcher = StartLauncher(root, stage, nonce);
                string acknowledgement = Path.Combine(stage, "started-" + nonce);
                var until = DateTime.UtcNow.AddSeconds(30);
                while (!File.Exists(acknowledgement) && !launcher.HasExited && DateTime.UtcNow < until) Thread.Sleep(100);
                if (!File.Exists(acknowledgement))
                {
                    if (!launcher.HasExited) { launcher.CloseMainWindow(); launcher.WaitForExit(5000); }
                    throw new IOException("Updated launcher did not confirm startup; restoring previous build.");
                }
                Installation.Confirm(root);
            }
            catch
            {
                Installation.Rollback(root);
                using var restored = StartLauncher(root);
                throw;
            }
        }
        catch (Exception error)
        {
            MessageBox.Show($"Update failed: {error.Message}\n\nInstallation: {root ?? "unknown"}\nRecovery journal: {Installation.JournalName}\nBackups remain in the .update-* folder. Close launchers and reopen the installed launcher to retry recovery. If recovery fails, keep the journal/backups and restore the original package manually.",
                "Lirin updater", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }
    private static Process StartLauncher(string root, string? stage = null, string? nonce = null)
    {
        var info = new ProcessStartInfo(Path.Combine(root, "LirinFeatureLauncher.exe")) { UseShellExecute = false, WorkingDirectory = root };
        if (stage != null) { info.ArgumentList.Add("--update-confirm"); info.ArgumentList.Add(stage); info.ArgumentList.Add(nonce!); }
        return Process.Start(info) ?? throw new IOException("Could not restart launcher.");
    }
}
