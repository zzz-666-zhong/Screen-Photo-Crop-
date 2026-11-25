using System.Diagnostics;
using System.Globalization;
using System.IO.Compression;
using System.Text;
using OpenCvSharp;

namespace Crop.Core;

public sealed record BatchProgress(int Index, int Total, PhotoRecord Photo, byte[]? Thumbnail);

public sealed class BatchEngine
{
    private const string FailureFolder = "拍摄失败";
    private const string FailureReport = "拍摄失败记录.csv";
    private static readonly HashSet<string> Extensions = new(StringComparer.OrdinalIgnoreCase)
        { ".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp" };
    private readonly BatchLedger ledger;
    private readonly FrameDetector detector = new();
    private int running;
    private volatile bool stopRequested;
    public bool IsRunning => Volatile.Read(ref running) != 0;
    public BatchSnapshot Batch { get; }
    public string Checkpoint => ledger.Checkpoint;
    public string? ReportWarning { get; private set; }
    public BatchTimings? LastTimings { get; private set; }
    private BatchEngine(BatchSnapshot batch, BatchLedger ledger) => (Batch, this.ledger) = (batch, ledger);

    public static bool IsPhotoFile(string path) => Extensions.Contains(Path.GetExtension(path));

    public static BatchEngine Create(string source, string destination, CropOptions options)
    {
        source = Normalize(source);
        destination = Normalize(destination);
        if (!Directory.Exists(source)) throw new DirectoryNotFoundException("请选择存在的原照片目录。");
        var enumeration = new EnumerationOptions
            { RecurseSubdirectories = options.Recursive, AttributesToSkip = FileAttributes.ReparsePoint };
        return CreateCore(source, destination, options, Directory.EnumerateFiles(source, "*", enumeration)
            .Where(IsPhotoFile).Where(path => !Inside(destination, path)));
    }

    public static BatchEngine CreateFiles(IEnumerable<string> paths, string destination, CropOptions options)
    {
        var files = paths.Select(Path.GetFullPath).Distinct(StringComparer.OrdinalIgnoreCase).ToArray();
        if (files.Length == 0 || files.Any(path => !IsPhotoFile(path) || !File.Exists(path)))
            throw new ArgumentException("请选择存在的 JPG、PNG、BMP、TIFF 或 WebP 照片。");
        string source = Path.GetDirectoryName(files[0])!;
        while (files.Any(file => !Inside(source, file)))
            source = Path.GetDirectoryName(source) ?? throw new ArgumentException("同一批次的照片必须位于同一磁盘。");
        return CreateCore(source, Normalize(destination), options, files);
    }

    private static BatchEngine CreateCore(string source, string destination, CropOptions options, IEnumerable<string> files)
    {
        if (SamePath(source, destination) || Inside(destination, source))
            throw new ArgumentException("结果目录应与原照片目录分开，且不得包含原照片目录。");
        if (options.OutputSize is < 0 or > 12000 || options.InsetPixels is < 0 or > 100 ||
            options.JpegQuality is < 1 or > 100 || options.PngCompression is < 0 or > 9 ||
            !Enum.IsDefined(options.Format) || !Enum.IsDefined(options.Detection) ||
            (options.PreserveDepth && options.Format != CropFileFormat.Png))
            throw new ArgumentException("输出尺寸、格式或质量设置无效。");
        var photos = files.Select(Path.GetFullPath).Distinct(StringComparer.OrdinalIgnoreCase)
            .Order(StringComparer.OrdinalIgnoreCase).Select(path =>
            {
                if (!Inside(source, path) || Inside(destination, path))
                    throw new ArgumentException("原照片不能位于结果目录中。");
                return new PhotoRecord { RelativePath = Path.GetRelativePath(source, path) };
            }).ToList();
        if (photos.Count == 0) throw new InvalidOperationException("没有找到支持的照片。");
        if (photos.GroupBy(photo => OutputName(photo, options), StringComparer.OrdinalIgnoreCase).Any(group => group.Count() > 1))
            throw new ArgumentException("当前命名或目录设置会产生同名结果。请保留子目录或在模板中加入 {ext}。");

        var ledger = new BatchLedger(destination);
        using var batchLock = Acquire(destination);
        if (File.Exists(ledger.Checkpoint) || File.Exists(Path.Combine(destination, "crop_session.json")))
            throw new InvalidOperationException("这个目录已有批次，请打开已有批次或选择新目录。");
        var batch = new BatchSnapshot { Source = source, Destination = destination, Options = options, Photos = photos };
        ledger.Compact(batch);
        return new BatchEngine(batch, ledger);
    }

