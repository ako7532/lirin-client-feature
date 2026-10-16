using System.Diagnostics;

namespace LirinUpdater;

public sealed record Journal(string Stage, string[] Files, string[] Existed, string State);
public static class Installation
{
    public const string JournalName = ".update-journal.json";
    public static FileStream Lock(string root) => new(Path.Combine(root, ".launcher-operation.lock"), FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None);
    public static void NoGame()
    {
        // Conservative: also blocks the launcher or an inaccessible Lirin process. No process memory access.
        var processes = Process.GetProcessesByName("Lirin");
        try { if (processes.Length != 0) throw new IOException("Close all Lirin clients and the game launcher before installing an update."); }
        finally { foreach (var process in processes) process.Dispose(); }
    }
    public static void ValidateStage(string root, string stage)
    {
        if (!string.Equals(
                Path.TrimEndingDirectorySeparator(Path.GetDirectoryName(Path.GetFullPath(stage))!),
                Path.TrimEndingDirectorySeparator(Path.GetFullPath(root)),
                StringComparison.OrdinalIgnoreCase) ||
            !System.Text.RegularExpressions.Regex.IsMatch(Path.GetFileName(stage), "^\\.update-[a-f0-9]{32}$"))
            throw new IOException("Invalid update staging path.");
        SafePaths.AssertProtected(stage);
    }
    public static Journal? Pending(string root)
    {
        string path = Path.Combine(root, JournalName); SafePaths.NoReparse(path);
        if (!File.Exists(path)) return null;
        var journal = Package.Read<Journal>(path);
        return journal.State is "confirmed" or "rolled-back" ? null : journal;
    }
    // Pure file transaction; callers hold the operation lock and enforce platform security policy.
    // The fault hook is used only by deterministic tests to simulate failures between individual writes.
    public static void Apply(string root, string stage, PackageMetadata incoming, Action<int>? afterWrite = null)
    {
        if (Pending(root) is not null) throw new IOException("An earlier update needs recovery.");
        Package.ValidateDirectory(stage, incoming);
        var old = Package.Read<PackageMetadata>(Path.Combine(root, Package.MetadataName));
        Package.ValidateDirectory(root, old);
        if (incoming.Build.Sequence <= old.Build.Sequence) throw new IOException("Refusing an equal/older update.");
        string[] files = old.Files.Select(f => f.Path).Union(incoming.Files.Select(f => f.Path), StringComparer.OrdinalIgnoreCase)
            .Append(Package.MetadataName).ToArray();
        string backup = Path.Combine(stage, "backup"); SafePaths.NoReparse(backup);
        Directory.CreateDirectory(backup);
        var existed = new List<string>();
        foreach (string name in files)
        {
            string destination = SafePaths.Child(root, name);
            if (File.Exists(destination))
            {
                // Newly managed files may not silently overwrite a user's existing file.
                if (name != Package.MetadataName && !old.Files.Any(f => f.Path.Equals(name, StringComparison.OrdinalIgnoreCase)))
                    throw new IOException("A new package file conflicts with an unmanaged file: " + name);
                DurableCopy(destination, SafePaths.Child(backup, name)); existed.Add(name);
            }
        }
        var journal = new Journal(stage, files, existed.ToArray(), "applying");
        Package.Write(Path.Combine(root, JournalName), journal);
        int index = 0;
        foreach (string name in files)
        {
            string destination = SafePaths.Child(root, name);
            if (name == Package.MetadataName || incoming.Files.Any(f => f.Path.Equals(name, StringComparison.OrdinalIgnoreCase)))
                DurableCopy(SafePaths.Child(stage, name), destination);
            else File.Delete(destination);
            afterWrite?.Invoke(++index);
        }
        Package.ValidateDirectory(root, incoming);
        Package.Write(Path.Combine(root, JournalName), journal with { State = "awaiting-startup" });
    }
    public static void Rollback(string root)
    {
        var journal = Pending(root); if (journal is null) return;
        string backup = Path.Combine(journal.Stage, "backup"); SafePaths.NoReparse(backup);
        // Validate every name and the complete original backup before changing anything.
        foreach (string name in journal.Files.Concat(journal.Existed)) Package.ValidateName(name);
        var original = Package.Read<PackageMetadata>(Path.Combine(backup, Package.MetadataName));
        Package.ValidateDirectory(backup, original);
        string[] expectedOriginal = original.Files.Select(f => f.Path).Append(Package.MetadataName).ToArray();
        if (!journal.Existed.Order().SequenceEqual(expectedOriginal.Order()) || journal.Files.Distinct(StringComparer.OrdinalIgnoreCase).Count() != journal.Files.Length)
            throw new InvalidDataException("Invalid recovery journal.");
        foreach (string name in journal.Files)
        {
            string target = SafePaths.Child(root, name);
            if (journal.Existed.Contains(name, StringComparer.OrdinalIgnoreCase)) DurableCopy(SafePaths.Child(backup, name), target);
            else File.Delete(target);
        }
        Package.ValidateDirectory(root, original);
        Package.Write(Path.Combine(root, JournalName), journal with { State = "rolled-back" });
    }
    public static void Confirm(string root)
    {
        var journal = Pending(root) ?? throw new IOException("No update awaiting confirmation.");
        Package.ValidateDirectory(root, Package.Read<PackageMetadata>(Path.Combine(root, Package.MetadataName)));
        Package.Write(Path.Combine(root, JournalName), journal with { State = "confirmed" });
    }
    public static void DurableCopy(string source, string destination)
    {
        SafePaths.NoReparse(source); SafePaths.NoReparse(destination);
        using var input = new FileStream(source, FileMode.Open, FileAccess.Read, FileShare.Read);
        using var output = new FileStream(destination, FileMode.Create, FileAccess.Write, FileShare.None);
        input.CopyTo(output); output.Flush(true);
    }
    public static Process StartHelper(string root, string stage, bool recover = false)
    {
        ValidateStage(root, stage);
        string helperDir = Path.Combine(stage, "helper"); SafePaths.NoReparse(helperDir);
        Directory.CreateDirectory(helperDir);
        if (!recover)
        {
            var installed = Package.Read<PackageMetadata>(Path.Combine(root, Package.MetadataName));
            foreach (var file in installed.Files.Where(f => f.Path.StartsWith("LirinUpdater.", StringComparison.Ordinal)))
            {
                string source = SafePaths.Child(root, file.Path);
                if (Package.Hash(source) != file.Sha256) throw new IOException("Installed helper was modified.");
                DurableCopy(source, Path.Combine(helperDir, file.Path));
            }
        }
        var start = new ProcessStartInfo(Path.Combine(helperDir, "LirinUpdater.Helper.exe")) { UseShellExecute = false, CreateNoWindow = true, WindowStyle = ProcessWindowStyle.Hidden };
        foreach (string arg in new[] { recover ? "recover" : "install", root, stage, Environment.ProcessId.ToString(), Process.GetCurrentProcess().StartTime.ToUniversalTime().Ticks.ToString() }) start.ArgumentList.Add(arg);
        return Process.Start(start) ?? throw new IOException("Could not start updater helper.");
    }
}
