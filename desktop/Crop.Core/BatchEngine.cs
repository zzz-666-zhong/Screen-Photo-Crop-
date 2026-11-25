using System.Text;
using System.Text.Json;
using OpenCvSharp;

namespace Crop.Core;

public sealed record BatchProgress(int Index, int Total, PhotoRecord Photo, byte[]? Thumbnail);
public sealed class BatchEngine
{
    private static readonly HashSet<string> Extensions = new(StringComparer.OrdinalIgnoreCase) { ".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp" };
    private readonly FrameDetector detector = new();
    private int running;
    private volatile bool stopRequested;
    public bool IsRunning => Volatile.Read(ref running) != 0;
    public BatchSnapshot Batch { get; }
    public string Checkpoint => Path.Combine(Batch.Destination,"batch_session.json");
    private FileStream? batchLock;
    private BatchEngine(BatchSnapshot batch) => Batch = batch;
    public static BatchEngine Create(string source,string destination,CropOptions options)
    {
        source=Path.GetFullPath(source).TrimEnd(Path.DirectorySeparatorChar);destination=Path.GetFullPath(destination).TrimEnd(Path.DirectorySeparatorChar);
        if(!Directory.Exists(source))throw new DirectoryNotFoundException("请选择存在的原照片目录。");
        if(source.Equals(destination,StringComparison.OrdinalIgnoreCase))throw new ArgumentException("原照片与结果目录必须不同。");
        if(options.OutputSize is not (0 or 128 or 256 or 400 or 512) || options.InsetPixels is <0 or >100)throw new ArgumentException("输出尺寸或内切设置无效。");
        if(File.Exists(Path.Combine(destination,"batch_session.json")))throw new InvalidOperationException("这个目录已有批次，请使用“打开批次”恢复，或选择新目录。");
        if(File.Exists(Path.Combine(destination,"crop_session.json")))throw new InvalidOperationException("这个目录保存着旧版结果，请选择一个新的结果目录，保留原实验记录。");
        var enumeration=new EnumerationOptions { RecurseSubdirectories=options.Recursive, AttributesToSkip=FileAttributes.ReparsePoint, IgnoreInaccessible=false };
        string prefix=destination+Path.DirectorySeparatorChar;
        var files=Directory.EnumerateFiles(source,"*",enumeration).Where(p=>Extensions.Contains(Path.GetExtension(p))&&!p.StartsWith(prefix,StringComparison.OrdinalIgnoreCase)).Order(StringComparer.OrdinalIgnoreCase).ToList();
        if(files.Count==0)throw new InvalidOperationException("没有找到支持的照片。");
        Directory.CreateDirectory(destination);
        var batch=new BatchSnapshot { Source=source, Destination=destination,Options=options,Photos=files.Select(p=>new PhotoRecord { RelativePath=Path.GetRelativePath(source,p) }).ToList() };
        var engine=new BatchEngine(batch);engine.Exclusive(()=>engine.Save());return engine;
    }
    public static BatchEngine Open(string directory)
    {
        string path=Directory.Exists(directory)?Path.Combine(directory,"batch_session.json"):directory;
        var batch=JsonSerializer.Deserialize<BatchSnapshot>(File.ReadAllText(path),Store.Json)??throw new InvalidDataException("批次记录为空。");
        if(batch.Schema!=1||batch.Photos.Count==0)throw new InvalidDataException("不支持的批次记录。");
        if(!Path.GetFullPath(Path.GetDirectoryName(path)!).Equals(Path.GetFullPath(batch.Destination),StringComparison.OrdinalIgnoreCase))throw new InvalidDataException("结果目录已移动。请先恢复原目录位置。");
        if(batch.Photos.Select(p=>p.RelativePath).Distinct(StringComparer.OrdinalIgnoreCase).Count()!=batch.Photos.Count)throw new InvalidDataException("批次包含重复照片。");
        foreach(var p in batch.Photos){Store.SafePath(batch.Source,p.RelativePath);if(p.Output is not null)Store.SafePath(batch.Destination,p.Output);if(p.State==PhotoState.Processing)p.State=PhotoState.Pending;}
        return new(batch);
    }
    public string SourcePath(PhotoRecord photo)=>Store.SafePath(Batch.Source,photo.RelativePath);
    public string? OutputPath(PhotoRecord photo)=>photo.Output is null?null:Store.SafePath(Batch.Destination,photo.Output);
    public void RequestStop()=>stopRequested=true;
    public async Task RunAsync(IProgress<BatchProgress>? progress=null,CancellationToken cancellation=default)
    {
        if(Interlocked.CompareExchange(ref running,1,0)!=0)throw new InvalidOperationException("批次正在处理。");
        stopRequested=false;
        try { await Task.Run(()=>Exclusive(()=>Run(progress,cancellation)),CancellationToken.None); }
        finally { Volatile.Write(ref running,0); }
    }
    private void Run(IProgress<BatchProgress>? progress,CancellationToken cancellation)
    {
        Cv2.SetNumThreads(Math.Max(1,Math.Min(4,Environment.ProcessorCount/2)));
        for(int i=0;i<Batch.Photos.Count;i++)
        {
            if(stopRequested||cancellation.IsCancellationRequested)break;
            var p=Batch.Photos[i];
            // Previously processed items are immutable during resume. A changed source
            // is surfaced for review; it is never silently re-associated to old corners.
            if(p.State!=PhotoState.Pending)
            {
                if(p.State is PhotoState.AutoAccepted or PhotoState.Confirmed)
                {
                    if(!File.Exists(SourcePath(p))||Store.Hash(SourcePath(p))!=p.SourceHash||OutputPath(p) is not string saved||!File.Exists(saved)||Store.Hash(saved)!=p.OutputHash)
                    {p.State=PhotoState.Error;p.Reasons=["原图或已保存结果缺失/改变，请人工检查"];Save();progress?.Report(new(i+1,Batch.Photos.Count,p,null));}
                }
                continue;
            }
            p.State=PhotoState.Processing;progress?.Report(new(i+1,Batch.Photos.Count,p,null));
            byte[]? thumbnail=null;
            try
            {
                string path=SourcePath(p),hash=Store.Hash(path);
                using var image=Store.LoadImage(path);p.Width=image.Width;p.Height=image.Height;
                p.SourceHash=hash;
                var result=detector.Detect(image,Batch.Options.Square,cancellation);
                if(Store.Hash(path)!=hash)throw new IOException("读取期间原照片发生变化。");
                p.Corners=result.Corners is null?null:PixelPoint.From(result.Corners);p.Evidence=result.Evidence;p.Reasons=result.Reasons;
                p.State=result.Automatic?PhotoState.AutoAccepted:PhotoState.NeedsReview;
                if(result.Corners is not null)
                {
                    using var cropped=Store.Rectify(image,result.Corners,Batch.Options);
                    SaveCrop(p,cropped,result.Automatic?"裁剪成功":"待复核");thumbnail=Store.Thumbnail(cropped);
                }
                else thumbnail=Store.Thumbnail(image);
            }
            catch(OperationCanceledException){p.State=PhotoState.Pending;Save();break;}
            catch(Exception ex) when(ex is not OutOfMemoryException){p.State=PhotoState.Error;p.Reasons=[ex.Message];}
            p.UpdatedAt=DateTimeOffset.Now;Save();progress?.Report(new(i+1,Batch.Photos.Count,p,thumbnail));
        }
        ExportCompatibility();ExportCsv();
    }
    private void SaveCrop(PhotoRecord p,Mat image,string folder)
    {
        string relative=Path.Combine(folder,Store.OutputName(p.RelativePath)),target=Store.SafePath(Batch.Destination,relative);
        Cv2.ImEncode(".png",image,out byte[] bytes,new int[]{(int)ImwriteFlags.PngCompression,1});
        if(File.Exists(target) && (p.Output is null || !target.Equals(OutputPath(p),StringComparison.OrdinalIgnoreCase)))
        {
            string expected=Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(bytes)).ToLowerInvariant();
            if(Store.Hash(target)!=expected)throw new IOException("目标文件已存在且内容不同，已阻止覆盖："+relative);
            // Recover a PNG committed just before an interrupted checkpoint write.
        }
        else Store.WriteBytes(target,bytes);
        p.Output=relative;p.OutputHash=Store.Hash(target);
    }
    public void Accept(PhotoRecord p,PixelPoint[] corners)
    {
        RequireIdle();Exclusive(()=>
        {
            string path=SourcePath(p),hash=Store.Hash(path);
            if(!string.IsNullOrEmpty(p.SourceHash)&&hash!=p.SourceHash)throw new IOException("原图已改变，无法沿用旧批次坐标。");
            using var image=Store.LoadImage(path);var q=Store.ValidateCorners(corners.Select(v=>v.ToCv()),image.Width,image.Height);
            using var cropped=Store.Rectify(image,q,Batch.Options);
            string? old=p.Output,oldHash=p.OutputHash; var previousCorners=p.Corners;
            // Update the item only after the image and all source checks succeed.
            if(Store.Hash(path)!=hash)throw new IOException("保存期间原图发生变化。");
            SaveCrop(p,cropped,"裁剪成功");p.Corners=PixelPoint.From(q);p.SourceHash=hash;p.Width=image.Width;p.Height=image.Height;
            p.ManuallyModified=old is null||p.ManuallyModified||!SameCorners(corners, previousCorners);
            p.State=PhotoState.Confirmed;p.Reasons=[];p.UpdatedAt=DateTimeOffset.Now;
            Save();ExportCompatibility();ExportCsv();
            if(old is not null&&old!=p.Output&&oldHash is not null){string oldPath=Store.SafePath(Batch.Destination,old);if(File.Exists(oldPath)&&Store.Hash(oldPath)==oldHash)File.Delete(oldPath);}
        });
    }
    private static bool SameCorners(PixelPoint[] a,PixelPoint[]? b)=>b is not null&&a.Length==b.Length&&a.Zip(b).All(pair=>Math.Abs(pair.First.X-pair.Second.X)<.1&&Math.Abs(pair.First.Y-pair.Second.Y)<.1);
    public void Reject(PhotoRecord p,string reason)
    {
        RequireIdle();Exclusive(()=>
        {
            string? old=p.Output,oldHash=p.OutputHash;
            if(old is not null && oldHash is not null && OutputPath(p) is string oldPath && File.Exists(oldPath))
            {
                if(Store.Hash(oldPath)!=oldHash)throw new IOException("已保存图片发生变化，已阻止自动排除。");
                string archived=Path.Combine("已排除",Store.OutputName(p.RelativePath));
                string target=Store.SafePath(Batch.Destination,archived);
                if(File.Exists(target)&&target!=oldPath)throw new IOException("归档文件已存在，请检查结果目录。");
                if(target!=oldPath)Store.WriteBytes(target,File.ReadAllBytes(oldPath));
                p.Output=archived;p.OutputHash=Store.Hash(target);
            }
            p.State=PhotoState.Rejected;p.Reasons=[reason];p.UpdatedAt=DateTimeOffset.Now;Save();ExportCompatibility();ExportCsv();
            if(old is not null && old!=p.Output && oldHash is not null){string path=Store.SafePath(Batch.Destination,old);if(File.Exists(path)&&Store.Hash(path)==oldHash)File.Delete(path);}
        });
    }
    public void RetryErrors()
    {
        RequireIdle();Exclusive(()=>{foreach(var p in Batch.Photos.Where(p=>p.State==PhotoState.Error && p.Output is null)){p.State=PhotoState.Pending;p.Reasons=[];}Save();});
    }
    private void RequireIdle(){if(IsRunning)throw new InvalidOperationException("请等待暂停完成后编辑结果。");}
    private void Exclusive(Action action)
    {
        if(batchLock is not null)throw new InvalidOperationException("批次正在写入。");
        string path=Path.Combine(Batch.Destination,".batch.lock");Directory.CreateDirectory(Batch.Destination);
        try { batchLock=new FileStream(path,FileMode.OpenOrCreate,FileAccess.ReadWrite,FileShare.None);action(); }
        finally { batchLock?.Dispose();batchLock=null; }
    }
    private void Save()=>Store.WriteJson(Checkpoint,Batch);
    public void ExportCsv()
    {
        static string Cell(string? value){value??="";if(value.Length>0&&"=+-@".Contains(value[0]))value="'"+value;return "\""+value.Replace("\"","\"\"")+"\"";}
        var text=new StringBuilder("input,status,output,source_sha256,output_sha256,reason,manual_modified\r\n");
        foreach(var p in Batch.Photos)text.AppendLine(string.Join(',',new[]{p.RelativePath,p.State.ToString(),p.Output,p.SourceHash,p.OutputHash,string.Join("；",p.Reasons),p.ManuallyModified.ToString()}.Select(Cell)));
        Store.WriteBytes(Path.Combine(Batch.Destination,"crop_report.csv"),Encoding.UTF8.GetPreamble().Concat(Encoding.UTF8.GetBytes(text.ToString())).ToArray());
    }
    private void ExportCompatibility()
    {
        var records=new Dictionary<string,object>();var labels=new Dictionary<string,object>();
        foreach(var p in Batch.Photos)
        {
            bool saved=p.State is PhotoState.AutoAccepted or PhotoState.Confirmed;
            records[p.RelativePath.Replace('\\','/')]=new {input=p.RelativePath,output=p.Output,status=saved?"ok":p.State==PhotoState.Rejected?"capture_failed":p.State==PhotoState.NeedsReview?"needs_review":p.State.ToString().ToLowerInvariant(),saved,source_sha256=p.SourceHash,quad=p.Corners?.Select(v=>new[]{v.X,v.Y}),manual_modified=p.ManuallyModified};
            if(p.Corners is not null&&!string.IsNullOrEmpty(p.SourceHash))labels[p.SourceHash]=new {id="capture_"+p.SourceHash[..20],group="capture_"+p.SourceHash,image=SourcePath(p),source_sha256=p.SourceHash,quad=p.Corners.Select(v=>new[]{v.X,v.Y}),image_size=new[]{p.Width,p.Height},output=p.Output,confirmed=p.State==PhotoState.Confirmed,manual_modified=p.ManuallyModified,application_version=Batch.Version,model_version=new{detector=Batch.Detector},square=Batch.Options.Square,crop_options=Batch.Options};
        }
        Store.WriteJson(Path.Combine(Batch.Destination,"crop_session.json"),new {schema=1,source=Batch.Source,destination=Batch.Destination,files=Batch.Photos.Select(p=>p.RelativePath.Replace('\\','/')),records,options=Batch.Options,application_version=Batch.Version});
        Store.WriteJson(Path.Combine(Batch.Destination,"crop_labels.json"),new{schema=1,coordinate_system="original pixels after EXIF orientation",items=labels});
    }
}