    public static BatchEngine Open(string directory) => OpenCore(directory, null);
    public static BatchEngine Relocate(string directory, string source) => OpenCore(directory, Normalize(source));

    private static BatchEngine OpenCore(string directory, string? source)
    {
        directory = Normalize(Directory.Exists(directory) ? directory : Path.GetDirectoryName(Path.GetFullPath(directory))!);
        var ledger = new BatchLedger(directory);
        if (!File.Exists(ledger.Checkpoint)) throw new FileNotFoundException("所选目录缺少 batch_session.json。");
        using var batchLock = Acquire(directory);
        var batch = ledger.Read();
        if (source is null && !SamePath(directory, Normalize(batch.Destination)))
            throw new IOException("结果目录已移动。请使用「重新定位批次」。");
        if (source is not null)
        {
            if (!Directory.Exists(source) || SamePath(source, directory) || Inside(directory, source))
                throw new ArgumentException("请选择与结果目录分开的原照片目录。");
            foreach (var photo in batch.Photos)
            {
                string original = Store.SafePath(source, photo.RelativePath);
                if (!File.Exists(original) || (photo.SourceHash.Length > 0 && Store.Hash(original) != photo.SourceHash))
                    throw new IOException("原照片缺失或内容不匹配：" + photo.RelativePath);
                if (photo.Output is string output && photo.OutputHash is string hash &&
                    photo.PendingWrite is null && Store.Hash(Store.SafePath(directory, output)) != hash)
                    throw new IOException("结果内容不匹配：" + output);
            }
            batch.Source = source;
            batch.Destination = directory;
        }

        foreach (var photo in batch.Photos)
        {
            Store.SafePath(batch.Source, photo.RelativePath);
            if (photo.Output is not null) Store.SafePath(directory, photo.Output);
            if (photo.State == PhotoState.Processing) photo.State = PhotoState.Pending;
            if (photo.State == PhotoState.Rejected && photo.FailureHistory is null)
                photo.FailureHistory = [new CaptureFailure(string.Join("；", photo.Reasons),
                    photo.UpdatedAt ?? batch.CreatedAt, photo.Output, photo.SourceHash)];
        }
        var engine = new BatchEngine(batch, ledger);
        bool recover = batch.Photos.Any(NeedsRecovery);
        if (recover) engine.RecoverPending();
        if (source is not null || recover)
        {
            ledger.Compact(batch);
            engine.WriteDerivedReports();
        }
        return engine;
    }

    public string SourcePath(PhotoRecord photo) => Store.SafePath(Batch.Source, photo.RelativePath);
    public string? OutputPath(PhotoRecord photo) => photo.Output is null ? null : Store.SafePath(Batch.Destination, photo.Output);
    public void RequestStop() => stopRequested = true;

    public async Task RunAsync(IProgress<BatchProgress>? progress = null, CancellationToken cancellation = default)
    {
        if (Interlocked.CompareExchange(ref running, 1, 0) != 0) throw new InvalidOperationException("批次正在处理。");
        stopRequested = false;
        try { await Task.Run(() => Exclusive(() => Run(progress, cancellation)), CancellationToken.None); }
        finally { Volatile.Write(ref running, 0); }
    }

