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
    Console.WriteLine($"Batch: {batch.Batch.Photos.Count}, auto: {batch.Batch.Photos.Count(p=>p.State==PhotoState.AutoAccepted)}, review: {batch.Batch.Photos.Count(p=>p.State==PhotoState.NeedsReview)}");return;
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
Console.WriteLine($"{passed} checks passed. Artifacts: {root}");
sealed class CallbackProgress(Action<BatchProgress> callback):IProgress<BatchProgress>{public void Report(BatchProgress p)=>callback(p);}
sealed record EvalCase(string Image,double[][] Quad,bool Square=true,string Split="diagnostic",double BaselineIou=0);
