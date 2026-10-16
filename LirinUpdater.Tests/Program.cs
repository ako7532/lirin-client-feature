using System.IO.Compression;
using System.Net;
using System.Text;
using System.Text.Json;
using LirinUpdater;

if (args.Length == 2 && args[0] == "--validate-package")
{
    string root = Path.GetFullPath(args[1]);
    var manifest = Package.Read<ReleaseManifest>(Path.Combine(root, "update-manifest.json"));
    using var temp = new Temp();
    Package.Extract(Path.Combine(root, "release.zip"), Path.Combine(temp.Root, "extracted"), manifest);
    Console.WriteLine("PASS real release archive and full identity validation"); return;
}

var tests = new (string, Func<Task>)[] {
    ("package identity, versions, malformed and unsupported metadata", Metadata),
    ("archive traversal, extras, duplicates, symlinks, size and checksum", Archives),
    ("complete apply, removed files and preserved user state", Apply),
    ("every partial replacement interruption recovers entire package", Interruptions),
    ("locked destination and tampered staging fail safely", Locked),
    ("concurrency lock and development/unknown install guards", Guards),
    ("HTTP errors, timeout, redirect credential isolation", Http),
    ("device pending, slow_down, denial, expiry, cancellation, disconnect", Auth),
    ("release ordering, drafts, incomplete releases and downgrade rejection", Releases),
    ("download cancellation and truncation", Downloads)
};
int failures = 0;
foreach (var (name, test) in tests)
{
    try { await test(); Console.WriteLine("PASS " + name); }
    catch (Exception e) { failures++; Console.WriteLine("FAIL " + name + "\n" + e); }
}
Console.WriteLine($"{tests.Length - failures}/{tests.Length} groups passed");
Environment.ExitCode = failures == 0 ? 0 : 1;

