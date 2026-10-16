using System.Net;
using System.Net.Http.Headers;
using System.Text.Json;

namespace LirinUpdater;

public enum UpdateFailure { Network, Timeout, Authentication, Access, RateLimit, Metadata }
public sealed class UpdateException(UpdateFailure kind, string message) : Exception(message)
{ public UpdateFailure Kind { get; } = kind; public DateTimeOffset? RetryAt { get; init; } }
public sealed record Credential(string Token, DateTimeOffset? Expires);
public interface ICredentialStore { Credential? Read(); void Save(Credential credential); void Delete(); }
public sealed record DeviceCode(string Code, string UserCode, int ExpiresIn, int Interval);
public sealed record ReleaseCandidate(ReleaseManifest Manifest, long AssetId, string Notes);

public sealed class GitHubTransport : IDisposable
{
    private readonly HttpClient client;
    public GitHubTransport(HttpMessageHandler? handler = null)
    {
        client = new HttpClient(handler ?? new HttpClientHandler { AllowAutoRedirect = false }) { Timeout = TimeSpan.FromSeconds(30) };
        client.DefaultRequestHeaders.UserAgent.ParseAdd("LirinFeatureLauncher/1.0");
    }
    public async Task<HttpResponseMessage> Send(HttpRequestMessage request, CancellationToken ct)
    {
        try
        {
            var response = await client.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, ct);
            if (response.StatusCode == HttpStatusCode.Unauthorized) { response.Dispose(); throw new UpdateException(UpdateFailure.Authentication, "GitHub authorization expired or was revoked. Reconnect GitHub."); }
            if ((int)response.StatusCode is 403 or 429)
            {
                bool limited = (int)response.StatusCode == 429 || response.Headers.Contains("Retry-After") ||
                    (response.Headers.TryGetValues("X-RateLimit-Remaining", out var remaining) && remaining.Contains("0"));
                DateTimeOffset retry = DateTimeOffset.UtcNow.AddHours(1);
                var retryHeader = response.Headers.RetryAfter;
                DateTimeOffset? requested = retryHeader?.Date ?? (retryHeader?.Delta is { } delta ? DateTimeOffset.UtcNow + delta : null);
                if (requested > retry) retry = requested.Value;
                if (response.Headers.TryGetValues("X-RateLimit-Reset", out var resets) && long.TryParse(resets.FirstOrDefault(), out long epoch) &&
                    epoch > retry.ToUnixTimeSeconds() && epoch < 253402300799) retry = DateTimeOffset.FromUnixTimeSeconds(epoch);
                response.Dispose();
                throw new UpdateException(limited ? UpdateFailure.RateLimit : UpdateFailure.Access,
                    limited ? "GitHub rate limit reached. Try again later." : "GitHub denied access. Check the app installation and your repository permissions.") { RetryAt = retry };
            }
            if (response.StatusCode == HttpStatusCode.NotFound) { response.Dispose(); throw new UpdateException(UpdateFailure.Access, "Private resource unavailable (404). Check repository/app access; it may be hidden from this account."); }
            if (!response.IsSuccessStatusCode && (int)response.StatusCode is not (301 or 302 or 303 or 307 or 308))
            { response.Dispose(); throw new UpdateException(UpdateFailure.Network, "GitHub request failed. Try again later."); }
            return response;
        }
        catch (HttpRequestException) { throw new UpdateException(UpdateFailure.Network, "Network unavailable. The installed launcher remains usable."); }
        catch (OperationCanceledException) when (!ct.IsCancellationRequested) { throw new UpdateException(UpdateFailure.Timeout, "GitHub request timed out."); }
    }
    public async Task<byte[]> GetAsset(long id, string token, long max, CancellationToken ct, Stream? destination = null, IProgress<long>? progress = null)
    {
        if (id <= 0) throw new InvalidDataException("Invalid asset ID.");
        Uri uri = new($"https://api.github.com/repos/{GitHubReleaseClient.Repository}/releases/assets/{id}");
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(ct); timeout.CancelAfter(TimeSpan.FromMinutes(5));
        for (int redirects = 0; redirects < 4; redirects++)
        {
            if (uri.Scheme != "https" || uri.Port != 443 || uri.UserInfo.Length != 0 ||
                !(uri.Host == "api.github.com" || uri.Host == "release-assets.githubusercontent.com" || uri.Host == "objects.githubusercontent.com"))
                throw new InvalidDataException("Untrusted asset redirect.");
            using var request = new HttpRequestMessage(HttpMethod.Get, uri);
            request.Headers.Accept.ParseAdd("application/octet-stream");
            // Authorization is attached only to the initial, fixed API endpoint; never to a redirect.
            if (redirects == 0) request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
            using var response = await Send(request, timeout.Token);
            if ((int)response.StatusCode is 301 or 302 or 303 or 307 or 308)
            { uri = response.Headers.Location is { } location ? new Uri(uri, location) : throw new InvalidDataException("Missing redirect destination."); continue; }
            if (response.Content.Headers.ContentLength > max) throw new InvalidDataException("Oversized download.");
            using var memory = new MemoryStream(); Stream output = destination ?? memory;
            using var input = await response.Content.ReadAsStreamAsync(timeout.Token);
            byte[] buffer = new byte[81920]; long total = 0; int read;
            while ((read = await input.ReadAsync(buffer, timeout.Token)) > 0)
            { total += read; if (total > max) throw new InvalidDataException("Oversized download."); await output.WriteAsync(buffer.AsMemory(0, read), timeout.Token); progress?.Report(total); }
            return destination is null ? memory.ToArray() : [];
        }
        throw new InvalidDataException("Too many asset redirects.");
    }
    public static async Task<JsonDocument> Json(HttpResponseMessage response, CancellationToken ct)
    {
        if (!response.IsSuccessStatusCode) throw new InvalidDataException("Unexpected API redirect.");
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(ct); timeout.CancelAfter(TimeSpan.FromSeconds(30));
        using var stream = await response.Content.ReadAsStreamAsync(timeout.Token);
        using var data = new MemoryStream(); byte[] buffer = new byte[8192]; int read;
        while ((read = await stream.ReadAsync(buffer, timeout.Token)) > 0)
        { if (data.Length + read > 2 * 1024 * 1024) throw new InvalidDataException("Oversized API metadata."); data.Write(buffer, 0, read); }
        return JsonDocument.Parse(data.ToArray());
    }
    public void Dispose() => client.Dispose();
}

