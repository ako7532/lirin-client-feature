namespace LirinFeatureLauncher;

public sealed record RepositoryPaths(string Root, string Runner, string FeatureLoader, string FeatureScript, string Injector, string Python)
{
    public static RepositoryPaths FromRoot(string root)
    {
        string fullRoot = Path.TrimEndingDirectorySeparator(Path.GetFullPath(root));
        return new(
            fullRoot,
            Path.Combine(fullRoot, "run_client_feature.ps1"),
            Path.Combine(fullRoot, "client_feature_loader.dll"),
            Path.Combine(fullRoot, "client_feature.py"),
            Path.Combine(fullRoot, "inject.py"),
            @"C:\Users\andrej-pc\AppData\Local\Programs\Python\Python311\python.exe");
    }

    public static RepositoryPaths Locate()
    {
        foreach (string start in new[] { AppContext.BaseDirectory, Environment.CurrentDirectory })
        {
            DirectoryInfo? directory = new(Path.GetFullPath(start));
            for (int depth = 0; directory is not null && depth < 10; depth++, directory = directory.Parent)
            {
                if (File.Exists(Path.Combine(directory.FullName, "run_client_feature.ps1")) && File.Exists(Path.Combine(directory.FullName, "inject.py")))
                {
                    return FromRoot(directory.FullName);
                }
            }
        }

        throw new DirectoryNotFoundException("Could not find run_client_feature.ps1 and inject.py above the launcher directory.");
    }

    public IReadOnlyList<string> ValidateForInjection()
    {
        List<string> errors = new();
        AddMissing(errors, Runner, "Injection runner missing");
        AddMissing(errors, FeatureLoader, "Feature loader missing. Run build.ps1 -FeatureOnly first");
        AddMissing(errors, FeatureScript, "Feature script missing");
        AddMissing(errors, Injector, "Python injector missing");
        AddMissing(errors, Python, "64-bit Python executable missing");
        if (!File.Exists(InjectionCommandBuilder.PowerShellPath))
        {
            errors.Add($"64-bit Windows PowerShell missing: {InjectionCommandBuilder.PowerShellPath}");
        }

        return errors;
    }

    private static void AddMissing(List<string> errors, string path, string label)
    {
        if (!File.Exists(path))
        {
            errors.Add($"{label}: {path}");
        }
    }
}
