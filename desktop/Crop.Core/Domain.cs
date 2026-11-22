using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using OpenCvSharp;

namespace Crop.Core;

public enum PhotoState { Pending, Processing, AutoAccepted, NeedsReview, Confirmed, Rejected, Error }
public sealed record PixelPoint(double X, double Y)
{
    public Point2f ToCv() => new((float)X, (float)Y);
    public static PixelPoint[] From(IEnumerable<Point2f> points) => points.Select(p => new PixelPoint(p.X, p.Y)).ToArray();
}
public sealed record CropOptions(bool Square = true, bool Recursive = false, int OutputSize = 0, int InsetPixels = 0);
public sealed class PhotoRecord
{
    public string RelativePath { get; set; } = "";
    public string SourceHash { get; set; } = "";
    public int Width { get; set; }
    public int Height { get; set; }
    public PhotoState State { get; set; }
    public PixelPoint[]? Corners { get; set; }
    public string? Output { get; set; }
    public string? OutputHash { get; set; }
    public string[] Reasons { get; set; } = [];
    public FrameEvidence? Evidence { get; set; }
    public bool ManuallyModified { get; set; }
    public DateTimeOffset? UpdatedAt { get; set; }
}
public sealed class BatchSnapshot
{
    public int Schema { get; set; } = 1;
    public string Version { get; set; } = "1.0.0";
    public string Detector { get; set; } = "frame-multiscale-v1";
    public string Source { get; set; } = "";
    public string Destination { get; set; } = "";
    public CropOptions Options { get; set; } = new();
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.Now;
    public List<PhotoRecord> Photos { get; set; } = [];
}
public static class Store
{
    public static readonly JsonSerializerOptions Json = new() { WriteIndented = true, PropertyNamingPolicy = JsonNamingPolicy.CamelCase, Converters = { new JsonStringEnumConverter() } };
    public static void WriteJson<T>(string path, T value) => WriteBytes(path, JsonSerializer.SerializeToUtf8Bytes(value, Json));
    public static void WriteBytes(string path, byte[] bytes)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(path))!);
        string temp = path + "." + Guid.NewGuid().ToString("N") + ".tmp";
        try
        {
            using (var stream = new FileStream(temp, FileMode.CreateNew, FileAccess.Write, FileShare.None)) { stream.Write(bytes); stream.Flush(true); }
            File.Move(temp, path, true);
        }
        finally { if (File.Exists(temp)) File.Delete(temp); }
    }
    public static string Hash(string path) { using var f = File.OpenRead(path); return Convert.ToHexString(SHA256.HashData(f)).ToLowerInvariant(); }
    public static string SafePath(string root, string relative)
    {
        var full = Path.GetFullPath(Path.Combine(root, relative));
        if (Path.IsPathRooted(relative) || !full.StartsWith(Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("记录中的路径超出批次目录。");
        return full;
    }
    public static string OutputName(string relative) => relative + "_cropped.png";
    public static Mat LoadImage(string path)
    {
        var mat = Cv2.ImDecode(File.ReadAllBytes(path), ImreadModes.Color);
        if (mat.Empty()) { mat.Dispose(); throw new InvalidDataException("图片无法完整解码。"); }
        return mat;
    }
    public static Point2f[] ValidateCorners(IEnumerable<Point2f> points, int width, int height)
    {
        var q = points.ToArray();
        if (q.Length != 4 || q.Any(p => !float.IsFinite(p.X) || !float.IsFinite(p.Y) || p.X < 0 || p.Y < 0 || p.X > width - 1 || p.Y > height - 1)) throw new ArgumentException("请选择原图范围内的四个角点。");
        var center = new Point2f(q.Average(p => p.X), q.Average(p => p.Y));
        q = q.OrderBy(p => Math.Atan2(p.Y - center.Y, p.X - center.X)).ToArray();
        int first = Array.FindIndex(q, p => p.X + p.Y == q.Min(v => v.X + v.Y));
        q = Enumerable.Range(0, 4).Select(i => q[(i + first) % 4]).ToArray();
        if (!Cv2.IsContourConvex(q.Select(p => new Point((int)Math.Round(p.X), (int)Math.Round(p.Y))).ToArray()) || Math.Abs(Cv2.ContourArea(q)) < 64) throw new ArgumentException("四角必须构成有效凸四边形。");
        return q;
    }
    public static Mat Rectify(Mat image, Point2f[] corners, CropOptions options)
    {
        var q = ValidateCorners(corners, image.Width, image.Height);
        double D(Point2f a, Point2f b) => Math.Sqrt(Math.Pow(a.X-b.X,2)+Math.Pow(a.Y-b.Y,2));
        int w = Math.Max(8, (int)Math.Round((D(q[0],q[1])+D(q[3],q[2]))/2));
        int h = Math.Max(8, (int)Math.Round((D(q[0],q[3])+D(q[1],q[2]))/2));
        if(options.Square) w = h = Math.Max(w,h);
        using var transform = Cv2.GetPerspectiveTransform(q, new Point2f[] { new(0,0), new(w-1,0), new(w-1,h-1), new(0,h-1) });
        using var warped = new Mat();
        Cv2.WarpPerspective(image, warped, transform, new Size(w,h), InterpolationFlags.Linear, BorderTypes.Replicate);
        int inset = options.InsetPixels;
        if(inset < 0 || Math.Min(w,h) <= 2*inset+4) throw new ArgumentException("内切像素过大。");
        using var region = new Mat(warped, new Rect(inset,inset,w-2*inset,h-2*inset));
        if(options.OutputSize == 0) return region.Clone();
        var result = new Mat();
        Cv2.Resize(region,result,new Size(options.OutputSize,options.OutputSize),0,0,InterpolationFlags.Area);
        return result;
    }
    public static byte[] Thumbnail(Mat image, int longest = 240)
    {
        using var small = new Mat();
        double scale = Math.Min(1, longest / (double)Math.Max(image.Width,image.Height));
        Cv2.Resize(image,small,new Size(Math.Max(1,(int)(image.Width*scale)),Math.Max(1,(int)(image.Height*scale))),0,0,InterpolationFlags.Area);
        Cv2.ImEncode(".jpg",small,out var bytes,new int[]{(int)ImwriteFlags.JpegQuality,85}); return bytes;
    }
}
