namespace LirinFeatureLauncher;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        ApplicationConfiguration.Initialize();
        try
        {
            string root = RepositoryPaths.Locate().Root;
            var pending = LirinUpdater.Installation.Pending(root);
            if (pending != null && !Environment.GetCommandLineArgs().Contains("--update-confirm"))
            {
                LirinUpdater.SafePaths.Installation(root);
                if (Path.GetFileName(pending.Stage) != "payload") throw new IOException("Invalid recovery journal.");
                using var helper = LirinUpdater.Installation.StartHelper(root, Path.GetDirectoryName(pending.Stage)!, recover: true);
                return;
            }
        }
        catch (Exception e)
        {
            MessageBox.Show("Cannot start while update recovery is unresolved: " + e.Message + "\nKeep .update-* backups and .update-journal.json for recovery.", "Launcher recovery");
            return;
        }
        Application.Run(new MainForm());
    }
}