    private void Run(IProgress<BatchProgress>? progress, CancellationToken cancellation)
    {
        // One decoded original at a time. OpenCV can parallelize image operations internally.
        Cv2.SetNumThreads(Math.Max(1, Math.Min(4, Environment.ProcessorCount / 2)));
        TimeSpan read = default, detect = default, rectify = default, encode = default, commit = default;
        int processed = 0;
        RecoverPending();
        for (int i = 0; i < Batch.Photos.Count; i++)
        {
            if (stopRequested || cancellation.IsCancellationRequested) break;
            var photo = Batch.Photos[i];
            if (NeedsRecovery(photo)) continue;
            if (photo.State != PhotoState.Pending)
            {
                if (photo.State is PhotoState.AutoAccepted or PhotoState.Confirmed)
                {
                    try { VerifyCompleted(photo); }
                    catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
                    {
                        RecordError(photo, ex);
                        progress?.Report(new(i + 1, Batch.Photos.Count, photo, null));
                    }
                }
                continue;
            }

            photo.State = PhotoState.Processing;
            progress?.Report(new(i + 1, Batch.Photos.Count, photo, null));
            try
            {
                long start = Stopwatch.GetTimestamp();
                using var source = new PhotoInput(SourcePath(photo));
                RequireSourceHash(photo, source.Hash);
                using var image = Store.Decode(source.Bytes, Batch.Options.PreserveDepth);
                read += Stopwatch.GetElapsedTime(start);
                start = Stopwatch.GetTimestamp();
                bool restore = photo.RestoreState is not null && photo.Corners?.Length == 4;
                var result = restore ? new FrameResult(photo.Corners!.Select(point => point.ToCv()).ToArray(),
                    true, [], photo.Evidence, photo.Alternatives?.Select(quad => quad.Select(point => point.ToCv()).ToArray()).ToArray()) :
                    detector.Detect(image, Batch.Options.Square, cancellation, Batch.Options.Detection);
                detect += Stopwatch.GetElapsedTime(start);
                byte[]? payload = null;
                if (result.Corners is not null)
                {
                    start = Stopwatch.GetTimestamp();
                    using var cropped = Store.Rectify(image, result.Corners, Batch.Options, restore ? photo.Rotation : 0);
                    rectify += Stopwatch.GetElapsedTime(start);
                    start = Stopwatch.GetTimestamp();
                    payload = Encode(cropped);
                    encode += Stopwatch.GetElapsedTime(start);
                }
                start = Stopwatch.GetTimestamp();
                var planned = Copy(photo);
                planned.Width = image.Width;
                planned.Height = image.Height;
                planned.SourceHash = source.Hash;
                planned.Corners = result.Corners is null ? null : PixelPoint.From(result.Corners);
                planned.Evidence = result.Evidence;
                planned.Alternatives = result.Alternatives?.Select(PixelPoint.From).ToArray();
                planned.Reasons = result.Reasons;
                planned.Error = PhotoError.None;
                planned.State = restore ? photo.RestoreState!.Value : result.Automatic ? PhotoState.AutoAccepted : PhotoState.NeedsReview;
                planned.RestoreState = null;
                planned.UpdatedAt = DateTimeOffset.Now;
                if (payload is not null)
                    SaveOutput(photo, planned, Path.Combine(result.Automatic ? "裁剪成功" : "待复核", OutputName(photo, Batch.Options)), payload, null);
                else Persist(photo, planned);
                commit += Stopwatch.GetElapsedTime(start);
                processed++;
            }
            catch (OperationCanceledException) { photo.State = PhotoState.Pending; break; }
            catch (Exception ex) when (ex is not OutOfMemoryException) { RecordError(photo, ex); }
            progress?.Report(new(i + 1, Batch.Photos.Count, photo, null));
            ledger.CompactIfNeeded(Batch);
        }
        ledger.Compact(Batch);
        LastTimings = new BatchTimings(processed, read, detect, rectify, encode, commit);
        WriteDerivedReports();
    }

    private void VerifyCompleted(PhotoRecord photo)
    {
        string source = SourcePath(photo);
        if (!File.Exists(source)) throw new PhotoFileException(PhotoError.MissingSource, "原照片找不到，请重新定位原照片目录。");
        RequireSourceHash(photo, Store.Hash(source));
        if (OutputPath(photo) is not string output || !File.Exists(output))
            throw new PhotoFileException(PhotoError.MissingOutput, "已导出的照片找不到，可以安全重试。");
        if (Store.Hash(output) != photo.OutputHash)
            throw new PhotoFileException(PhotoError.ChangedOutput, "导出文件已修改，请在复核时选择是否覆盖。");
    }

    private static void RequireSourceHash(PhotoRecord photo, string actual)
    {
        if (photo.SourceHash.Length > 0 && photo.SourceHash != actual)
            throw new PhotoFileException(PhotoError.ChangedSource, "原照片内容已改变。请恢复原文件或将新照片导入新批次。");
    }

    private byte[] Encode(Mat image)
    {
        bool jpeg = Batch.Options.Format == CropFileFormat.Jpeg;
        Cv2.ImEncode(jpeg ? ".jpg" : ".png", image, out byte[] bytes, jpeg
            ? [(int)ImwriteFlags.JpegQuality, Batch.Options.JpegQuality]
            : [(int)ImwriteFlags.PngCompression, Batch.Options.PngCompression]);
        if (bytes.Length == 0) throw new IOException("图像编码未生成结果。");
        return bytes;
    }

