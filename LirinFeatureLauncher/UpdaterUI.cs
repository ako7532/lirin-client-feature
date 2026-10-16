using System.Diagnostics;
using System.Text.RegularExpressions;
using LirinUpdater;

namespace LirinFeatureLauncher;

public sealed partial class MainForm
{
    private readonly GitHubTransport _github = new();
    private readonly CancellationTokenSource _updateLifetime = new();
    private bool _updating, _checking;
    private DateTimeOffset _nextCheck;
    private ToolStripMenuItem _updateMenu = null!;
    private GitHubAuthService Auth => new(_github, new CredentialStore());

    private void InitializeUpdater()
    {
        var menu = new MenuStrip { BackColor = BackColor, ForeColor = ForeColor };
        _updateMenu = new ToolStripMenuItem("Updates");
        _updateMenu.DropDownItems.Add("Connect GitHub", null, async (_, _) => await ConnectGitHub());
        _updateMenu.DropDownItems.Add("Check for updates", null, async (_, _) => await CheckUpdates(true));
        _updateMenu.DropDownItems.Add("Disconnect GitHub", null, (_, _) =>
        { try { Auth.Disconnect(); AppendOutput("GitHub credential removed from this Windows account. Revoke the app on GitHub to revoke its authorization too."); } catch (Exception e) { UpdateError(e, true); } });
        menu.Items.Add(_updateMenu); Controls.Add(menu); MainMenuStrip = menu;
        Shown += async (_, _) =>
        {
            if (await ConfirmUpdateStartup()) await CheckUpdates(false);
        };
        FormClosing += (_, _) => _updateLifetime.Cancel();
    }
    private FileStream? TryInjectionLock()
    {
        try
        {
            if (_paths is null) return null;
            var operation = Installation.Lock(_paths.Root);
            if (Installation.Pending(_paths.Root) != null) { operation.Dispose(); throw new IOException("Update recovery is pending. Restart the launcher first."); }
            return operation;
        }
        catch (Exception e) { ShowFailure("Cannot inject while another launcher operation is active: " + e.Message); return null; }
    }
    private async Task<bool> ConfirmUpdateStartup()
    {
        string[] args = Environment.GetCommandLineArgs().Skip(1).ToArray();
        if (args.Length == 0) return true;
        if (args.Length != 3 || args[0] != "--update-confirm") return false;
        _updating = true; UpdateInjectEnabled();
        try
        {
            if (_paths is null || !Regex.IsMatch(args[2], "^[a-f0-9]{32}$")) throw new IOException("Invalid startup confirmation.");
            SafePaths.Installation(_paths.Root); Installation.ValidateStage(_paths.Root, args[1]);
            var journal = Installation.Pending(_paths.Root) ?? throw new IOException("No pending update.");
            if (journal.State != "awaiting-startup" || Path.GetDirectoryName(journal.Stage) != args[1]) throw new IOException("Wrong update transaction.");
            Package.ValidateDirectory(_paths.Root, Package.Read<PackageMetadata>(Path.Combine(_paths.Root, Package.MetadataName)));
            File.WriteAllText(Path.Combine(args[1], "started-" + args[2]), Environment.ProcessId.ToString());
            var until = DateTime.UtcNow.AddSeconds(35);
            while (Installation.Pending(_paths.Root) != null && DateTime.UtcNow < until) await Task.Delay(100, _updateLifetime.Token);
            if (Installation.Pending(_paths.Root) != null) throw new IOException("Updater did not finalize installation.");
            _updating = false; UpdateInjectEnabled(); return true;
        }
        catch (Exception e) { UpdateError(e, true); Close(); return false; }
    }
    private async Task ConnectGitHub()
    {
        if (_checking || _updating || _busy || _paths is null) return;
        _checking = true; _updateMenu.Enabled = false;
        using var dialog = new UpdateProgressDialog("Connect GitHub", "Requesting a device code...");
        using var cancel = CancellationTokenSource.CreateLinkedTokenSource(_updateLifetime.Token, dialog.Cancellation);
        dialog.Show(this);
        try
        {
            string config = Path.Combine(_paths.Root, "updater.json");
            string clientId = File.Exists(config) ? Package.Read<UpdaterConfig>(config).ClientId : "";
            await Auth.Connect(clientId, code =>
            {
                dialog.SetText($"Enter this code on GitHub: {code.UserCode}\r\n\r\nhttps://github.com/login/device\r\nExpires in {code.ExpiresIn / 60} minutes.\r\nEach person must authorize using their own account.");
                Process.Start(new ProcessStartInfo("https://github.com/login/device") { UseShellExecute = true });
            }, cancel.Token);
            AppendOutput("GitHub connected for this Windows account. Expiring tokens require reconnecting; no client secret is stored.");
        }
        catch (Exception e) { UpdateError(e, true); }
        finally { dialog.Close(); _checking = false; _updateMenu.Enabled = true; }
    }
    private async Task CheckUpdates(bool manual)
    {
        if (_checking || _updating || _paths is null || DateTimeOffset.UtcNow < _nextCheck) return;
        _checking = true; _updateMenu.Enabled = false;
        _nextCheck = DateTimeOffset.UtcNow.AddSeconds(60);
        try
        {
            var credential = Auth.Current();
            if (credential is null)
            {
                AppendOutput("Updates: use Updates > Connect GitHub to authorize your account.");
                if (manual) MessageBox.Show(this, "Connect GitHub from the Updates menu first.", "Updates");
                return;
            }
            string identity = Path.Combine(_paths.Root, "build.json");
            BuildIdentity? installed = File.Exists(identity) ? Package.Read<BuildIdentity>(identity) : null;
            installed?.Validate();
            var candidate = await new GitHubReleaseClient(_github).Check(installed, credential.Token, _updateLifetime.Token);
            if (candidate is null)
            { if (manual) MessageBox.Show(this, installed is null ? "Unknown/local build. Install a published package manually first." : "No newer published build is available.", "Updates"); return; }
            if (_busy) { AppendOutput("A newer build is available. Use Check for updates after injection finishes."); return; }
            using var prompt = new UpdateOfferDialog(installed?.ToString() ?? "Unknown/local build", candidate);
            if (prompt.ShowDialog(this) != DialogResult.OK) return;
            if (installed is null) throw new IOException("Unknown/local build: download and install the first updater-enabled package manually.");
            SafePaths.Installation(_paths.Root);
            Installation.NoGame();
            _updating = true; UpdateInjectEnabled();
            using var operation = Installation.Lock(_paths.Root);
            if (Installation.Pending(_paths.Root) != null) throw new IOException("Update recovery is pending. Restart the launcher.");
            string stage = SafePaths.CreateStage(_paths.Root);
            Package.Write(Path.Combine(stage, "manifest.json"), candidate.Manifest);
            using var progress = new UpdateProgressDialog("Downloading update", "Downloading the complete package...");
            using var cancel = CancellationTokenSource.CreateLinkedTokenSource(_updateLifetime.Token, progress.Cancellation);
            progress.Show(this);
            try
            {
                using (var file = new FileStream(Path.Combine(stage, "release.zip"), FileMode.CreateNew, FileAccess.Write, FileShare.None))
                {
                    await _github.GetAsset(candidate.AssetId, credential.Token, candidate.Manifest.ArchiveSize, cancel.Token, file,
                        new Progress<long>(bytes => progress.SetText($"Downloaded {bytes / 1024:N0} / {candidate.Manifest.ArchiveSize / 1024:N0} KB\r\nYou can cancel before installation.")));
                    file.Flush(true);
                }
                await Task.Run(() => Package.Extract(Path.Combine(stage, "release.zip"), Path.Combine(stage, "validated"), candidate.Manifest, cancel.Token), cancel.Token);
                cancel.Token.ThrowIfCancellationRequested(); Installation.NoGame();
                progress.SetText("Validated. Closing launcher and installing...");
                using var helper = Installation.StartHelper(_paths.Root, stage);
                Close();
            }
            finally { progress.Close(); }
        }
        catch (Exception e) { UpdateError(e, manual); }
        finally { _checking = false; _updating = false; _updateMenu.Enabled = true; UpdateInjectEnabled(); }
    }
    private void UpdateError(Exception error, bool show)
    {
        if (error is OperationCanceledException) { AppendOutput("Update operation cancelled or timed out; nothing was installed."); return; }
        if (error is UpdateException { Kind: UpdateFailure.Authentication })
        { try { Auth.Disconnect(); } catch { /* Credential storage failure must not crash the ordinary launcher. */ } }
        if (error is UpdateException { Kind: UpdateFailure.RateLimit } limited) _nextCheck = limited.RetryAt ?? DateTimeOffset.UtcNow.AddHours(1);
        // Never display raw HTTP bodies, token values or signed download URLs.
        string message = error is UpdateException or IOException or InvalidOperationException ? error.Message : "Update check failed due to invalid metadata or unavailable local resources.";
        AppendOutput("Updates: " + message);
        if (show && !IsDisposed) MessageBox.Show(this, message, "Updates", MessageBoxButtons.OK, MessageBoxIcon.Information);
    }
}

