using System.Globalization;
using System.Text.Json;

namespace Crop.Core;

internal sealed class BatchLedger(string directory)
{
    private const int CompactAfter = 32;
    private string LogFolder => Path.Combine(directory, ".screen-crop-journal");
    public string Checkpoint => Path.Combine(directory, "batch_session.json");
    private long persistedRevision;
    private long snapshotRevision;
    private string? snapshotHash;

    public BatchSnapshot Read()
    {
        byte[] data = File.ReadAllBytes(Checkpoint);
        var batch = JsonSerializer.Deserialize<BatchSnapshot>(data, Store.Json)
            ?? throw new InvalidDataException("批次记录为空。");
        if (batch.Schema != 1 || batch.Photos.Count == 0 || batch.Revision < 0)
            throw new InvalidDataException("不支持的批次记录。");
        snapshotRevision = batch.Revision;
        var photos = batch.Photos.Select((photo, index) => (photo, index))
            .ToDictionary(item => item.photo.RelativePath, item => item.index, StringComparer.OrdinalIgnoreCase);
        foreach (var entry in Entries().Where(entry => entry.Revision > batch.Revision).ToArray())
        {
            var update = JsonSerializer.Deserialize<PhotoRecord>(File.ReadAllBytes(entry.Path), Store.Json);
            if (entry.Revision != batch.Revision + 1 || update is null || !photos.TryGetValue(update.RelativePath, out var index))
                throw new InvalidDataException("批次日志不完整，无法安全恢复。请使用批次备份。");
            batch.Photos[index] = update;
            batch.Revision = entry.Revision;
        }

        snapshotHash = Store.Hash(data);
        persistedRevision = batch.Revision;
        return batch;
    }

    public void AssertCurrent()
    {
        string? diskHash = File.Exists(Checkpoint) ? Store.Hash(Checkpoint) : null;
        long newest = Entries().Select(entry => entry.Revision).DefaultIfEmpty(0).Max();
        if (diskHash != snapshotHash || Math.Max(snapshotRevision, newest) != persistedRevision) throw new BatchChangedException();
    }

    public void Append(BatchSnapshot batch, PhotoRecord photo)
    {
        long revision = checked(persistedRevision + 1);
        string file = Path.Combine(LogFolder, revision.ToString("D20", CultureInfo.InvariantCulture) + ".json");
        Store.WriteBytes(file, JsonSerializer.SerializeToUtf8Bytes(photo, Store.Json), overwrite: false);
        batch.Revision = persistedRevision = revision;
    }

    public void CompactIfNeeded(BatchSnapshot batch)
    {
        if (persistedRevision - snapshotRevision >= CompactAfter) Compact(batch);
    }

    public void Compact(BatchSnapshot batch)
    {
        byte[] data = JsonSerializer.SerializeToUtf8Bytes(batch, Store.Json);
        Store.WriteBytes(Checkpoint, data);
        snapshotHash = Store.Hash(data);
        snapshotRevision = batch.Revision;
        foreach (var entry in Entries().Where(entry => entry.Revision <= batch.Revision))
        {
            try { File.Delete(entry.Path); }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
        }
    }

    private IEnumerable<(long Revision, string Path)> Entries()
    {
        if (!Directory.Exists(LogFolder)) return [];
        return Directory.EnumerateFiles(LogFolder, "*.json")
            .Select(path => (long.TryParse(Path.GetFileNameWithoutExtension(path), NumberStyles.None,
                CultureInfo.InvariantCulture, out var revision) ? revision : 0, path))
            .Where(entry => entry.Item1 > 0).OrderBy(entry => entry.Item1);
    }
}