public sealed class GitHubAuthService(GitHubTransport transport, ICredentialStore store,
    Func<TimeSpan, CancellationToken, Task>? delay = null)
{
    private readonly Func<TimeSpan, CancellationToken, Task> wait = delay ?? Task.Delay;
    private async Task<JsonDocument> Post(string endpoint, Dictionary<string, string> values, CancellationToken ct)
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, "https://github.com/login/" + endpoint) { Content = new FormUrlEncodedContent(values) };
        request.Headers.Accept.ParseAdd("application/json");
        using var response = await transport.Send(request, ct); return await GitHubTransport.Json(response, ct);
    }
    public Credential? Current()
    {
        var credential = store.Read();
        if (credential?.Expires <= DateTimeOffset.UtcNow) { store.Delete(); return null; }
        return credential;
    }
    public void Disconnect() => store.Delete();
    public async Task Connect(string clientId, Action<DeviceCode> display, CancellationToken ct)
    {
        if (string.IsNullOrWhiteSpace(clientId)) throw new InvalidOperationException("GitHub App is not configured. See docs/LAUNCHER_UPDATER.md.");
        using var response = await Post("device/code", new() { ["client_id"] = clientId }, ct);
        var json = response.RootElement;
        var code = new DeviceCode(json.GetProperty("device_code").GetString()!, json.GetProperty("user_code").GetString()!,
            json.GetProperty("expires_in").GetInt32(), json.GetProperty("interval").GetInt32());
        if (code.ExpiresIn is <= 0 or > 1800 || code.Interval is <= 0 or > 300) throw new InvalidDataException("Invalid device authorization lifetime.");
        display(code);
        var deadline = DateTimeOffset.UtcNow.AddSeconds(code.ExpiresIn); int interval = code.Interval;
        using var expiry = CancellationTokenSource.CreateLinkedTokenSource(ct); expiry.CancelAfter(TimeSpan.FromSeconds(code.ExpiresIn));
        try
        {
            while (DateTimeOffset.UtcNow < deadline)
            {
                await wait(TimeSpan.FromSeconds(interval), expiry.Token);
                using var poll = await Post("oauth/access_token", new() { ["client_id"] = clientId, ["device_code"] = code.Code,
                    ["grant_type"] = "urn:ietf:params:oauth:grant-type:device_code" }, expiry.Token);
                var item = poll.RootElement;
                if (item.TryGetProperty("access_token", out var token))
                {
                    var value = token.GetString(); if (string.IsNullOrWhiteSpace(value)) throw new InvalidDataException("Empty authorization.");
                    // Validate private repository access before persisting any credential. No refresh secret is shipped.
                    await new GitHubReleaseClient(transport).ValidateAccess(value, expiry.Token);
                    store.Save(new(value, item.TryGetProperty("expires_in", out var seconds) ? DateTimeOffset.UtcNow.AddSeconds(seconds.GetInt32()) : null));
                    return;
                }
                string error = item.GetProperty("error").GetString()!;
                if (error == "authorization_pending") continue;
                if (error == "slow_down") { interval += 5; continue; }
                throw new UpdateException(UpdateFailure.Authentication, error switch {
                    "access_denied" => "GitHub authorization was denied.", "expired_token" => "Device code expired. Connect again.",
                    _ => "GitHub device authorization failed. Check app configuration and reconnect." });
            }
        }
        catch (OperationCanceledException) when (!ct.IsCancellationRequested) { throw new UpdateException(UpdateFailure.Authentication, "Device code expired. Connect again."); }
        throw new UpdateException(UpdateFailure.Authentication, "Device code expired. Connect again.");
    }
}