internal sealed class UpdateOfferDialog : Form
{
    public UpdateOfferDialog(string installed, ReleaseCandidate candidate)
    {
        Text = "Launcher update available"; Size = new Size(560, 430); StartPosition = FormStartPosition.CenterParent;
        var notes = new TextBox { Dock = DockStyle.Fill, Multiline = true, ReadOnly = true, ScrollBars = ScrollBars.Vertical,
            Text = $"Installed: {installed}\r\nAvailable: {candidate.Manifest.Build}\r\n\r\n{candidate.Notes}\r\n\r\nClose all Lirin clients before installing. Updates do not change code already loaded in a game process." };
        var buttons = new FlowLayoutPanel { Dock = DockStyle.Bottom, Height = 44, FlowDirection = FlowDirection.RightToLeft };
        var later = new Button { Text = "Later", DialogResult = DialogResult.Cancel };
        var update = new Button { Text = "Update now", DialogResult = DialogResult.OK, AutoSize = true };
        buttons.Controls.Add(later); buttons.Controls.Add(update); Controls.Add(notes); Controls.Add(buttons); CancelButton = later;
    }
}
internal sealed class UpdateProgressDialog : Form
{
    private readonly CancellationTokenSource cancel = new();
    private readonly TextBox text = new() { Dock = DockStyle.Fill, Multiline = true, ReadOnly = true };
    public CancellationToken Cancellation => cancel.Token;
    public UpdateProgressDialog(string title, string message)
    {
        Text = title; Size = new Size(500, 250); StartPosition = FormStartPosition.CenterParent;
        var button = new Button { Text = "Cancel", Dock = DockStyle.Bottom }; button.Click += (_, _) => cancel.Cancel();
        Controls.Add(text); Controls.Add(button); SetText(message); FormClosing += (_, _) => cancel.Cancel();
    }
    public void SetText(string value) { if (!IsDisposed) text.Text = value; }
    protected override void Dispose(bool disposing) { if (disposing) cancel.Dispose(); base.Dispose(disposing); }
}
