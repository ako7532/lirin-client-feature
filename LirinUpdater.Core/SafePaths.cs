using System.Security.AccessControl;
using System.Security.Principal;

namespace LirinUpdater;

public static class SafePaths
{
    public static void NoReparse(string path)
    {
        string? current = Path.GetFullPath(path);
        while (current is not null)
        {
            try
            {
                if ((File.GetAttributes(current) & FileAttributes.ReparsePoint) != 0)
                    throw new IOException("Reparse points are forbidden in updater paths.");
            }
            catch (FileNotFoundException) { }
            catch (DirectoryNotFoundException) { }
            current = Path.GetDirectoryName(current);
        }
    }
    public static string Child(string root, string name)
    { Package.ValidateName(name); string path = Path.Combine(root, name); NoReparse(path); return path; }
    public static void Installation(string root)
    {
        root = Path.GetFullPath(root); NoReparse(root);
        for (DirectoryInfo? dir = new(root); dir != null; dir = dir.Parent)
            if (Directory.Exists(Path.Combine(dir.FullName, ".git")) || File.Exists(Path.Combine(dir.FullName, ".git")))
                throw new IOException("Updates are disabled in development checkouts.");
        if (!File.Exists(Path.Combine(root, "distribution.json")) ||
            File.ReadAllText(Path.Combine(root, "distribution.json")).Trim() != "\"lirin-private-package-v1\"")
            throw new IOException("Unknown/local build. Install the updater-enabled package manually first.");
        // An elevated helper must never execute/copy code controlled by a medium-integrity process.
        string programFiles = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles).TrimEnd('\\') + "\\";
        if (!root.StartsWith(programFiles, StringComparison.OrdinalIgnoreCase) || root.TrimEnd('\\') == programFiles.TrimEnd('\\'))
            throw new IOException("Move the complete package into a dedicated folder under Program Files before updating.");
        for (DirectoryInfo? dir = new(root); dir != null &&
            (dir.FullName.StartsWith(programFiles, StringComparison.OrdinalIgnoreCase) || dir.FullName.Equals(programFiles.TrimEnd('\\'), StringComparison.OrdinalIgnoreCase)); dir = dir.Parent)
            AssertProtected(dir.FullName);
        foreach (string file in Directory.GetFiles(root)) AssertProtected(file);
    }
    public static void AssertProtected(string path)
    {
        NoReparse(path);
        FileSystemSecurity acl = Directory.Exists(path) ? new DirectoryInfo(path).GetAccessControl() : new FileInfo(path).GetAccessControl();
        var admins = new SecurityIdentifier(WellKnownSidType.BuiltinAdministratorsSid, null);
        var system = new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null);
        var installer = new NTAccount("NT SERVICE", "TrustedInstaller").Translate(typeof(SecurityIdentifier));
        var owner = acl.GetOwner(typeof(SecurityIdentifier));
        if (!admins.Equals(owner) && !system.Equals(owner) && !installer.Equals(owner)) throw new IOException("Updater files must have an administrative owner: " + path);
        const FileSystemRights writes = FileSystemRights.Write | FileSystemRights.Delete | FileSystemRights.DeleteSubdirectoriesAndFiles |
            FileSystemRights.ChangePermissions | FileSystemRights.TakeOwnership;
        foreach (FileSystemAccessRule rule in acl.GetAccessRules(true, true, typeof(SecurityIdentifier)))
            if (rule.AccessControlType == AccessControlType.Allow &&
                ((rule.FileSystemRights & writes) != 0 || (unchecked((uint)rule.FileSystemRights) & 0x50000000u) != 0) &&
                !admins.Equals(rule.IdentityReference) && !system.Equals(rule.IdentityReference) && !installer.Equals(rule.IdentityReference) &&
                rule.IdentityReference.Value != "S-1-3-0") // CREATOR OWNER inherits to the administrative owner
                throw new IOException("Non-administrative write access is forbidden: " + path);
    }
    public static string CreateStage(string root)
    {
        Installation(root);
        string stage = Path.Combine(root, ".update-" + Guid.NewGuid().ToString("N"));
        var acl = new DirectorySecurity();
        acl.SetAccessRuleProtection(true, false);
        var admins = new SecurityIdentifier(WellKnownSidType.BuiltinAdministratorsSid, null);
        acl.SetOwner(admins);
        foreach (var sid in new[] { admins, new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null) })
            acl.AddAccessRule(new FileSystemAccessRule(sid, FileSystemRights.FullControl,
                InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit, PropagationFlags.None, AccessControlType.Allow));
        new DirectoryInfo(stage).Create(acl); AssertProtected(stage); return stage;
    }
}
