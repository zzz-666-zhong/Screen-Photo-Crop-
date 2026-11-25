using System.Diagnostics;
using System.Text.Json;
using Crop.Core;
using OpenCvSharp;

int passed=0;
void Assert(bool condition,string message){if(!condition)throw new Exception(message);}
async Task Test(string name,Func<Task> body){await body();passed++;Console.WriteLine("PASS "+name);}
Mat Scene(int blur=0)
{
    var image=new Mat(600,800,MatType.CV_8UC3,new Scalar(225,228,232));
    using var texture=new Mat(280,280,MatType.CV_8UC3);Cv2.Randu(texture,new Scalar(15,25,35),new Scalar(185,195,205));
    using(var region=new Mat(image,new Rect(260,150,280,280)))texture.CopyTo(region);
    Cv2.Rectangle(image,new Rect(257,147,286,286),new Scalar(24,24,24),3);
    if(blur>0){using var kernel=new Mat(blur,blur,MatType.CV_32F,Scalar.All(0));for(int i=0;i<blur;i++)kernel.Set(i,i,1f/blur);Cv2.Filter2D(image,image,-1,kernel);}
    return image;
}
string Save(Mat image,string path){Directory.CreateDirectory(Path.GetDirectoryName(path)!);Cv2.ImEncode(".png",image,out byte[] bytes);File.WriteAllBytes(path,bytes);return path;}
if(args.Length>0&&args[0]=="--batch")
{
    var batch=BatchEngine.Create(args[1],args[2],new());await batch.RunAsync();
    Console.WriteLine($"Batch: {batch.Batch.Photos.Count}, auto: {batch.Batch.Photos.Count(p=>p.State==PhotoState.AutoAccepted)}, review: {batch.Batch.Photos.Count(p=>p.State==PhotoState.NeedsReview)}");
    Console.WriteLine(JsonSerializer.Serialize(batch.LastTimings,Store.Json));return;
}
if(args.Length>0&&args[0]=="--evaluate")
{
    var samples=JsonSerializer.Deserialize<List<EvalCase>>(File.ReadAllText(args[1]),Store.Json)!;
    var results=new List<object>();var detector=new FrameDetector();var watch=Stopwatch.StartNew();
    foreach(var sample in samples)
    {
        using var image=Store.LoadImage(sample.Image);var timer=Stopwatch.StartNew();var found=detector.Detect(image,sample.Square);timer.Stop();
        double iou=found.Corners is null?0:FrameDetector.Overlap(found.Corners,sample.Quad.Select(p=>new Point2f((float)p[0],(float)p[1])).ToArray());
        results.Add(new{sample.Image,sample.Split,sample.BaselineIou,iou,automatic=found.Automatic,reasons=found.Reasons,elapsedMs=timer.ElapsedMilliseconds,quad=found.Corners is null?null:PixelPoint.From(found.Corners),found.Evidence});
        Console.WriteLine($"{results.Count}/{samples.Count} IoU={iou:F4} auto={found.Automatic} {Path.GetFileName(sample.Image)}");
    }
    Store.WriteJson(args[2],new{count=samples.Count,elapsedMs=watch.ElapsedMilliseconds,results});return;
}
string root=Path.GetFullPath(args.Length>1&&args[0]=="--fixture"?args[1]:Path.Combine(Path.GetTempPath(),"screen-crop-verify-"+Guid.NewGuid().ToString("N")));
Directory.CreateDirectory(root);
await Test("角点顺序、透视校正及暗色内容保留",()=>
{
    using var image=Scene();var points=new Point2f[]{new(260,150),new(539,150),new(539,429),new(260,429)};
    using var crop=Store.Rectify(image,points.Reverse().ToArray(),new());Assert(crop.Width==crop.Height,"square");Assert(crop.At<Vec3b>(20,20).Item0<210,"dark content");
    bool invalid=false;try{Store.ValidateCorners([new(0,0),new(0,0),new(10,10),new(20,20)],800,600);}catch(ArgumentException){invalid=true;}Assert(invalid,"degenerate corners accepted");return Task.CompletedTask;
});
await Test("清晰和拖影照片定位",()=>
{
    var detector=new FrameDetector();foreach(int blur in new[]{0,9,19}){using var image=Scene(blur);var result=detector.Detect(image);Assert(result.Corners is not null,$"no proposal blur={blur}");double overlap=FrameDetector.Overlap(result.Corners!,[new(260,150),new(539,150),new(539,429),new(260,429)]);Console.WriteLine($"blur={blur} IoU={overlap:F4} auto={result.Automatic}");Assert(overlap>.85,"wrong target");}return Task.CompletedTask;
});
await Test("平坦面板不会自动通过",()=>{using var image=new Mat(600,800,MatType.CV_8UC3,new Scalar(230,230,230));var result=new FrameDetector().Detect(image);Assert(!result.Automatic,"blank accepted");return Task.CompletedTask;});
await Test("JPEG EXIF 方向与原图坐标一致",()=>
{
    using var image=new Mat(60,100,MatType.CV_8UC3,new Scalar(50,100,150));Cv2.ImEncode(".jpg",image,out byte[] jpeg);
    byte[] exif=Convert.FromHexString("FFE1002245786966000049492A0008000000010012010300010000000600000000000000");
    string path=Path.Combine(root,"orientation.jpg");File.WriteAllBytes(path,jpeg.Take(2).Concat(exif).Concat(jpeg.Skip(2)).ToArray());
    using var oriented=Store.LoadImage(path);Assert(oriented.Width==60&&oriented.Height==100,"EXIF orientation mismatch");return Task.CompletedTask;
});
BatchEngine? fixture=null;
await Test("整批运行：自动保存、疑难分流、损坏文件继续",async()=>
{
    string input=Path.Combine(root,"input"),output=Path.Combine(root,"output");using var clear=Scene();using var blurred=Scene(19);using var blank=new Mat(600,800,MatType.CV_8UC3,new Scalar(230,230,230));
    Save(clear,Path.Combine(input,"01_清晰.png"));Save(blurred,Path.Combine(input,"02_抖动.png"));Save(blank,Path.Combine(input,"03_无边界.png"));File.WriteAllText(Path.Combine(input,"04_损坏.jpg"),"broken");
    var hashes=Directory.GetFiles(input).ToDictionary(p=>p,Store.Hash);fixture=BatchEngine.Create(input,output,new());await fixture.RunAsync();
    Assert(fixture.Batch.Photos.All(p=>p.State is not PhotoState.Pending and not PhotoState.Processing),"blocked batch");
    Assert(fixture.Batch.Photos[2].State==PhotoState.NeedsReview,"blank missing from review");Assert(fixture.Batch.Photos[3].State==PhotoState.Error,"corrupt missing from errors");
    foreach(var h in hashes)Assert(Store.Hash(h.Key)==h.Value,"source modified");
    Assert(File.Exists(Path.Combine(output,"crop_labels.json")),"missing legacy labels");
    using var labels=JsonDocument.Parse(File.ReadAllText(Path.Combine(output,"crop_labels.json")));Assert(labels.RootElement.GetProperty("items").EnumerateObject().All(p=>!p.Value.GetProperty("confirmed").GetBoolean()),"automatic output became training truth");
});
await Test("人工补选四角、确认及排除不会混入成功目录",()=>
{
    var item=fixture!.Batch.Photos[2];fixture.Accept(item,[new(260,150),new(539,150),new(539,429),new(260,429)]);Assert(item.State==PhotoState.Confirmed&&item.ManuallyModified,"manual state");
    string saved=fixture.OutputPath(item)!;Assert(File.Exists(saved),"missing confirmed output");fixture.Reject(item,"目标缺失");Assert(!File.Exists(saved),"rejected image still in success folder");Assert(File.Exists(fixture.OutputPath(item)),"archive missing");return Task.CompletedTask;
});
await Test("重开批次、恢复不会覆盖已确认输出",async()=>
{
    var reopened=BatchEngine.Open(fixture!.Batch.Destination);var item=reopened.Batch.Photos[0];string? path=reopened.OutputPath(item),hash=path is null?null:Store.Hash(path);await reopened.RunAsync();if(hash is not null)Assert(Store.Hash(path!)==hash,"resume rewrote crop");
});
await Test("当前照片完成后暂停并安全续跑",async()=>
{
    string input=Path.Combine(root,"pause-input");using var image=Scene();for(int i=0;i<3;i++)Save(image,Path.Combine(input,$"{i}.png"));var batch=BatchEngine.Create(input,Path.Combine(root,"pause-output"),new());
    await batch.RunAsync(new CallbackProgress(p=>{if(p.Photo.State!=PhotoState.Processing)batch.RequestStop();}));Assert(batch.Batch.Photos.Count(p=>p.State==PhotoState.Pending)==2,"pause lost pending state");
    var resumed=BatchEngine.Open(batch.Batch.Destination);await resumed.RunAsync();Assert(resumed.Batch.Photos.All(p=>p.State!=PhotoState.Pending),"resume incomplete");
});
await Test("PNG 已落盘而检查点未提交时可恢复",async()=>
{
    var batch=BatchEngine.Open(fixture!.Batch.Destination);var p=batch.Batch.Photos[1];string target=batch.OutputPath(p)!;string before=Store.Hash(target);
    p.State=PhotoState.Pending;p.Output=null;p.OutputHash=null;Store.WriteJson(batch.Checkpoint,batch.Batch);
    batch=BatchEngine.Open(batch.Batch.Destination);p=batch.Batch.Photos[1];
    await batch.RunAsync();Assert(p.State is PhotoState.AutoAccepted or PhotoState.NeedsReview,"orphan recovery failed");Assert(Store.Hash(target)==before,"recovery replaced saved bytes");
});
await Test("批次锁与冲突文件保护",async()=>
{
    var batch=BatchEngine.Open(fixture!.Batch.Destination);
    using(var locked=new FileStream(Path.Combine(batch.Batch.Destination,".batch.lock"),FileMode.OpenOrCreate,FileAccess.ReadWrite,FileShare.None))
    {
        bool blocked=false;try{await batch.RunAsync();}catch(IOException){blocked=true;}Assert(blocked,"concurrent writer allowed");
    }
    string input=Path.Combine(root,"conflict-input");using var image=Scene();Save(image,Path.Combine(input,"a.png"));var other=BatchEngine.Create(input,Path.Combine(root,"conflict-output"),new());
    string existing=Path.Combine(other.Batch.Destination,"裁剪成功","a.png_cropped.png");Directory.CreateDirectory(Path.GetDirectoryName(existing)!);File.WriteAllText(existing,"untouched");await other.RunAsync();
    Assert(other.Batch.Photos[0].State==PhotoState.Error&&File.ReadAllText(existing)=="untouched","conflicting result overwritten");
});
await Test("源图变化拦截与目录越界拦截",()=>
{
    var item=fixture!.Batch.Photos[0];File.AppendAllText(fixture.SourcePath(item),"changed");bool changed=false;try{fixture.Accept(item,item.Corners!);}catch(IOException){changed=true;}Assert(changed,"changed source accepted");
    bool unsafePath=false;try{Store.SafePath(root,"../escape.png");}catch(InvalidDataException){unsafePath=true;}Assert(unsafePath,"path escape accepted");return Task.CompletedTask;
});
await Test("拍摄失败保留原照片、恢复归档状态并导出表格", async () =>
{
    string input = Path.Combine(root, "capture-input");
    string destination = Path.Combine(root, "capture-output");
    using var image = Scene();
    string source = Save(image, Path.Combine(input, "子目录", "照片,01.png"));
    string hash = Store.Hash(source);
    var batch = BatchEngine.Create(input, destination, new(Recursive: true));
    await batch.RunAsync();
    var photo = batch.Batch.Photos.Single();
    string cropPath = batch.OutputPath(photo)!;
    byte[] cropped = File.ReadAllBytes(cropPath);
    string cropHash = Store.Hash(cropPath);

    batch.Reject(photo, "严重模糊");
    string archive = batch.OutputPath(photo)!;
    Assert(photo.State == PhotoState.Rejected && File.Exists(archive), "missing capture archive");
    Assert(Path.GetRelativePath(destination, archive) == Path.Combine("拍摄失败", "子目录", "照片,01.png"), "archive lost the original path");
    Assert(Store.Hash(archive) == hash && Store.Hash(source) == hash, "archive did not preserve original bytes");
    Assert(!File.Exists(cropPath), "superseded crop is still in the output");

    // Simulate a crash between committing the rejection and removing its old crop.
    batch.RetryErrors();
    Store.WriteBytes(cropPath, cropped);
    photo.PendingRemoval = new OutputRemoval(Path.GetRelativePath(destination, cropPath), cropHash);
    Store.WriteJson(batch.Checkpoint, batch.Batch);
    var reopened = BatchEngine.Open(destination);
    var reopenedPhoto = reopened.Batch.Photos.Single();
    Assert(reopenedPhoto.State == PhotoState.Rejected && reopenedPhoto.PendingRemoval is null, "capture failure did not reload");
    Assert(!File.Exists(cropPath), "reopening did not complete the interrupted removal");
    reopened.Reject(reopenedPhoto, "其他，\"说明\"");
    string report = reopened.ExportCaptureFailures();
    byte[] bytes = File.ReadAllBytes(report);
    Assert(bytes.AsSpan().StartsWith(new byte[] { 0xEF, 0xBB, 0xBF }), "missing Excel UTF-8 BOM");
    var rows = File.ReadAllLines(report);
    Assert(rows.Length == 2 && rows[1].Contains("照片,01.png") && rows[1].Contains("其他，\"\"说明\"\"") &&
        rows[1].Contains("原照片副本") && rows[1].Contains(hash), "CSV did not preserve fields or escaped quotes");
});
await Test("版本冲突、逐张日志、覆盖确认及 SHA-256 复核", () =>
{
    string input = Path.Combine(root, "version-input");
    using var scene = Scene();
    Save(scene, Path.Combine(input, "a.png"));
    Save(scene, Path.Combine(input, "b.png"));
    PixelPoint[] corners = [new(260,150),new(539,150),new(539,429),new(260,429)];
    var first = BatchEngine.Create(input, Path.Combine(root, "version-output"), new());
    var stale = BatchEngine.Open(first.Batch.Destination);
    first.Reject(first.Batch.Photos[0], "严重模糊");
    bool refresh = false;
    try { stale.Reject(stale.Batch.Photos[1], "反光遮挡"); } catch (BatchChangedException) { refresh = true; }
    Assert(refresh, "stale window rewrote the batch");
    var reopened = BatchEngine.Open(first.Batch.Destination);
    Assert(reopened.Batch.Photos[0].State == PhotoState.Rejected && reopened.Batch.Photos[1].State == PhotoState.Pending, "journal was not replayed");
    var second = reopened.Batch.Photos[1];
    reopened.Accept(second, corners);
    string saved = reopened.OutputPath(second)!;
    File.AppendAllText(saved, "external change");
    string external = Store.Hash(saved);
    CropOverwrite? approval = null;
    try { reopened.Accept(second, corners); }
    catch (OutputConflictException ex) { approval = new CropOverwrite(ex.TargetPath, ex.ExistingHash); }
    Assert(approval is not null && Store.Hash(saved) == external, "unapproved overwrite");
    File.AppendAllText(saved, "newer change");
    bool declined = false;
    try { reopened.Accept(second, corners, approval); } catch (OutputConflictException ex) { approval = new(ex.TargetPath, ex.ExistingHash); declined = true; }
    Assert(declined, "approval applied to a different hash");
    reopened.Accept(second, corners, approval);
    Assert(second.State == PhotoState.Confirmed && Store.Hash(saved) == second.OutputHash, "approved overwrite did not save");
    return Task.CompletedTask;
});
await Test("恢复日志中已经登记但尚未来得及写入的图像", () =>
{
    string input = Path.Combine(root, "prepared-input"), destination = Path.Combine(root, "prepared-output");
    using var scene = Scene();
    string source = Save(scene, Path.Combine(input, "test.png"));
    var batch = BatchEngine.Create(input, destination, new());
    var photo = batch.Batch.Photos.Single();
    string stage = Path.Combine(".screen-crop-pending", "simulated.bin");
    string result = Path.Combine("裁剪成功", "test.png_cropped.png");
    string hash = Store.Hash(source);
    Store.WriteBytes(Path.Combine(destination, stage), File.ReadAllBytes(source));
    photo.State = PhotoState.Confirmed;
    photo.SourceHash = hash;
    photo.Output = result;
    photo.OutputHash = hash;
    photo.PendingWrite = new OutputCommit(stage, result, hash, null);
    Store.WriteJson(Path.Combine(destination, ".screen-crop-journal", "00000000000000000001.json"), photo);
    var recovered = BatchEngine.Open(destination).Batch.Photos.Single();
    Assert(recovered.PendingWrite is null && recovered.State == PhotoState.Confirmed &&
        Store.Hash(Path.Combine(destination, result)) == hash && !File.Exists(Path.Combine(destination, stage)), "prepared file was not committed on open");
    return Task.CompletedTask;
});
await Test("失败空表、已重裁历史、报表锁定及相同照片独立导出", () =>
{
    string input = Path.Combine(root, "report-input");
    using var scene = Scene();
    var a = Save(scene, Path.Combine(input, "a.png"));
    File.Copy(a, Path.Combine(input, "b.png"));
    PixelPoint[] corners = [new(260,150),new(539,150),new(539,429),new(260,429)];
    var batch = BatchEngine.Create(input, Path.Combine(root, "report-output"), new());
    var firstPhoto = batch.Batch.Photos[0];
    batch.Reject(firstPhoto, "目标缺失");
    string active = batch.ExportCaptureFailures();
    string archive = batch.OutputPath(firstPhoto)!;
    using (var locked = new FileStream(Path.Combine(batch.Batch.Destination, "crop_report.csv"), FileMode.Open, FileAccess.Read, FileShare.Read))
    {
        batch.Accept(firstPhoto, corners);
        Assert(firstPhoto.State == PhotoState.Confirmed && File.Exists(batch.OutputPath(firstPhoto)) &&
            batch.ReportWarning?.Contains("表格待重试") == true, "report lock interrupted image save");
    }
    batch.Accept(batch.Batch.Photos[1], corners);
    Assert(batch.ReportWarning is null && File.Exists(archive), "history archive or report recovery missing");
    Assert(batch.FailureReportOutdated() && File.ReadAllLines(active).Length == 2, "outdated report not detected");
    batch.ExportCaptureFailures();
    Assert(File.ReadAllLines(active).Length == 1 && !batch.FailureReportOutdated(), "empty report did not replace obsolete rows");
    var history = File.ReadAllText(batch.ExportCaptureFailures(true));
    Assert(history.Contains("已重裁") && history.Contains("目标缺失"), "resolution history missing");
    using var labels = JsonDocument.Parse(File.ReadAllText(Path.Combine(batch.Batch.Destination, "crop_labels.json")));
    var paths = labels.RootElement.GetProperty("items");
    Assert(paths.TryGetProperty("a.png", out var one) && paths.TryGetProperty("b.png", out _) &&
        one.GetProperty("source_sha256").GetString() == firstPhoto.SourceHash, "same-content photos were merged");
    return Task.CompletedTask;
});
await Test("备份、搬家校验、按文件导入与 16 位 PNG", () =>
{
    string input = Path.Combine(root, "bundle-input");
    string destination = Path.Combine(root, "bundle-output");
    using var scene = new Mat(90, 140, MatType.CV_16UC3, new Scalar(18000, 32000, 44000));
    string source = Save(scene, Path.Combine(input, "nested", "selected.png"));
    Save(scene, Path.Combine(input, "nested", "ignored.png"));
    var batch = BatchEngine.CreateFiles([source], destination, new(Square: false, OutputSize: 80,
        KeepFolders: false, NameTemplate: "{name}-export", PreserveDepth: true));
    var photo = batch.Batch.Photos.Single();
    batch.Accept(photo, [new(8,8),new(130,8),new(130,77),new(8,77)], rotation: 90);
    string file = batch.OutputPath(photo)!;
    using var result = Store.LoadImage(file, preserveDepth: true);
    Assert(Path.GetFileName(file) == "selected-export.png" && result.Depth() == MatType.CV_16U && result.Height == 80 &&
        result.Width < result.Height, "format, naming, aspect or rotation mismatch");
    string zip = Path.Combine(root, "batch-backup.zip");
    batch.ExportBackup(zip);
    string expanded = Path.Combine(root, "restored-backup");
    System.IO.Compression.ZipFile.ExtractToDirectory(zip, expanded);
    var restored = BatchEngine.Relocate(Path.Combine(expanded, "results"), Path.Combine(expanded, "originals"));
    var restoredPhoto = restored.Batch.Photos.Single();
    Assert(Store.Hash(restored.SourcePath(restoredPhoto)) == photo.SourceHash &&
        Store.Hash(restored.OutputPath(restoredPhoto)!) == photo.OutputHash, "backup relocation lost bytes");
    return Task.CompletedTask;
});
await Test("扩展检测覆盖等亮彩色框、贴边近拍和斜拍候选", () =>
{
    var detector = new FrameDetector();
    var fixtures = new[] {
        ("等亮色差", new Scalar(210,115,90), new Scalar(25,90,210),
            new[] { new Point(160,135), new Point(594,135), new Point(594,505), new Point(160,505) }),
        ("浅色边界", new Scalar(177,177,177), new Scalar(208,208,208),
            new[] { new Point(160,135), new Point(594,135), new Point(594,505), new Point(160,505) }),
        ("贴边近拍", new Scalar(225,225,225), new Scalar(42,42,42),
            new[] { new Point(9,12), new Point(776,12), new Point(776,615), new Point(9,615) }),
        ("大角度", new Scalar(220,220,220), new Scalar(45,45,45),
            new[] { new Point(91,104), new Point(600,61), new Point(710,493), new Point(260,557) })
    };
    foreach (var (name, background, fill, polygon) in fixtures)
    {
        using var image = new Mat(640, 800, MatType.CV_8UC3, background);
        Cv2.FillConvexPoly(image, polygon, fill);
        var found = detector.Detect(image, square: false, mode: DetectionMode.Difficult);
        var expected = polygon.Select(point => new Point2f(point.X, point.Y)).ToArray();
        var candidates = (found.Corners is null ? Array.Empty<Point2f[]>() : new[] { found.Corners })
            .Concat(found.Alternatives ?? []).ToArray();
        double iou = candidates.Select(candidate => FrameDetector.Overlap(candidate, expected)).DefaultIfEmpty(0).Max();
        Console.WriteLine($"{name} IoU={iou:F3} auto={found.Automatic}");
        Assert(iou > .80 && !found.Automatic, name + " did not enter review with an adequate proposal");
    }
    return Task.CompletedTask;
});
await Test("反光和内部强轮廓的错误候选不得自动通过", () =>
{
    var detector = new FrameDetector();
    using var scene = Scene();
    using var reflected = scene.Clone();
    Cv2.Line(reflected, new Point(224, 94), new Point(605, 460), new Scalar(251, 251, 251), 40);
    using var interior = scene.Clone();
    Cv2.Rectangle(interior, new Rect(308, 203, 170, 170), new Scalar(13, 13, 13), 8);
    foreach (var (name, image) in new[] { ("反光遮挡", reflected), ("内部强轮廓", interior) })
    {
        var result = detector.Detect(image, mode: DetectionMode.Difficult);
        double iou = result.Corners is null ? 0 : FrameDetector.Overlap(result.Corners,
            [new(260,150),new(539,150),new(539,429),new(260,429)]);
        Console.WriteLine($"{name} IoU={iou:F3} auto={result.Automatic}");
        Assert(!result.Automatic || iou > .85, "bad automatic candidate: " + name);
    }
    return Task.CompletedTask;
});
Console.WriteLine($"{passed} checks passed. Artifacts: {root}");
sealed class CallbackProgress(Action<BatchProgress> callback):IProgress<BatchProgress>{public void Report(BatchProgress p)=>callback(p);}
sealed record EvalCase(string Image,double[][] Quad,bool Square=true,string Split="diagnostic",double BaselineIou=0);