    public void Accept(PhotoRecord photo, PixelPoint[] corners, CropOverwrite? overwrite = null, int rotation = 0,
        string? previewHash = null, bool deferReports = false)
    {
        RequireIdle();
        Exclusive(() =>
        {
            if (NeedsRecovery(photo)) FinishOutput(photo, overwrite);
            using var source = new PhotoInput(SourcePath(photo));
            RequireSourceHash(photo, source.Hash);
            if (previewHash is not null && source.Hash != previewHash)
                throw new PhotoFileException(PhotoError.ChangedSource, "照片在预览期间发生变化，请重新打开这张照片。");
            using var image = Store.Decode(source.Bytes, Batch.Options.PreserveDepth);
            var points = Store.ValidateCorners(corners.Select(point => point.ToCv()), image.Width, image.Height);
            using var result = Store.Rectify(image, points, Batch.Options, rotation);
            var planned = Copy(photo);
            planned.SourceHash = source.Hash;
            planned.Corners = PixelPoint.From(points);
            planned.Width = image.Width;
            planned.Height = image.Height;
            planned.Rotation = rotation;
            planned.ManuallyModified = photo.Output is null || photo.ManuallyModified ||
                !SameCorners(planned.Corners, photo.Corners) || rotation != photo.Rotation;
            planned.State = PhotoState.Confirmed;
            planned.Error = PhotoError.None;
            planned.RestoreState = null;
            planned.Reasons = [];
            planned.UpdatedAt = DateTimeOffset.Now;
            if (planned.FailureHistory is not null)
                planned.FailureHistory = planned.FailureHistory.Select(failure => failure.ResolvedAt is null
                    ? failure with { ResolvedAt = planned.UpdatedAt } : failure).ToList();
            SaveOutput(photo, planned, Path.Combine("裁剪成功", OutputName(photo, Batch.Options)), Encode(result), overwrite);
            ledger.CompactIfNeeded(Batch);
            if (!deferReports) WriteDerivedReports();
        });
    }

