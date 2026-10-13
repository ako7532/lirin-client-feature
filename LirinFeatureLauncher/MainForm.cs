using System.Diagnostics;
using System.Security.Principal;

namespace LirinFeatureLauncher;

public sealed class MainForm : Form
{
    private readonly ProcessDiscovery _processDiscovery = new();
    private readonly ProcessExecutor _processExecutor = new();
    private readonly DataGridView _clientGrid = new();
    private readonly Button _refreshButton = new();
    private readonly Button _injectButton = new();
    private readonly Label _stateLabel = new();
    private readonly Label _statusDetailLabel = new();
    private readonly Label _managedClientLabel = new();
    private readonly RichTextBox _output = new();
    private RepositoryPaths? _paths;
    private CancellationTokenSource? _injectionCancellation;
    private bool _busy;
    private bool _refreshing;
    private int? _managedInjectedPid;

    public MainForm()
    {
        InitializeWindow();
        InitializeLayout();

        try
        {
            _paths = RepositoryPaths.Locate();
            AppendOutput($"Repository: {_paths.Root}");
        }
        catch (Exception exception)
        {
            ShowFailure(exception.Message);
        }

        Shown += async (_, _) => await RefreshClientsAsync();
        FormClosing += (_, _) => _injectionCancellation?.Cancel();
    }

    private void InitializeWindow()
    {
        Text = "Lirin Feature Launcher";
        StartPosition = FormStartPosition.CenterScreen;
        MinimumSize = new Size(720, 480);
        Size = new Size(840, 560);
        AutoScaleMode = AutoScaleMode.Dpi;
        Font = new Font("Segoe UI", 9F);
        BackColor = Color.FromArgb(10, 15, 28);
        ForeColor = Color.FromArgb(231, 236, 245);
        DoubleBuffered = true;
    }

