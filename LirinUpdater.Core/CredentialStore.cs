using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;

namespace LirinUpdater;

// Windows Credential Manager encrypts this generic credential for the current Windows identity.
public sealed class CredentialStore : ICredentialStore
{
    private const string Target = "LirinFeatureLauncher/GitHub/ako7532/lirin-client-feature/v1";
    public Credential? Read()
    {
        if (!CredRead(Target, 1, 0, out var pointer))
        { if (Marshal.GetLastWin32Error() == 1168) return null; throw new Win32Exception(Marshal.GetLastWin32Error()); }
        try
        {
            var native = Marshal.PtrToStructure<NativeCredential>(pointer);
            byte[] bytes = new byte[native.Size]; Marshal.Copy(native.Blob, bytes, 0, bytes.Length);
            try { return JsonSerializer.Deserialize<Credential>(bytes); }
            catch (JsonException) { Delete(); return null; }
            finally { Array.Clear(bytes); }
        }
        finally { CredFree(pointer); }
    }
    public void Save(Credential credential)
    {
        byte[] bytes = Encoding.UTF8.GetBytes(JsonSerializer.Serialize(credential));
        IntPtr blob = Marshal.AllocHGlobal(bytes.Length);
        try
        {
            Marshal.Copy(bytes, 0, blob, bytes.Length);
            var native = new NativeCredential { Type = 1, TargetName = Target, Size = (uint)bytes.Length, Blob = blob, Persist = 2, UserName = "GitHub user" };
            if (!CredWrite(ref native, 0)) throw new Win32Exception(Marshal.GetLastWin32Error());
        }
        finally { Array.Clear(bytes); Marshal.Copy(bytes, 0, blob, bytes.Length); Marshal.FreeHGlobal(blob); }
    }
    public void Delete()
    { if (!CredDelete(Target, 1, 0) && Marshal.GetLastWin32Error() != 1168) throw new Win32Exception(Marshal.GetLastWin32Error()); }
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct NativeCredential
    {
        public uint Flags, Type;
        public string? TargetName, Comment;
        public System.Runtime.InteropServices.ComTypes.FILETIME LastWritten;
        public uint Size;
        public IntPtr Blob;
        public uint Persist, AttributeCount;
        public IntPtr Attributes;
        public string? TargetAlias, UserName;
    }
    [DllImport("advapi32.dll", EntryPoint = "CredReadW", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool CredRead(string target, uint type, uint flags, out IntPtr credential);
    [DllImport("advapi32.dll", EntryPoint = "CredWriteW", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool CredWrite(ref NativeCredential credential, uint flags);
    [DllImport("advapi32.dll", EntryPoint = "CredDeleteW", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool CredDelete(string target, uint type, uint flags);
    [DllImport("advapi32.dll")] private static extern void CredFree(IntPtr pointer);
}
