using System.ComponentModel;
using System.Diagnostics;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

namespace LirinFeatureLauncher;

public sealed class ProcessDiscovery
{
    private const uint ProcessQueryLimitedInformation = 0x1000;
    private const ushort ImageFileMachineUnknown = 0x0000;
    private const ushort ImageFileMachineIa64 = 0x0200;
    private const ushort ImageFileMachineAmd64 = 0x8664;
    private const ushort ImageFileMachineArm64 = 0xaa64;

    public DiscoveryResult Discover()
    {
        List<ProcessSnapshot> snapshots = new();
        List<DiscoveryIssue> issues = new();

        foreach (Process process in Process.GetProcessesByName("Lirin"))
        {
            using (process)
            {
                int? pid = TryGetPid(process);
                try
                {
                    snapshots.Add(Inspect(process));
                }
                catch (Win32Exception exception) when (exception.NativeErrorCode == 5)
                {
                    issues.Add(new(pid, DiscoveryIssueKind.AccessDenied, $"Access denied for Lirin PID {pid?.ToString() ?? "unknown"}."));
                }
                catch (Exception exception) when (exception is ArgumentException or InvalidOperationException or Win32Exception)
                {
                    issues.Add(new(pid, DiscoveryIssueKind.Exited, $"Lirin PID {pid?.ToString() ?? "unknown"} exited during refresh: {exception.Message}"));
                }
            }
        }

        return new(ProcessFilter.ValidGameClients(snapshots), issues);
    }

    public ProcessValidationResult ValidateForInjection(int pid)
    {
        try
        {
            using Process process = Process.GetProcessById(pid);
            ProcessSnapshot snapshot = Inspect(process);
            GameClientInfo? client = ProcessFilter.ValidGameClients(new[] { snapshot }).SingleOrDefault();
            return client is null
                ? ProcessValidationResult.Invalid($"PID {pid} is not the exact 64-bit game executable {ProcessFilter.ExpectedGamePath}.")
                : ProcessValidationResult.Valid(client);
        }
        catch (Win32Exception exception) when (exception.NativeErrorCode == 5)
        {
            return ProcessValidationResult.Invalid($"Access denied while revalidating PID {pid}. Restart this launcher as administrator.");
        }
        catch (Exception exception) when (exception is ArgumentException or InvalidOperationException or Win32Exception)
        {
            return ProcessValidationResult.Invalid($"Selected client PID {pid} exited or became unavailable. Refresh the list. {exception.Message}");
        }
    }

    private static ProcessSnapshot Inspect(Process process)
    {
        int pid = process.Id;
        using SafeProcessHandle handle = OpenProcess(ProcessQueryLimitedInformation, false, pid);
        if (handle.IsInvalid)
        {
            throw new Win32Exception(Marshal.GetLastWin32Error(), "OpenProcess failed");
        }

        return new(
            pid,
            QueryImagePath(handle),
            Is64Bit(handle),
            TryRead(() => process.MainWindowTitle, string.Empty),
            TryRead<DateTime?>(() => process.StartTime, null),
            TryRead<bool?>(() => process.Responding, null));
    }

    private static string QueryImagePath(SafeProcessHandle process)
    {
        uint capacity = 32768;
        System.Text.StringBuilder buffer = new((int)capacity);
        if (!QueryFullProcessImageName(process, 0, buffer, ref capacity))
        {
            throw new Win32Exception(Marshal.GetLastWin32Error(), "QueryFullProcessImageNameW failed");
        }

        return buffer.ToString();
    }

    private static bool Is64Bit(SafeProcessHandle process)
    {
        try
        {
            if (!IsWow64Process2(process, out ushort processMachine, out ushort nativeMachine))
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "IsWow64Process2 failed");
            }

            ushort effectiveMachine = processMachine == ImageFileMachineUnknown ? nativeMachine : processMachine;
            return effectiveMachine is ImageFileMachineAmd64 or ImageFileMachineArm64 or ImageFileMachineIa64;
        }
        catch (EntryPointNotFoundException)
        {
            if (!IsWow64Process(process, out bool isWow64))
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "IsWow64Process failed");
            }

            return Environment.Is64BitOperatingSystem && !isWow64;
        }
    }

    private static int? TryGetPid(Process process)
    {
        try { return process.Id; }
        catch (InvalidOperationException) { return null; }
    }

    private static T TryRead<T>(Func<T> getter, T fallback)
    {
        try { return getter(); }
        catch (Exception exception) when (exception is InvalidOperationException or Win32Exception or NotSupportedException) { return fallback; }
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern SafeProcessHandle OpenProcess(uint desiredAccess, bool inheritHandle, int processId);

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool QueryFullProcessImageName(SafeProcessHandle process, uint flags, System.Text.StringBuilder executableName, ref uint size);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool IsWow64Process2(SafeProcessHandle process, out ushort processMachine, out ushort nativeMachine);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool IsWow64Process(SafeProcessHandle process, out bool wow64Process);
}