public sealed class GitHubReleaseClient(GitHubTransport transport)
{
    public const string Repository = "ako7532/lirin-client-feature";
    private async Task<JsonDocument> Get(string path, string token, CancellationToken ct)
    {
        using var request = new HttpRequestMessage(HttpMethod.Get, $"https://api.github.com/repos/{Repository}{path}");
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
        request.Headers.Accept.ParseAdd("application/vnd.github+json"); request.Headers.Add("X-GitHub-Api-Version", "2022-11-28");
        using var response = await transport.Send(request, ct); return await GitHubTransport.Json(response, ct);
    }
    public async Task ValidateAccess(string token, CancellationToken ct) { using var result = await Get("", token, ct); }
    public async Task<ReleaseCandidate?> Check(BuildIdentity? installed, string token, CancellationToken ct)
    {
        ReleaseCandidate? best = null; bool malformed = false;
        // Bounded pagination; publication order is never used for comparison.
        for (int page = 1; page <= 10; page++)
        {
            using var response = await Get($"/releases?per_page=100&page={page}", token, ct);
            var releases = response.RootElement;
            foreach (var release in releases.EnumerateArray())
            {
                if (release.GetProperty("draft").GetBoolean() || release.GetProperty("prerelease").GetBoolean()) continue;
                string tag = release.GetProperty("tag_name").GetString() ?? "";
                if (!tag.StartsWith("stable-", StringComparison.Ordinal)) continue;
                var assets = release.GetProperty("assets").EnumerateArray().ToArray();
                var manifests = assets.Where(a => a.GetProperty("name").GetString() == "update-manifest.json").ToArray();
                var archives = assets.Where(a => a.GetProperty("name").GetString() == "release.zip").ToArray();
                if (manifests.Length != 1 || archives.Length != 1) { malformed = true; continue; }
                try
                {
                    var bytes = await transport.GetAsset(manifests[0].GetProperty("id").GetInt64(), token, 128 * 1024, ct);
                    var manifest = JsonSerializer.Deserialize<ReleaseManifest>(bytes, Package.Json) ?? throw new InvalidDataException();
                    Package.ValidateManifest(manifest);
                    if (tag != $"stable-{manifest.Build.Sequence}-{manifest.Build.Commit}" ||
                        archives[0].GetProperty("size").GetInt64() != manifest.ArchiveSize ||
                        assets.Any(a => a.GetProperty("state").GetString() != "uploaded")) throw new InvalidDataException("Release identity mismatch.");
                    if (manifest.Build.Sequence > (installed?.Sequence ?? 0) && manifest.Build.Sequence > (best?.Manifest.Build.Sequence ?? 0))
                        best = new(manifest, archives[0].GetProperty("id").GetInt64(), release.GetProperty("body").GetString() ?? "");
                }
                catch (Exception e) when (e is InvalidDataException or JsonException or KeyNotFoundException or NullReferenceException or InvalidOperationException)
                { malformed = true; }
            }
            if (releases.GetArrayLength() < 100)
            {
                if (best is null && malformed) throw new UpdateException(UpdateFailure.Metadata, "Published update metadata is incomplete or unsupported. No update was installed.");
                return best;
            }
        }
        throw new UpdateException(UpdateFailure.Metadata, "Release history exceeds the check limit; no reliable update result is available.");
    }
}
