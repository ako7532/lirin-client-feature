using System.IO.Compression;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace LirinUpdater;

public sealed record BuildIdentity(int Schema, long Sequence, string Commit, string Channel, int PackageFormat)
{
    public void Validate()
    {
        if (Schema != 1 || PackageFormat != 1 || Sequence <= 0 || Channel != "stable" ||
            !Regex.IsMatch(Commit ?? "", "^[a-f0-9]{40}$"))
            throw new InvalidDataException("Unsupported or malformed build identity.");
    }
    public override string ToString() => $"{Channel} #{Sequence} ({Commit[..8]})";
}
public sealed record PackageFile(string Path, long Size, string Sha256);
public sealed record PackageMetadata(BuildIdentity Build, PackageFile[] Files);
public sealed record ReleaseManifest(BuildIdentity Build, long ArchiveSize, string ArchiveSha256, PackageFile[] Files);
public sealed record UpdaterConfig(string ClientId);

public static class Package
{
    public const long MaxArchive = 256 * 1024 * 1024;
    public const long MaxExpanded = 512 * 1024 * 1024;
    public const string MetadataName = "package.json";
    public static readonly JsonSerializerOptions Json = new() { PropertyNameCaseInsensitive = true, WriteIndented = true };
    public static readonly string[] Required = ["LirinFeatureLauncher.exe", "LirinFeatureLauncher.dll", "LirinFeatureLauncher.deps.json",
        "LirinFeatureLauncher.runtimeconfig.json", "LirinUpdater.Core.dll", "LirinUpdater.Helper.exe", "LirinUpdater.Helper.dll",
        "LirinUpdater.Helper.deps.json", "LirinUpdater.Helper.runtimeconfig.json", "client_feature_loader.dll", "client_feature.py",
        "inject.py", "run_client_feature.ps1", "build.json", "distribution.json", "updater.json"];
    public static T Read<T>(string path) => JsonSerializer.Deserialize<T>(File.ReadAllText(path), Json)
        ?? throw new InvalidDataException("Missing metadata.");
    public static void Write<T>(string path, T value)
    {
        // Flush before atomic rename: journals never expose a half-written JSON document.
        string temp = path + ".new";
        using (var stream = new FileStream(temp, FileMode.Create, FileAccess.Write, FileShare.None))
        { JsonSerializer.Serialize(stream, value, Json); stream.Flush(true); }
        File.Move(temp, path, true);
    }
    public static string Hash(string path)
    { using var stream = File.OpenRead(path); return Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant(); }
    public static void ValidateFiles(PackageFile[] files)
    {
        if (files is null || files.Length > 128) throw new InvalidDataException("Invalid file list.");
        var names = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        long size = 0;
        foreach (var file in files)
        {
            ValidateName(file.Path);
            if (!names.Add(file.Path) || file.Path.Equals(MetadataName, StringComparison.OrdinalIgnoreCase) ||
                file.Size < 0 || file.Size > MaxExpanded || !Regex.IsMatch(file.Sha256 ?? "", "^[a-f0-9]{64}$"))
                throw new InvalidDataException("Invalid or duplicate managed file.");
            size = checked(size + file.Size);
        }
        if (size > MaxExpanded || Required.Any(name => !names.Contains(name))) throw new InvalidDataException("Incomplete or oversized package.");
    }
    public static void ValidateName(string name)
    {
        // Format 1 is deliberately flat. No directories, ADS, devices, aliases, settings or runtime files.
        if (string.IsNullOrEmpty(name) || !Regex.IsMatch(name, "^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}$") ||
            name.EndsWith('.') || Regex.IsMatch(name, "^(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])($|\\.)", RegexOptions.IgnoreCase) ||
            !(Required.Contains(name, StringComparer.OrdinalIgnoreCase) || name == MetadataName ||
              name == "yin_yang_duel_model.json" || Regex.IsMatch(name, "^Lirin(FeatureLauncher|Updater\\.(Core|Helper))\\.pdb$")))
            throw new InvalidDataException("Unexpected package path.");
    }
    public static void ValidateManifest(ReleaseManifest manifest)
    {
        manifest.Build.Validate(); ValidateFiles(manifest.Files);
        if (manifest.ArchiveSize <= 0 || manifest.ArchiveSize > MaxArchive ||
            !Regex.IsMatch(manifest.ArchiveSha256 ?? "", "^[a-f0-9]{64}$")) throw new InvalidDataException("Invalid archive manifest.");
    }
    public static void ValidateDirectory(string root, PackageMetadata metadata)
    {
        metadata.Build.Validate(); ValidateFiles(metadata.Files);
        foreach (var file in metadata.Files)
        {
            string path = Path.Combine(root, file.Path); SafePaths.NoReparse(path);
            if (!File.Exists(path) || new FileInfo(path).Length != file.Size || Hash(path) != file.Sha256)
                throw new InvalidDataException($"Package file failed validation: {file.Path}");
        }
        if (Read<BuildIdentity>(Path.Combine(root, "build.json")) != metadata.Build ||
            File.ReadAllText(Path.Combine(root, "distribution.json")).Trim() != "\"lirin-private-package-v1\"")
            throw new InvalidDataException("Installed build/distribution identity mismatch.");
    }
    public static PackageMetadata Extract(string archive, string destination, ReleaseManifest manifest, CancellationToken ct = default)
    {
        ValidateManifest(manifest); SafePaths.NoReparse(archive); SafePaths.NoReparse(destination);
        using var source = new FileStream(archive, FileMode.Open, FileAccess.Read, FileShare.Read);
        if (source.Length != manifest.ArchiveSize || Convert.ToHexString(SHA256.HashData(source)).ToLowerInvariant() != manifest.ArchiveSha256)
            throw new InvalidDataException("Archive size/checksum mismatch.");
        source.Position = 0;
        if (Directory.Exists(destination)) throw new IOException("Staging destination already exists.");
        Directory.CreateDirectory(destination);
        using var zip = new ZipArchive(source, ZipArchiveMode.Read);
        var expected = manifest.Files.ToDictionary(f => f.Path, StringComparer.OrdinalIgnoreCase);
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        if (zip.Entries.Count != expected.Count + 1) throw new InvalidDataException("Unexpected archive contents.");
        foreach (var entry in zip.Entries)
        {
            ct.ThrowIfCancellationRequested(); ValidateName(entry.FullName);
            if (!seen.Add(entry.FullName) || (entry.ExternalAttributes & 0x400) != 0 ||
                ((entry.ExternalAttributes >> 16) & 0xF000) is 0xA000 or 0x4000)
                throw new InvalidDataException("Archive links/directories/duplicates are forbidden.");
            long limit = entry.FullName == MetadataName ? 128 * 1024 :
                expected.TryGetValue(entry.FullName, out var file) ? file.Size : throw new InvalidDataException("Unexpected file.");
            if (entry.Length > limit) throw new InvalidDataException("Oversized entry.");
            using var input = entry.Open();
            using var output = new FileStream(Path.Combine(destination, entry.FullName), FileMode.CreateNew);
            byte[] buffer = new byte[81920]; long count = 0; int read;
            while ((read = input.Read(buffer)) > 0)
            { ct.ThrowIfCancellationRequested(); count += read; if (count > limit) throw new InvalidDataException("Oversized extraction."); output.Write(buffer, 0, read); }
            output.Flush(true);
        }
        var metadata = Read<PackageMetadata>(Path.Combine(destination, MetadataName));
        if (metadata.Build != manifest.Build || !metadata.Files.SequenceEqual(manifest.Files)) throw new InvalidDataException("Manifest/package identity mismatch.");
        ValidateDirectory(destination, metadata);
        return metadata;
    }
}