    private void InitializeLayout()
    {
        TableLayoutPanel root = new()
        {
            Dock = DockStyle.Fill,
            BackColor = BackColor,
            Padding = new Padding(14, 12, 14, 14),
            ColumnCount = 1,
            RowCount = 6
        };
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 62));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 27));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 48));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 48));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 27));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 52));

        root.Controls.Add(CreateHeader(), 0, 0);
        root.Controls.Add(CreateSectionHeading("RUNNING CLIENTS", "Exact x64 game path only"), 0, 1);
        ConfigureGrid();
        root.Controls.Add(_clientGrid, 0, 2);
        root.Controls.Add(CreateActionBar(), 0, 3);
        root.Controls.Add(CreateSectionHeading("ACTIVITY", "One active injected client"), 0, 4);
        ConfigureOutput();
        root.Controls.Add(_output, 0, 5);
        Controls.Add(root);
        SetStatus(LauncherState.Ready, "Ready - refresh to find game clients.");
    }

    private Control CreateHeader()
    {
        TableLayoutPanel header = new()
        {
            Dock = DockStyle.Fill,
            BackColor = Color.FromArgb(20, 27, 45),
            ColumnCount = 2,
            Margin = new Padding(0, 0, 0, 8),
            Padding = new Padding(14, 7, 12, 6)
        };
        header.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        header.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));

        TableLayoutPanel heading = new()
        {
            Dock = DockStyle.Fill,
            ColumnCount = 1,
            RowCount = 2,
            Margin = new Padding(0)
        };
        heading.RowStyles.Add(new RowStyle(SizeType.Absolute, 29));
        heading.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        Label title = new()
        {
            Dock = DockStyle.Fill,
            Font = new Font("Segoe UI Semibold", 13.5F),
            ForeColor = Color.White,
            Text = "Lirin Feature Launcher",
            TextAlign = ContentAlignment.MiddleLeft
        };
        _statusDetailLabel.Dock = DockStyle.Fill;
        _statusDetailLabel.AutoEllipsis = true;
        _statusDetailLabel.ForeColor = Color.FromArgb(145, 160, 184);
        _statusDetailLabel.TextAlign = ContentAlignment.MiddleLeft;
        heading.Controls.Add(title, 0, 0);
        heading.Controls.Add(_statusDetailLabel, 0, 1);

        FlowLayoutPanel statePanel = new()
        {
            AutoSize = true,
            FlowDirection = FlowDirection.TopDown,
            WrapContents = false,
            Anchor = AnchorStyles.Top | AnchorStyles.Right,
            Margin = new Padding(10, 0, 0, 0)
        };
        _stateLabel.AutoSize = true;
        _stateLabel.Font = new Font("Segoe UI Semibold", 8.5F);
        _stateLabel.Padding = new Padding(10, 4, 10, 4);
        _stateLabel.Margin = new Padding(0);
        _managedClientLabel.AutoSize = true;
        _managedClientLabel.Font = new Font("Segoe UI", 8F);
        _managedClientLabel.ForeColor = Color.FromArgb(145, 160, 184);
        _managedClientLabel.TextAlign = ContentAlignment.MiddleRight;
        _managedClientLabel.Margin = new Padding(0, 4, 0, 0);
        _managedClientLabel.Text = "No managed client";
        statePanel.Controls.Add(_stateLabel);
        statePanel.Controls.Add(_managedClientLabel);

        header.Controls.Add(heading, 0, 0);
        header.Controls.Add(statePanel, 1, 0);
        return header;
    }

    private Control CreateActionBar()
    {
        TableLayoutPanel actions = new()
        {
            Dock = DockStyle.Fill,
            ColumnCount = 3,
            Margin = new Padding(0, 7, 0, 7)
        };
        actions.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 102));
        actions.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 102));
        actions.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));

        _refreshButton.Text = "Refresh";
        StyleButton(_refreshButton, primary: false);
        _refreshButton.Click += async (_, _) => await RefreshClientsAsync();
        _injectButton.Text = "Inject";
        StyleButton(_injectButton, primary: true);
        _injectButton.Enabled = false;
        _injectButton.Click += async (_, _) => await InjectSelectedAsync();

        Label selectionHint = new()
        {
            Dock = DockStyle.Fill,
            ForeColor = Color.FromArgb(145, 160, 184),
            TextAlign = ContentAlignment.MiddleRight,
            Text = "Select one PID to continue"
        };
        actions.Controls.Add(_refreshButton, 0, 0);
        actions.Controls.Add(_injectButton, 1, 0);
        actions.Controls.Add(selectionHint, 2, 0);
        return actions;
    }

    private static Label CreateSectionHeading(string title, string note)
    {
        return new Label
        {
            Dock = DockStyle.Fill,
            Font = new Font("Segoe UI Semibold", 8F),
            ForeColor = Color.FromArgb(145, 160, 184),
            TextAlign = ContentAlignment.BottomLeft,
            Text = $"{title}     {note}",
            Padding = new Padding(1, 0, 0, 4)
        };
    }

    private static void StyleButton(Button button, bool primary)
    {
        button.Dock = DockStyle.Fill;
        button.Margin = new Padding(0, 0, 8, 0);
        button.FlatStyle = FlatStyle.Flat;
        button.FlatAppearance.BorderSize = primary ? 0 : 1;
        button.FlatAppearance.BorderColor = Color.FromArgb(52, 65, 91);
        button.FlatAppearance.MouseOverBackColor = primary
            ? Color.FromArgb(116, 143, 255)
            : Color.FromArgb(31, 42, 67);
        button.BackColor = primary ? Color.FromArgb(94, 124, 245) : Color.FromArgb(20, 27, 45);
        button.ForeColor = Color.White;
        button.Font = new Font("Segoe UI Semibold", 9F);
        button.Cursor = Cursors.Hand;
        button.UseVisualStyleBackColor = false;
    }

    private void ConfigureGrid()
    {
        _clientGrid.Dock = DockStyle.Fill;
        _clientGrid.AllowUserToAddRows = false;
        _clientGrid.AllowUserToDeleteRows = false;
        _clientGrid.AllowUserToResizeRows = false;
        _clientGrid.AutoGenerateColumns = false;
        _clientGrid.MultiSelect = false;
        _clientGrid.ReadOnly = true;
        _clientGrid.RowHeadersVisible = false;
        _clientGrid.SelectionMode = DataGridViewSelectionMode.FullRowSelect;
        _clientGrid.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill;
        _clientGrid.BackgroundColor = Color.FromArgb(13, 19, 33);
        _clientGrid.BorderStyle = BorderStyle.None;
        _clientGrid.CellBorderStyle = DataGridViewCellBorderStyle.SingleHorizontal;
        _clientGrid.GridColor = Color.FromArgb(37, 48, 72);
        _clientGrid.EnableHeadersVisualStyles = false;
        _clientGrid.ColumnHeadersBorderStyle = DataGridViewHeaderBorderStyle.None;
        _clientGrid.ColumnHeadersHeight = 30;
        _clientGrid.ColumnHeadersDefaultCellStyle = new DataGridViewCellStyle
        {
            BackColor = Color.FromArgb(20, 27, 45),
            ForeColor = Color.FromArgb(145, 160, 184),
            Font = new Font("Segoe UI Semibold", 8F),
            SelectionBackColor = Color.FromArgb(20, 27, 45),
            Alignment = DataGridViewContentAlignment.MiddleLeft,
            Padding = new Padding(5, 0, 0, 0)
        };
        _clientGrid.DefaultCellStyle = new DataGridViewCellStyle
        {
            BackColor = Color.FromArgb(13, 19, 33),
            ForeColor = Color.FromArgb(220, 226, 237),
            SelectionBackColor = Color.FromArgb(45, 63, 103),
            SelectionForeColor = Color.White,
            Font = new Font("Segoe UI", 8.5F),
            Padding = new Padding(5, 0, 0, 0)
        };
        _clientGrid.AlternatingRowsDefaultCellStyle.BackColor = Color.FromArgb(16, 23, 39);
        _clientGrid.RowTemplate.Height = 29;
        _clientGrid.Columns.Add(new DataGridViewTextBoxColumn { HeaderText = "PID", FillWeight = 12, MinimumWidth = 64 });
        _clientGrid.Columns.Add(new DataGridViewTextBoxColumn { HeaderText = "WINDOW", FillWeight = 19, MinimumWidth = 100 });
        _clientGrid.Columns.Add(new DataGridViewTextBoxColumn { HeaderText = "STARTED", FillWeight = 18, MinimumWidth = 110 });
        _clientGrid.Columns.Add(new DataGridViewTextBoxColumn { HeaderText = "STATUS", FillWeight = 15, MinimumWidth = 92 });
        _clientGrid.Columns.Add(new DataGridViewTextBoxColumn { HeaderText = "EXECUTABLE", FillWeight = 48, MinimumWidth = 220 });
        _clientGrid.SelectionChanged += (_, _) => UpdateInjectEnabled();
    }

    private void ConfigureOutput()
    {
        _output.Dock = DockStyle.Fill;
        _output.ReadOnly = true;
        _output.BackColor = Color.FromArgb(13, 19, 33);
        _output.ForeColor = Color.FromArgb(194, 204, 220);
        _output.BorderStyle = BorderStyle.None;
        _output.Font = new Font("Consolas", 8.5F);
        _output.WordWrap = false;
        _output.DetectUrls = false;
    }

    private async Task RefreshClientsAsync()
    {
        if (_busy || _refreshing)
        {
            return;
        }

        _refreshing = true;
        _refreshButton.Enabled = false;
        _injectButton.Enabled = false;
        int? selectedPid = GetSelectedPid();
        try
        {
            DiscoveryResult result = await Task.Run(_processDiscovery.Discover);
            int? preservedPid = SelectionPreserver.Preserve(selectedPid, result.Clients);
            ReplaceRows(result.Clients, preservedPid);

            if (_managedInjectedPid is not null && result.Clients.All(client => client.Pid != _managedInjectedPid.Value))
            {
                AppendOutput($"Managed client PID {_managedInjectedPid.Value} is no longer running.");
                _managedInjectedPid = null;
                _managedClientLabel.Text = "No managed client";
            }

            StatusPresentation presentation = _managedInjectedPid is not null
                ? new(LauncherState.Injected, $"Injected - actively managing PID {_managedInjectedPid.Value}.")
                : StatusPresentation.ForDiscovery(result);
            SetStatus(presentation.State, presentation.Message);

            foreach (DiscoveryIssue issue in result.Issues.Where(issue => issue.Kind == DiscoveryIssueKind.AccessDenied))
            {
                AppendOutput($"[error] {issue.Message}");
            }
        }
        catch (Exception exception)
        {
            ShowFailure($"Refresh failed: {exception.Message}");
        }
        finally
        {
            _refreshing = false;
            _refreshButton.Enabled = !_busy;
            UpdateInjectEnabled();
        }
    }

    private void ReplaceRows(IReadOnlyList<GameClientInfo> clients, int? selectedPid)
    {
        _clientGrid.Rows.Clear();
        foreach (GameClientInfo client in clients)
        {
            int index = _clientGrid.Rows.Add(
                client.Pid,
                client.WindowTitle.Length == 0 ? "(no window title)" : client.WindowTitle,
                client.StartTime?.ToString("MMM dd  HH:mm") ?? "Unavailable",
                client.Responding is null ? "Unknown" : client.Responding.Value ? "Responsive" : "Not responding",
                client.ExecutablePath);
            _clientGrid.Rows[index].Tag = client;
        }

        _clientGrid.ClearSelection();
        if (selectedPid is not null)
        {
            DataGridViewRow? row = _clientGrid.Rows.Cast<DataGridViewRow>()
                .FirstOrDefault(candidate => candidate.Tag is GameClientInfo client && client.Pid == selectedPid.Value);
            if (row is not null)
            {
                row.Selected = true;
                _clientGrid.CurrentCell = row.Cells[0];
            }
        }
    }

    private async Task InjectSelectedAsync()
    {
        if (_busy)
        {
            return;
        }

        int? selectedPid = GetSelectedPid();
        if (selectedPid is null)
        {
            ShowFailure("Select exactly one valid game client before injecting.");
            return;
        }

        if (_paths is null)
        {
            ShowFailure("The repository root is unavailable; run the launcher from this checkout.");
            return;
        }

        IReadOnlyList<string> preflightErrors = _paths.ValidateForInjection();
        if (preflightErrors.Count > 0)
        {
            foreach (string error in preflightErrors) { AppendOutput($"[error] {error}"); }
            SetStatus(LauncherState.Failed, $"Failed - {preflightErrors[0]}");
            return;
        }

        if (!IsAdministrator())
        {
            ShowFailure("Administrator privileges are required. Restart this launcher as administrator.");
            return;
        }

        if (_managedInjectedPid is not null && _managedInjectedPid != selectedPid)
        {
            DialogResult answer = MessageBox.Show(
                this,
                $"PID {_managedInjectedPid.Value} is currently managed. Injecting PID {selectedPid.Value} will replace the shared active marker, and the previous client's snapshot feed may stop. Continue?",
                "Switch managed client",
                MessageBoxButtons.OKCancel,
                MessageBoxIcon.Warning);
            if (answer != DialogResult.OK)
            {
                return;
            }
        }

        SetBusy(true);
        SetStatus(LauncherState.Injecting, $"Injecting - revalidating PID {selectedPid.Value}.");
        AppendOutput($"Revalidating PID {selectedPid.Value} immediately before injection...");
        try
        {
            ProcessValidationResult validation = await Task.Run(() => _processDiscovery.ValidateForInjection(selectedPid.Value));
            if (!validation.IsValid)
            {
                ShowFailure(validation.Error ?? "Selected process validation failed.");
                return;
            }

            SetStatus(LauncherState.Injecting, $"Injecting - running run_client_feature.ps1 for PID {selectedPid.Value}.");
            AppendOutput($"Starting 64-bit PowerShell runner for PID {selectedPid.Value}.");
            ProcessStartInfo command = InjectionCommandBuilder.Build(_paths.Root, selectedPid.Value);
            _injectionCancellation = new CancellationTokenSource();
            IProgress<ProcessOutputLine> progress = new Progress<ProcessOutputLine>(
                line => AppendOutput(line.IsError ? $"[stderr] {line.Text}" : line.Text));
            ProcessExecutionResult result = await _processExecutor.RunAsync(
                command,
                progress.Report,
                TimeSpan.FromSeconds(60),
                _injectionCancellation.Token);

            StatusPresentation presentation = StatusPresentation.ForExecution(result);
            SetStatus(presentation.State, presentation.Message);
            AppendOutput(presentation.Message);
            if (presentation.State == LauncherState.Injected)
            {
                _managedInjectedPid = selectedPid.Value;
                _managedClientLabel.Text = $"Managing PID {_managedInjectedPid.Value}";
                AppendOutput("Important: switch Auto Reaction OFF in the v11 panel now. The general Stop button does not disable it.");
            }
        }
        catch (OperationCanceledException)
        {
            ShowFailure("Injection was cancelled.");
        }
        catch (Exception exception)
        {
            ShowFailure($"Injection failed: {exception.Message}");
        }
        finally
        {
            _injectionCancellation?.Dispose();
            _injectionCancellation = null;
            SetBusy(false);
        }
    }

    private int? GetSelectedPid()
    {
        if (_clientGrid.SelectedRows.Count != 1)
        {
            return null;
        }

        return (_clientGrid.SelectedRows[0].Tag as GameClientInfo)?.Pid;
    }

    private void SetBusy(bool busy)
    {
        _busy = busy;
        _clientGrid.Enabled = !busy;
        _refreshButton.Enabled = !busy && !_refreshing;
        UpdateInjectEnabled();
    }

    private void UpdateInjectEnabled()
    {
        _injectButton.Enabled = !_busy && !_refreshing && GetSelectedPid() is not null;
    }

    private void ShowFailure(string message)
    {
        SetStatus(LauncherState.Failed, $"Failed - {message}");
        AppendOutput($"[error] {message}");
    }

    private void SetStatus(LauncherState state, string message)
    {
        _stateLabel.Text = state.ToString().ToUpperInvariant();
        _statusDetailLabel.Text = message;
        (_stateLabel.ForeColor, _stateLabel.BackColor) = state switch
        {
            LauncherState.Ready => (Color.FromArgb(153, 175, 255), Color.FromArgb(35, 47, 82)),
            LauncherState.Injecting => (Color.FromArgb(255, 195, 116), Color.FromArgb(69, 49, 30)),
            LauncherState.Injected => (Color.FromArgb(90, 226, 180), Color.FromArgb(25, 62, 54)),
            _ => (Color.FromArgb(255, 139, 151), Color.FromArgb(70, 34, 45))
        };
    }

    private void AppendOutput(string line)
    {
        _output.SelectionStart = _output.TextLength;
        _output.SelectionColor = line.Contains("[error]", StringComparison.OrdinalIgnoreCase) ||
                                 line.Contains("[stderr]", StringComparison.OrdinalIgnoreCase)
            ? Color.FromArgb(255, 123, 137)
            : Color.FromArgb(194, 204, 220);
        _output.AppendText($"[{DateTime.Now:HH:mm:ss}] {line}{Environment.NewLine}");
        _output.SelectionStart = _output.TextLength;
        _output.ScrollToCaret();
    }

    private static bool IsAdministrator()
    {
        using WindowsIdentity identity = WindowsIdentity.GetCurrent();
        return new WindowsPrincipal(identity).IsInRole(WindowsBuiltInRole.Administrator);
    }
}