    public void Reject(PhotoRecord photo, string reason)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(reason);
        RequireIdle();
        Exclusive(() =>
        {
            if (NeedsRecovery(photo)) FinishOutput(photo);
            using var source = new PhotoInput(SourcePath(photo));
            RequireSourceHash(photo, source.Hash);
            string archive = Path.Combine(FailureFolder, photo.RelativePath);
            var planned = Copy(photo);
            var now = DateTimeOffset.Now;
            planned.FailureHistory ??= [];
            int active = planned.FailureHistory.FindLastIndex(failure => failure.ResolvedAt is null);
            var mark = new CaptureFailure(reason.Trim(), active >= 0 ? planned.FailureHistory[active].MarkedAt : now, archive, source.Hash);
            if (active >= 0) planned.FailureHistory[active] = mark;
            else planned.FailureHistory.Add(mark);
            planned.SourceHash = source.Hash;
            planned.State = PhotoState.Rejected;
            planned.UpdatedAt = now;
            planned.Error = PhotoError.None;
            planned.RestoreState = null;
            planned.Reasons = [mark.Reason];
            SaveOutput(photo, planned, archive, source.Bytes, null, keepArchive: true);
            ledger.CompactIfNeeded(Batch);
            WriteDerivedReports();
        });
    }

    private void SaveOutput(PhotoRecord photo, PhotoRecord planned, string relative, byte[] bytes,
        CropOverwrite? overwrite, bool keepArchive = false)
    {
        string target = Store.SafePath(Batch.Destination, relative);
        string contentHash = Store.Hash(bytes);
        string? existing = File.Exists(target) ? Store.Hash(target) : null;
        if (existing is not null && existing != contentHash &&
            !(SamePath(photo.Output ?? "", relative) && existing == photo.OutputHash && !keepArchive) &&
            !(overwrite is not null && SamePath(overwrite.TargetPath, target) && existing == overwrite.ExistingHash))
            throw new OutputConflictException(target, existing);
        planned.Output = relative;
        planned.OutputHash = contentHash;
        if (photo.Output is string old && !SamePath(old, relative) && photo.OutputHash is string hash &&
            !(photo.FailureHistory?.Any(failure => SamePath(failure.Archive ?? "", old)) ?? false))
        {
            string oldFile = Store.SafePath(Batch.Destination, old);
            if (File.Exists(oldFile) && Store.Hash(oldFile) != hash)
                throw new PhotoFileException(PhotoError.ChangedOutput, "旧裁剪文件已修改，请先保留或移走旧文件：" + old);
            planned.PendingRemoval = new OutputRemoval(old, hash);
        }

        if (existing != contentHash)
        {
            string relativeStage = Path.Combine(".screen-crop-pending", Guid.NewGuid().ToString("N") + ".bin");
            string stage = Store.SafePath(Batch.Destination, relativeStage);
            Store.WriteBytes(stage, bytes, overwrite: false);
            planned.PendingWrite = new OutputCommit(relativeStage, relative, contentHash, existing);
            try { Persist(photo, planned); }
            catch { File.Delete(stage); throw; }
        }
        else Persist(photo, planned);
        try { FinishOutput(photo); }
        catch (Exception ex) when (ex is IOException or InvalidDataException or UnauthorizedAccessException)
        {
            photo.Error = Classify(ex);
            ReportWarning = "结果已登记，文件待恢复：" + ex.Message;
        }
    }

    private void FinishOutput(PhotoRecord photo, CropOverwrite? overwrite = null)
    {
        if (photo.PendingWrite is OutputCommit write)
        {
            string target = Store.SafePath(Batch.Destination, write.TargetPath);
            string staged = Store.SafePath(Batch.Destination, write.StagedPath);
            string? current = File.Exists(target) ? Store.Hash(target) : null;
            if (current != write.Sha256)
            {
                bool approved = overwrite is not null && SamePath(overwrite.TargetPath, target) && current == overwrite.ExistingHash;
                if (current is not null && current != write.ReplacesHash && !approved)
                    throw new OutputConflictException(target, current);
                if (!File.Exists(staged) || Store.Hash(staged) != write.Sha256)
                    throw new InvalidDataException("待恢复的输出文件缺失或损坏：" + write.TargetPath);
                Directory.CreateDirectory(Path.GetDirectoryName(target)!);
                File.Move(staged, target, current is not null);
            }
            else if (File.Exists(staged)) File.Delete(staged);
        }
        if (photo.PendingRemoval is OutputRemoval removal)
        {
            string path = Store.SafePath(Batch.Destination, removal.RelativePath);
            if (!SamePath(removal.RelativePath, photo.Output ?? "") && File.Exists(path))
            {
                if (Store.Hash(path) != removal.Sha256)
                    throw new PhotoFileException(PhotoError.ChangedOutput, "旧裁剪文件已修改，请保留或移走旧文件：" + removal.RelativePath);
                File.Delete(path);
            }
        }
        if (NeedsRecovery(photo))
        {
            var done = Copy(photo);
            done.PendingWrite = null;
            done.PendingRemoval = null;
            done.Error = PhotoError.None;
            Persist(photo, done);
        }
    }

    private static bool NeedsRecovery(PhotoRecord photo) => photo.PendingWrite is not null || photo.PendingRemoval is not null;

    private void RecoverPending()
    {
        foreach (var photo in Batch.Photos.Where(NeedsRecovery))
        {
            try { FinishOutput(photo); }
            catch (Exception ex) when (ex is IOException or InvalidDataException or UnauthorizedAccessException)
            {
                photo.Error = Classify(ex);
                ReportWarning = "部分结果待恢复：" + ex.Message;
            }
        }
        if (!Batch.Photos.Any(NeedsRecovery) &&
            (ReportWarning?.StartsWith("部分结果待恢复", StringComparison.Ordinal) == true ||
             ReportWarning?.StartsWith("结果已登记", StringComparison.Ordinal) == true))
            ReportWarning = null;
    }

    public bool CanRetry(PhotoRecord photo) => NeedsRecovery(photo) ||
        (photo.State == PhotoState.Error && photo.Error != PhotoError.Conflict);

    public void RetryErrors()
    {
        RequireIdle();
        Exclusive(() =>
        {
            RecoverPending();
            foreach (var photo in Batch.Photos.Where(photo => photo.State == PhotoState.Error && CanRetry(photo) && !NeedsRecovery(photo)))
            {
                var retry = Copy(photo);
                if (photo.Error is PhotoError.ChangedSource or PhotoError.ChangedOutput)
                {
                    try
                    {
                        RequireSourceHash(photo, Store.Hash(SourcePath(photo)));
                        if (photo.RestoreState is not null) VerifyCompleted(photo);
                    }
                    catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { continue; }
                }
                retry.State = photo.Error is PhotoError.ChangedSource or PhotoError.ChangedOutput
                    ? photo.RestoreState ?? PhotoState.Pending : PhotoState.Pending;
                if (retry.State is not PhotoState.Pending) retry.RestoreState = null;
                retry.Error = PhotoError.None;
                retry.Reasons = [];
                Persist(photo, retry);
            }
            ledger.Compact(Batch);
            WriteDerivedReports();
        });
    }

    private void RecordError(PhotoRecord photo, Exception exception)
    {
        var failure = Copy(photo);
        if (photo.State is PhotoState.AutoAccepted or PhotoState.Confirmed) failure.RestoreState = photo.State;
        failure.State = PhotoState.Error;
        failure.Error = Classify(exception);
        string hint = failure.Error switch
        {
            PhotoError.Busy => "请关闭占用这个文件的程序后重试。",
            PhotoError.MissingSource => "请检查原照片，或重新定位批次。",
            PhotoError.InvalidImage => "请检查照片能否打开，必要时转换为支持的格式。",
            PhotoError.NoSpace => "请释放结果磁盘空间后重试。",
            PhotoError.Conflict => "可在单图复核中检查结果并确认覆盖。",
            _ => ""
        };
        failure.Reasons = hint.Length == 0 ? [exception.Message] : [exception.Message, hint];
        failure.UpdatedAt = DateTimeOffset.Now;
        Persist(photo, failure);
    }

    private static PhotoError Classify(Exception error) => error switch
    {
        PhotoFileException file => file.Kind,
        OutputConflictException => PhotoError.Conflict,
        FileNotFoundException or DirectoryNotFoundException => PhotoError.MissingSource,
        InvalidDataException or OpenCvSharpException => PhotoError.InvalidImage,
        UnauthorizedAccessException => PhotoError.Busy,
        IOException io when (io.HResult & 0xffff) is 32 or 33 => PhotoError.Busy,
        IOException io when (io.HResult & 0xffff) is 39 or 112 => PhotoError.NoSpace,
        _ => PhotoError.Other
    };

    public string ExportCaptureFailures() => ExportCaptureFailures(false);

    public string ExportCaptureFailures(bool includeHistory)
    {
        RequireIdle();
        string path = Path.Combine(Batch.Destination, includeHistory ? "拍摄失败历史.csv" : FailureReport);
        Exclusive(() => WriteCsv(path, FailureRows(includeHistory)));
        return path;
    }

    public bool FailureReportOutdated()
    {
        string path = Path.Combine(Batch.Destination, FailureReport);
        try { return File.Exists(path) && File.ReadAllText(path) != FailureRows(false).ToString(); }
        catch (IOException) { return true; }
        catch (UnauthorizedAccessException) { return true; }
    }

    private StringBuilder FailureRows(bool includeHistory)
    {
        var csv = new StringBuilder("照片相对路径,失败原因,标记时间,原照片路径,归档相对路径,归档类型,原照片SHA256,状态,重裁时间\r\n");
        foreach (var photo in Batch.Photos)
        {
            foreach (var failure in photo.FailureHistory ?? [])
            {
                if (!includeHistory && (failure.ResolvedAt is not null || photo.State != PhotoState.Rejected)) continue;
                string kind = failure.Archive is null ? "无归档" :
                    failure.Archive.StartsWith(FailureFolder + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase) ? "原照片副本" : "旧版裁剪归档";
                AppendCsvRow(csv, photo.RelativePath, failure.Reason, FormatDate(failure.MarkedAt), SourcePath(photo),
                    failure.Archive, kind, failure.Sha256, failure.ResolvedAt is null ? "待重拍" : "已重裁", FormatDate(failure.ResolvedAt));
            }
        }
        return csv;
    }

    public void RefreshReports()
    {
        RequireIdle();
        Exclusive(() => WriteDerivedReports());
    }

    private void WriteDerivedReports()
    {
        try
        {
            ExportCompatibility();
            ExportCsv();
            if (ReportWarning?.StartsWith("表格待重试", StringComparison.Ordinal) == true) ReportWarning = null;
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException)
        {
            ReportWarning = "表格待重试。请关闭占用文件的程序后点「更新批次报表」。" + error.Message;
        }
    }

    public void ExportCsv()
    {
        var csv = new StringBuilder("input,status,output,source_sha256,output_sha256,reason,manual_modified,error_kind\r\n");
        foreach (var photo in Batch.Photos)
            AppendCsvRow(csv, photo.RelativePath, photo.State.ToString(), photo.Output, photo.SourceHash,
                photo.OutputHash, string.Join("；", photo.Reasons), photo.ManuallyModified.ToString(), photo.Error.ToString());
        WriteCsv(Path.Combine(Batch.Destination, "crop_report.csv"), csv);
    }

    private void ExportCompatibility()
    {
        var records = new Dictionary<string, object>();
        var labels = new Dictionary<string, object>();
        foreach (var p in Batch.Photos)
        {
            string path = p.RelativePath.Replace('\\', '/');
            bool saved = p.State is PhotoState.AutoAccepted or PhotoState.Confirmed && p.PendingWrite is null;
            var quad = p.Corners?.Select(point => new[] { point.X, point.Y });
            records[path] = new { input = p.RelativePath, output = p.Output, status = saved ? "ok" :
                p.State == PhotoState.Rejected ? "capture_failed" : p.State == PhotoState.NeedsReview ? "needs_review" :
                p.State.ToString().ToLowerInvariant(), saved, source_sha256 = p.SourceHash, quad, manual_modified = p.ManuallyModified };
            if (p.Corners is not null && p.SourceHash.Length > 0)
                labels[path] = new { id = "capture_" + Store.Hash(Encoding.UTF8.GetBytes(path))[..20],
                    group = "capture_" + p.SourceHash, image = SourcePath(p), source_sha256 = p.SourceHash, quad,
                    image_size = new[] { p.Width, p.Height }, output = p.Output, confirmed = saved && p.State == PhotoState.Confirmed,
                    manual_modified = p.ManuallyModified, application_version = BatchSnapshot.CurrentVersion,
                    model_version = new { detector = Batch.Detector }, square = Batch.Options.Square, crop_options = Batch.Options,
                    output_rotation = p.Rotation };
        }
        Store.WriteJson(Path.Combine(Batch.Destination, "crop_session.json"), new { schema = 1, source = Batch.Source,
            destination = Batch.Destination, files = records.Keys, records, options = Batch.Options, application_version = BatchSnapshot.CurrentVersion });
        Store.WriteJson(Path.Combine(Batch.Destination, "crop_labels.json"),
            new { schema = 1, coordinate_system = "original pixels after EXIF orientation", items = labels });
    }

    public void ExportBackup(string destination)
    {
        RequireIdle();
        string zip = Path.GetFullPath(destination);
        if (!Path.GetExtension(zip).Equals(".zip", StringComparison.OrdinalIgnoreCase) || File.Exists(zip))
            throw new ArgumentException("请选择新的 .zip 文件。");
        Exclusive(() =>
        {
            if (Batch.Photos.Any(NeedsRecovery))
                throw new IOException("请先恢复待保存的结果，再导出备份。");
            string temp = zip + "." + Guid.NewGuid().ToString("N") + ".tmp";
            try
            {
                using (var archive = ZipFile.Open(temp, ZipArchiveMode.Create))
                {
                    var manifest = archive.CreateEntry("results/batch_session.json");
                    using (var stream = manifest.Open()) System.Text.Json.JsonSerializer.Serialize(stream, Batch, Store.Json);
                    var entries = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                    foreach (var p in Batch.Photos)
                    {
                        AddToBackup(archive, "originals/" + p.RelativePath, SourcePath(p), p.SourceHash);
                        if (p.Output is string output && entries.Add(output))
                            AddToBackup(archive, "results/" + output, OutputPath(p)!, p.OutputHash);
                    }
                    foreach (var failure in Batch.Photos.SelectMany(p => p.FailureHistory ?? []))
                        if (failure.Archive is string file && entries.Add(file))
                            AddToBackup(archive, "results/" + file, Store.SafePath(Batch.Destination, file),
                                file.StartsWith(FailureFolder + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase) ? failure.Sha256 : null);
                }
                File.Move(temp, zip, overwrite: false);
            }
            finally { if (File.Exists(temp)) File.Delete(temp); }
        });
    }

    private static void AddToBackup(ZipArchive archive, string entry, string path, string? hash)
    {
        using var file = File.OpenRead(path);
        if (!string.IsNullOrEmpty(hash))
        {
            string actual = Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(file)).ToLowerInvariant();
            if (actual != hash) throw new IOException("无法备份内容已变化的文件：" + path);
            file.Position = 0;
        }
        using var stream = archive.CreateEntry(entry.Replace('\\', '/'), CompressionLevel.Fastest).Open();
        file.CopyTo(stream);
    }

    private static string OutputName(PhotoRecord photo, CropOptions options)
    {
        string template = options.NameTemplate ?? "{name}.{ext}_cropped";
        string original = Path.GetFileName(photo.RelativePath);
        string name = System.Text.RegularExpressions.Regex.Replace(template, @"\{(name|ext)\}", match =>
            match.Groups[1].Value == "name" ? Path.GetFileNameWithoutExtension(original) : Path.GetExtension(original).TrimStart('.'));
        if (string.IsNullOrWhiteSpace(name) || name.Length > 220 || name.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0 ||
            name.IndexOfAny(['{', '}']) >= 0 || name.EndsWith('.') || name.EndsWith(' ') ||
            System.Text.RegularExpressions.Regex.IsMatch(name.Split('.')[0], @"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$",
                System.Text.RegularExpressions.RegexOptions.IgnoreCase))
            throw new ArgumentException("命名模板无效。可用 {name} 和 {ext}，无需填写输出扩展名。");
        return Path.Combine(options.KeepFolders ? Path.GetDirectoryName(photo.RelativePath) ?? "" : "",
            name + (options.Format == CropFileFormat.Jpeg ? ".jpg" : ".png"));
    }

    private static void AppendCsvRow(StringBuilder report, params string?[] fields)
    {
        static string Cell(string? field)
        {
            string value = field ?? "";
            string trimmed = value.TrimStart();
            if (trimmed.Length > 0 && "=+-@".Contains(trimmed[0])) value = "'" + value;
            return "\"" + value.Replace("\"", "\"\"") + "\"";
        }
        report.AppendJoin(',', fields.Select(Cell)).Append("\r\n");
    }

    private static void WriteCsv(string path, StringBuilder report) =>
        Store.WriteBytes(path, Encoding.UTF8.GetPreamble().Concat(Encoding.UTF8.GetBytes(report.ToString())).ToArray());
    private static string? FormatDate(DateTimeOffset? date) => date?.ToString("yyyy-MM-dd HH:mm:ss zzz", CultureInfo.InvariantCulture);
    private static string Normalize(string path) => Path.TrimEndingDirectorySeparator(Path.GetFullPath(path));
    private static bool SamePath(string a, string b) => string.Equals(a, b, StringComparison.OrdinalIgnoreCase);
    private static bool Inside(string root, string file) => Path.GetFullPath(file).StartsWith(
        Path.EndsInDirectorySeparator(root) ? root : root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase);
    private static bool SameCorners(PixelPoint[] a, PixelPoint[]? b) => b is not null && a.Length == b.Length &&
        a.Zip(b).All(pair => Math.Abs(pair.First.X - pair.Second.X) < .1 && Math.Abs(pair.First.Y - pair.Second.Y) < .1);

    private void RequireIdle() { if (IsRunning) throw new InvalidOperationException("请暂停批次后再操作。"); }
    private static FileStream Acquire(string destination)
    {
        Directory.CreateDirectory(destination);
        try { return new FileStream(Path.Combine(destination, ".batch.lock"), FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None); }
        catch (IOException ex) when ((ex.HResult & 0xffff) is 32 or 33)
        { throw new IOException("该批次正在另一个窗口写入，请等待它结束后刷新。", ex); }
    }

    private void Exclusive(Action action)
    {
        using var batchLock = Acquire(Batch.Destination);
        ledger.AssertCurrent();
        action();
    }

    private void Persist(PhotoRecord target, PhotoRecord planned)
    {
        ledger.Append(Batch, planned);
        target.SourceHash = planned.SourceHash;
        target.State = planned.State;
        target.Corners = planned.Corners;
        target.Width = planned.Width;
        target.Height = planned.Height;
        target.Output = planned.Output;
        target.OutputHash = planned.OutputHash;
        target.Reasons = planned.Reasons;
        target.Evidence = planned.Evidence;
        target.Alternatives = planned.Alternatives;
        target.Error = planned.Error;
        target.RestoreState = planned.RestoreState;
        target.Rotation = planned.Rotation;
        target.FailureHistory = planned.FailureHistory;
        target.ManuallyModified = planned.ManuallyModified;
        target.UpdatedAt = planned.UpdatedAt;
        target.PendingRemoval = planned.PendingRemoval;
        target.PendingWrite = planned.PendingWrite;
    }

    private static PhotoRecord Copy(PhotoRecord photo) => new()
    {
        RelativePath = photo.RelativePath, SourceHash = photo.SourceHash, State = photo.State,
        Corners = photo.Corners, Width = photo.Width, Height = photo.Height, Output = photo.Output,
        OutputHash = photo.OutputHash, Reasons = photo.Reasons, Evidence = photo.Evidence,
        Alternatives = photo.Alternatives, Error = photo.Error, RestoreState = photo.RestoreState, Rotation = photo.Rotation,
        FailureHistory = photo.FailureHistory?.ToList(), ManuallyModified = photo.ManuallyModified,
        UpdatedAt = photo.UpdatedAt, PendingRemoval = photo.PendingRemoval, PendingWrite = photo.PendingWrite
    };

    private sealed class PhotoInput : IDisposable
    {
        private readonly FileStream stream;
        public byte[] Bytes { get; }
        public string Hash { get; }
        public PhotoInput(string path)
        {
            stream = File.OpenRead(path);
            try
            {
                Bytes = new byte[checked((int)stream.Length)];
                stream.ReadExactly(Bytes);
                Hash = Store.Hash(Bytes);
            }
            catch { stream.Dispose(); throw; }
        }
        public void Dispose() => stream.Dispose();
    }

    private sealed class PhotoFileException(PhotoError kind, string message) : IOException(message)
    {
        public PhotoError Kind { get; } = kind;
    }
}