static void Check(bool value, string message = "Assertion failed") { if (!value) throw new Exception(message); }
static void Reject(Action action) { try { action(); } catch (Exception) { return; } throw new Exception("Expected rejection"); }
static async Task RejectAsync(Func<Task> action) { try { await action(); } catch (Exception) { return; } throw new Exception("Expected rejection"); }
static BuildIdentity Identity(long sequence = 1) => new(1, sequence, new string('a', 40), "stable", 1);
static PackageMetadata Fixture(string root, long sequence, bool optional = false)
{
    Directory.CreateDirectory(root);
    foreach (string name in Package.Required) File.WriteAllText(Path.Combine(root, name), name + sequence);
    Package.Write(Path.Combine(root, "build.json"), Identity(sequence));
    File.WriteAllText(Path.Combine(root, "distribution.json"), "\"lirin-private-package-v1\"");
    if (optional) File.WriteAllText(Path.Combine(root, "yin_yang_duel_model.json"), "{}");
    var files = Directory.GetFiles(root).Select(p => new PackageFile(Path.GetFileName(p), new FileInfo(p).Length, Package.Hash(p))).OrderBy(f => f.Path).ToArray();
    var metadata = new PackageMetadata(Identity(sequence), files); Package.Write(Path.Combine(root, Package.MetadataName), metadata); return metadata;
}
static ReleaseManifest Zip(string root, string archive, PackageMetadata metadata, Action<ZipArchive>? mutate = null)
{
    ZipFile.CreateFromDirectory(root, archive);
    if (mutate != null) { using var zip = ZipFile.Open(archive, ZipArchiveMode.Update); mutate(zip); }
    return new(metadata.Build, new FileInfo(archive).Length, Package.Hash(archive), metadata.Files);
}
static Task Metadata()
{
    using var temp = new Temp(); var m = Fixture(temp.Child("package"), 1);
    Package.ValidateDirectory(temp.Child("package"), m);
    Reject(() => (m.Build with { Channel = "beta" }).Validate());
    Reject(() => (m.Build with { PackageFormat = 2 }).Validate());
    Reject(() => (m.Build with { Commit = "bad" }).Validate());
    Reject(() => Package.ValidateFiles(m.Files[..^1]));
    Reject(() => Package.ValidateFiles([..m.Files, m.Files[0]]));
    Reject(() => Package.ValidateManifest(new(m.Build, Package.MaxArchive + 1, new string('a', 64), m.Files)));
    foreach (string path in new[] { "../evil", "C:\\evil", "/evil", "CON", "x:stream", "client_feature.py.", "logs.txt", ".runtime" }) Reject(() => Package.ValidateName(path));
    return Task.CompletedTask;
}
static Task Archives()
{
    using var temp = new Temp(); string root = temp.Child("package"); var m = Fixture(root, 1);
    var good = Zip(root, temp.Child("good.zip"), m); Package.Extract(temp.Child("good.zip"), temp.Child("ok"), good);
    Reject(() => Package.Extract(temp.Child("good.zip"), temp.Child("hash"), good with { ArchiveSha256 = new string('0', 64) }));
    Reject(() => Package.Extract(temp.Child("good.zip"), temp.Child("length"), good with { ArchiveSize = good.ArchiveSize + 1 }));
    Reject(() => Package.Extract(temp.Child("good.zip"), temp.Child("identity"), good with { Build = Identity(2) }));
    int index = 0;
    foreach (var mutation in new Action<ZipArchive>[] {
        z => { z.GetEntry("inject.py")!.Delete(); z.CreateEntry("../inject.py"); },
        z => z.CreateEntry("unexpected.txt"),
        z => { z.GetEntry("inject.py")!.Delete(); z.CreateEntry("client_feature.py"); },
        z => z.GetEntry("inject.py")!.ExternalAttributes = unchecked((int)0xA1FF0000),
        z => { z.GetEntry("inject.py")!.Delete(); using var w = new StreamWriter(z.CreateEntry("inject.py").Open()); w.Write(new string('x', 1000)); }
    })
    { string archive = temp.Child($"bad{index}.zip"); var manifest = Zip(root, archive, m, mutation); string output = temp.Child($"bad{index++}"); Reject(() => Package.Extract(archive, output, manifest)); }
    return Task.CompletedTask;
}
static Task Apply()
{
    using var temp = new Temp(); string root = temp.Child("installed"), stage = temp.Child("stage");
    Fixture(root, 1, true); var incoming = Fixture(stage, 2);
    File.WriteAllText(Path.Combine(root, "user.log"), "preserve");
    Installation.Apply(root, stage, incoming); Installation.Confirm(root);
    Package.ValidateDirectory(root, incoming);
    Check(File.ReadAllText(Path.Combine(root, "user.log")) == "preserve");
    Check(!File.Exists(Path.Combine(root, "yin_yang_duel_model.json")));
    Reject(() => Installation.Apply(root, stage, incoming));
    return Task.CompletedTask;
}
static Task Interruptions()
{
    for (int failAt = 1; failAt <= Package.Required.Length + 2; failAt++)
    {
        using var temp = new Temp(); string root = temp.Child("root"), stage = temp.Child("stage");
        var old = Fixture(root, 1, true); var incoming = Fixture(stage, 2);
        File.WriteAllText(Path.Combine(root, "settings.txt"), "keep");
        int failure = failAt;
        Reject(() => Installation.Apply(root, stage, incoming, n => { if (n == failure) throw new IOException("Simulated interruption"); }));
        Check(Installation.Pending(root) != null); Installation.Rollback(root); Installation.Rollback(root);
        Package.ValidateDirectory(root, old); Check(File.ReadAllText(Path.Combine(root, "settings.txt")) == "keep");
    }
    // Restart failure after a fully applied package still rolls back all files.
    using (var temp = new Temp())
    { var old = Fixture(temp.Child("root"), 1); var next = Fixture(temp.Child("stage"), 2); Installation.Apply(temp.Child("root"), temp.Child("stage"), next); Installation.Rollback(temp.Child("root")); Package.ValidateDirectory(temp.Child("root"), old); }
    return Task.CompletedTask;
}
static Task Locked()
{
    using var temp = new Temp(); string root = temp.Child("root"), stage = temp.Child("stage");
    var old = Fixture(root, 1); var next = Fixture(stage, 2);
    using (var locked = new FileStream(Path.Combine(root, "inject.py"), FileMode.Open, FileAccess.Read, FileShare.Read))
        Reject(() => Installation.Apply(root, stage, next));
    Installation.Rollback(root); Package.ValidateDirectory(root, old);
    string denied = Path.Combine(root, "inject.py");
    File.SetAttributes(denied, FileAttributes.ReadOnly);
    try { Reject(() => Installation.Apply(root, stage, next)); }
    finally { File.SetAttributes(denied, FileAttributes.Normal); }
    Installation.Rollback(root); Package.ValidateDirectory(root, old);
    File.AppendAllText(Path.Combine(stage, "inject.py"), "tampered");
    Reject(() => Installation.Apply(root, stage, next)); Package.ValidateDirectory(root, old);
    return Task.CompletedTask;
}
static Task Guards()
{
    using var temp = new Temp();
    using (var operation = Installation.Lock(temp.Root)) Reject(() => { using var other = Installation.Lock(temp.Root); });
    // Portable installs: any folder with the distribution marker is accepted, even outside Program Files.
    Reject(() => SafePaths.Installation(temp.Child("nomarker")));
    var portable = temp.Child("portable"); Fixture(portable, 1);
    SafePaths.Installation(portable); // must not throw
    // A Git checkout is still refused regardless of location.
    var repo = temp.Child("repo"); Fixture(repo, 1); File.WriteAllText(Path.Combine(repo, ".git"), "gitdir: elsewhere");
    Reject(() => SafePaths.Installation(repo));
    return Task.CompletedTask;
}
static HttpResponseMessage Response(string json, HttpStatusCode status = HttpStatusCode.OK) => new(status) { Content = new StringContent(json) };
static async Task Http()
{
    foreach (var (status, expected) in new[] { (401, UpdateFailure.Authentication), (403, UpdateFailure.Access), (404, UpdateFailure.Access), (429, UpdateFailure.RateLimit), (500, UpdateFailure.Network) })
    {
        using var transport = new GitHubTransport(new Fake((_, _) => Task.FromResult(Response("{}", (HttpStatusCode)status))));
        try { await new GitHubReleaseClient(transport).ValidateAccess("private-token", default); throw new Exception("Expected error"); }
        catch (UpdateException e) { Check(e.Kind == expected); }
    }
    int requests = 0;
    using (var transport = new GitHubTransport(new Fake((r, _) =>
    {
        requests++;
        if (requests == 1) { Check(r.Headers.Authorization?.Parameter == "private-token"); var result = Response("", HttpStatusCode.Found); result.Headers.Location = new Uri("https://release-assets.githubusercontent.com/asset"); return Task.FromResult(result); }
        Check(r.Headers.Authorization == null, "Credential leaked to redirect"); return Task.FromResult(Response("abc"));
    }))) Check(Encoding.UTF8.GetString(await transport.GetAsset(1, "private-token", 10, default)) == "abc");
    foreach (string destination in new[] { "http://release-assets.githubusercontent.com/asset", "https://evil.example/asset", "https://api.github.com:444/asset" })
    {
        using var transport = new GitHubTransport(new Fake((_, _) => { var r = Response("", HttpStatusCode.Found); r.Headers.Location = new Uri(destination); return Task.FromResult(r); }));
        await RejectAsync(() => transport.GetAsset(1, "token", 100, default));
    }
    using (var transport = new GitHubTransport(new Fake((_, _) => throw new HttpRequestException("offline"))))
        await RejectAsync(() => new GitHubReleaseClient(transport).ValidateAccess("token", default));
    using (var transport = new GitHubTransport(new Fake((_, _) => throw new TaskCanceledException())))
    {
        try { await new GitHubReleaseClient(transport).ValidateAccess("token", default); throw new Exception("Expected timeout"); }
        catch (UpdateException e) { Check(e.Kind == UpdateFailure.Timeout); }
    }
    using (var transport = new GitHubTransport(new Fake((_, _) =>
    {
        var response = Response("{}", HttpStatusCode.Forbidden);
        response.Headers.Add("Retry-After", "7200"); return Task.FromResult(response);
    })))
    {
        try { await new GitHubReleaseClient(transport).ValidateAccess("t", default); throw new Exception("Expected limit"); }
        catch (UpdateException e) { Check(e.Kind == UpdateFailure.RateLimit && e.RetryAt > DateTimeOffset.UtcNow.AddMinutes(119)); }
    }
}
static async Task Auth()
{
    var store = new MemoryCredentials(); int polls = 0; var intervals = new List<double>();
    using (var transport = new GitHubTransport(new Fake((r, _) => Task.FromResult(Response(
        r.RequestUri!.AbsolutePath == "/login/device/code" ? "{\"device_code\":\"device\",\"user_code\":\"ABCD-EFGH\",\"expires_in\":900,\"interval\":5}" :
        r.RequestUri.AbsolutePath == "/login/oauth/access_token" ? ++polls switch {
            1 => "{\"error\":\"authorization_pending\"}", 2 => "{\"error\":\"slow_down\"}", _ => "{\"access_token\":\"private-token\",\"expires_in\":28800}" } : "{}")))))
    {
        var auth = new GitHubAuthService(transport, store, (t, ct) => { intervals.Add(t.TotalSeconds); return Task.CompletedTask; });
        await auth.Connect("client", _ => { }, default); Check(store.Value?.Token == "private-token"); Check(intervals.SequenceEqual(new double[] { 5, 5, 10 }));
        auth.Disconnect(); Check(auth.Current() == null);
        store.Value = new("expired", DateTimeOffset.UtcNow.AddSeconds(-1)); Check(auth.Current() == null && store.Value == null);
    }
    foreach (string error in new[] { "access_denied", "expired_token" })
    {
        using var transport = new GitHubTransport(new Fake((r, _) => Task.FromResult(Response(r.RequestUri!.AbsolutePath.EndsWith("device/code") ?
            "{\"device_code\":\"d\",\"user_code\":\"U\",\"expires_in\":900,\"interval\":5}" : "{\"error\":\"" + error + "\"}"))));
        await RejectAsync(() => new GitHubAuthService(transport, store, (_, _) => Task.CompletedTask).Connect("client", _ => { }, default));
        Check(store.Value == null);
    }
    using (var cancel = new CancellationTokenSource())
    using (var transport = new GitHubTransport(new Fake((r, ct) => { ct.ThrowIfCancellationRequested(); return Task.FromResult(Response("{}")); })))
    { cancel.Cancel(); await RejectAsync(() => new GitHubAuthService(transport, store).Connect("client", _ => { }, cancel.Token)); }
}
static async Task Releases()
{
    using var temp = new Temp(); var m = Fixture(temp.Child("package"), 4); var manifest = Zip(temp.Child("package"), temp.Child("p.zip"), m);
    string release = JsonSerializer.Serialize(new { draft = false, prerelease = false, tag_name = $"stable-4-{m.Build.Commit}", body = "notes", assets = new[] {
        new { name = "update-manifest.json", id = 1, size = 100L, state = "uploaded" }, new { name = "release.zip", id = 2, size = manifest.ArchiveSize, state = "uploaded" } } });
    using var transport = new GitHubTransport(new Fake((r, _) => Task.FromResult(Response(r.RequestUri!.AbsolutePath.EndsWith("/assets/1") ? JsonSerializer.Serialize(manifest) : "[" + release + "]"))));
    var client = new GitHubReleaseClient(transport);
    Check((await client.Check(Identity(3), "token", default))?.Manifest.Build.Sequence == 4);
    Check(await client.Check(Identity(4), "token", default) == null);
    Check(await client.Check(Identity(5), "token", default) == null);
    Check(await client.Check(null, "token", default) != null);
    // The first listed release may be an old workflow rerun; choose by sequence.
    var newer = manifest with { Build = Identity(9) };
    string newerRelease = release.Replace("stable-4-", "stable-9-").Replace("\"id\":1,", "\"id\":3,");
    using (var unordered = new GitHubTransport(new Fake((r, _) => Task.FromResult(Response(
        r.RequestUri!.AbsolutePath.EndsWith("/assets/1") ? JsonSerializer.Serialize(manifest) :
        r.RequestUri.AbsolutePath.EndsWith("/assets/3") ? JsonSerializer.Serialize(newer) : "[" + release + "," + newerRelease + "]")))))
        Check((await new GitHubReleaseClient(unordered).Check(Identity(2), "t", default))?.Manifest.Build.Sequence == 9);
    using var draft = new GitHubTransport(new Fake((_, _) => Task.FromResult(Response("[" + release.Replace("\"draft\":false", "\"draft\":true") + "]"))));
    Check(await new GitHubReleaseClient(draft).Check(Identity(1), "t", default) == null);
    using var incomplete = new GitHubTransport(new Fake((_, _) => Task.FromResult(Response("[{\"draft\":false,\"prerelease\":false,\"tag_name\":\"stable-5-a\",\"assets\":[]}]"))));
    await RejectAsync(() => new GitHubReleaseClient(incomplete).Check(Identity(1), "t", default));
}
static async Task Downloads()
{
    using var transport = new GitHubTransport(new Fake((_, _) => Task.FromResult(Response("truncated"))));
    await RejectAsync(() => transport.GetAsset(1, "token", 2, default));
    using var cancelled = new CancellationTokenSource(); cancelled.Cancel();
    await RejectAsync(() => transport.GetAsset(1, "token", 100, cancelled.Token));
    using var temp = new Temp(); var metadata = Fixture(temp.Child("package"), 1); var manifest = Zip(temp.Child("package"), temp.Child("p.zip"), metadata);
    File.WriteAllText(temp.Child("short.zip"), "truncated"); Reject(() => Package.Extract(temp.Child("short.zip"), temp.Child("out"), manifest));
}

sealed class Fake(Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>> respond) : HttpMessageHandler
{ protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken ct) => respond(request, ct); }
sealed class MemoryCredentials : ICredentialStore
{ public Credential? Value; public Credential? Read() => Value; public void Save(Credential credential) => Value = credential; public void Delete() => Value = null; }
sealed class Temp : IDisposable
{
    public string Root { get; } = Path.Combine(Environment.GetEnvironmentVariable("LIRIN_UPDATER_TEST_ROOT") ?? Path.GetTempPath(), "lirin-updater-test-" + Guid.NewGuid().ToString("N"));
    public Temp() => Directory.CreateDirectory(Root);
    public string Child(string name) => Path.Combine(Root, name);
    public void Dispose() { if (Directory.Exists(Root)) Directory.Delete(Root, true); }
}
