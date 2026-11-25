using OpenCvSharp;

namespace Crop.Core;

public sealed record FrameEvidence(double MinSupport, double MeanSupport, double MinContrast, double ExteriorNoise, double ScoreGap, double AspectError, int DetectionSize, int CandidateCount, bool Ambiguous, int ThinFrameSides);
public sealed record FrameResult(Point2f[]? Corners, bool Automatic, string[] Reasons, FrameEvidence? Evidence);

// No network, model weights, learned features, image restoration, or decoder feedback.
public sealed class FrameDetector
{
    private sealed record Line(double Slope, double Intercept, double Position, double Low, double High, double Covered);
    private sealed record Candidate(Point2f[] Quad, double Score, double MinSupport, double MeanSupport, double Contrast, double Noise, double Aspect, int ThinFrameSides);
    private sealed class Pixels(Mat image)
    {
        public readonly int Width = image.Width, Height = image.Height;
        private readonly byte[] data = Read(image);
        static byte[] Read(Mat mat) { var bytes = new byte[mat.Rows*mat.Cols]; int rows=mat.Rows; for(int y=0;y<rows;y++) System.Runtime.InteropServices.Marshal.Copy(mat.Ptr(y),bytes,y*mat.Cols,mat.Cols); return bytes; }
        public double At(double x,double y)
        {
            if(x<0||y<0||x>=Width-1||y>=Height-1) return double.NaN;
            int ix=(int)x,iy=(int)y; double a=x-ix,b=y-iy;
            return data[iy*Width+ix]*(1-a)*(1-b)+data[iy*Width+ix+1]*a*(1-b)+data[(iy+1)*Width+ix]*(1-a)*b+data[(iy+1)*Width+ix+1]*a*b;
        }
    }
    public FrameResult Detect(Mat image, bool square = true, CancellationToken cancellation = default)
    {
        cancellation.ThrowIfCancellationRequested();
        var first = DetectAt(image,square,1100,cancellation);
        // Cross-scale agreement is an independent geometry check even for strong edges.
        if(Math.Max(image.Width,image.Height) <= 1200) return first;
        var second = DetectAt(image,square,1600,cancellation);
        if(second.Corners is null) return first;
        if(first.Corners is null) return second;
        double iou = Overlap(first.Corners,second.Corners);
        if(iou < .96) return second with { Automatic=false, Reasons=second.Reasons.Append("不同检测尺度的边界不一致").Distinct().ToArray() };
        return second;
    }
    private FrameResult DetectAt(Mat image,bool square,int size,CancellationToken cancellation)
    {
        double scale = Math.Min(1,size/(double)Math.Max(image.Width,image.Height));
        using var small=new Mat(); using var gray=new Mat();
        Cv2.Resize(image,small,new Size((int)Math.Round(image.Width*scale),(int)Math.Round(image.Height*scale)),0,0,InterpolationFlags.Area);
        Cv2.CvtColor(small,gray,ColorConversionCodes.BGR2GRAY);
        var pixels = new Pixels(gray);
        var ranked = Rank(Proposals(gray,cancellation),pixels,square,cancellation);
        if(ranked.Count==0 || ranked[0].MinSupport < .82)
        {
            using var blurred=new Mat(); using var enhanced=new Mat();
            Cv2.GaussianBlur(gray,blurred,new Size(0,0),2);
            Cv2.AddWeighted(gray,3.5,blurred,-2.5,0,enhanced);
            ranked.AddRange(Rank(Proposals(enhanced,cancellation),pixels,square,cancellation));
        }
        if(ranked.Count==0) return new(null,false,["没有找到四边完整的目标边界"],null);
        ranked.Sort((a,b)=>b.Score.CompareTo(a.Score));
        var best=ranked[0];
        var distinct = ranked.Skip(1).FirstOrDefault(c=>Overlap(best.Quad,c.Quad)<.85);
        double gap=distinct is null ? 1 : best.Score-distinct.Score;
        bool ambiguous=distinct is not null && gap<.16;
        var reasons=new List<string>();
        if(best.MinSupport<.82) reasons.Add("部分边界断裂或拖影较重");
        if(best.Contrast<12) reasons.Add("边界与背景对比不足");
        if(best.Noise>15) reasons.Add("边框外侧存在明显纹理干扰");
        if(square && best.Aspect>.16) reasons.Add("目标形状偏离正方形，需检查完整性");
        if(best.ThinFrameSides<2) reasons.Add("缺少细边框证据，可能选中了图片内部内容");
        if(ambiguous) reasons.Add("存在多个接近的边界候选");
        var q=Inset(best.Quad,.65f).Select(p=>new Point2f((float)(p.X/scale),(float)(p.Y/scale))).ToArray();
        try { q=Store.ValidateCorners(q,image.Width,image.Height); }
        catch(ArgumentException){return new(null,false,["边界四角几何无效"],null);}
        var evidence=new FrameEvidence(best.MinSupport,best.MeanSupport,best.Contrast,best.Noise,gap,best.Aspect,size,ranked.Count,ambiguous,best.ThinFrameSides);
        return new(q,reasons.Count==0,reasons.ToArray(),evidence);
    }
    private List<Candidate> Rank(IEnumerable<Point2f[]> quads,Pixels pixels,bool square,CancellationToken cancellation)
    {
        var result=new List<Candidate>(); var seen=new HashSet<string>();
        foreach(var q in quads)
        {
            cancellation.ThrowIfCancellationRequested();
            if(!Plausible(q,pixels.Width,pixels.Height))continue;
            string key=string.Join(',',q.SelectMany(p=>new[]{(int)Math.Round(p.X/3),(int)Math.Round(p.Y/3)}));
            if(!seen.Add(key))continue;
            var score=Score(q,pixels,square);
            if(score is not null)result.Add(score);
        }
        return result;
    }
    private static Candidate? Score(Point2f[] q,Pixels px,bool square)
    {
        var supports=new List<double>(); var strengths=new List<double>(); var noises=new List<double>(); int thinSides=0;
        for(int side=0;side<4;side++)
        {
            var a=q[side];var b=q[(side+1)%4];double dx=b.X-a.X,dy=b.Y-a.Y,len=Math.Sqrt(dx*dx+dy*dy),nx=-dy/len,ny=dx/len;
            var outside=new double[48];var contrast=new double[48];var recovery=new double[48];
            for(int j=0;j<48;j++)
            {
                double t=.07+.86*j/47,x=a.X+t*dx,y=a.Y+t*dy;
                double[] ex={px.At(x-20*nx,y-20*ny),px.At(x-13*nx,y-13*ny),px.At(x-7*nx,y-7*ny)};
                outside[j]=Median(ex);
                double darkest=double.PositiveInfinity;
                for(int off=-3;off<=4;off++)darkest=Math.Min(darkest,px.At(x+off*nx,y+off*ny));
                contrast[j]=outside[j]-darkest; recovery[j]=Math.Max(px.At(x+9*nx,y+9*ny),px.At(x+15*nx,y+15*ny))-darkest;
            }
            if(outside.Any(v=>!double.IsFinite(v))||contrast.Any(v=>!double.IsFinite(v)))return null;
            double median=Median(outside),noise=Median(outside.Select(v=>Math.Abs(v-median)).ToArray());
            double threshold=Math.Max(5,noise*1.5);bool[] supported=contrast.Select(v=>v>threshold).ToArray();
            double support=supported.Count(v=>v)/48d;
            int gap=0,longest=0;foreach(bool yes in supported){gap=yes?0:gap+1;longest=Math.Max(longest,gap);}
            double strength=Percentile(contrast,.35); if(recovery.Count(v=>v>Math.Max(7,noise*1.8))/48d>=.45)thinSides++;
            if(support<.56||Percentile(outside,.25)<65||noise>27||longest>16||strength<5)return null;
            supports.Add(support);strengths.Add(strength);noises.Add(noise);
        }
        var lengths=Enumerable.Range(0,4).Select(i=>Distance(q[i],q[(i+1)%4])).ToArray();
        double aspect=Math.Abs(Math.Log((lengths[0]+lengths[2])/(lengths[1]+lengths[3])));
        double area=Math.Abs(Cv2.ContourArea(q))/(px.Width*px.Height);
        double score=supports.Average()+strengths.Average(s=>Math.Min(s/50,1))-.012*noises.Average()+.50*Math.Log(area)-(square?.6*aspect:0);
        return new(q,score,supports.Min(),supports.Average(),strengths.Min(),noises.Max(),aspect,thinSides);
    }
    private IEnumerable<Point2f[]> Proposals(Mat gray,CancellationToken cancellation)
    {
        var result=new List<Point2f[]>();
        foreach(double threshold in new[]{35d,70,105,140,170})
        {
            cancellation.ThrowIfCancellationRequested();
            using var binary=new Mat(); using var kernel=Cv2.GetStructuringElement(MorphShapes.Rect,new Size(3,3));
            Cv2.Threshold(gray,binary,threshold,255,ThresholdTypes.BinaryInv);
            Cv2.MorphologyEx(binary,binary,MorphTypes.Close,kernel);
            Cv2.FindContours(binary,out Point[][] contours,out _,RetrievalModes.List,ContourApproximationModes.ApproxSimple);
            foreach(var contour in contours.OrderByDescending(c=>Math.Abs(Cv2.ContourArea(c))).Take(70))
            {
                var hull=Cv2.ConvexHull(contour);
                double area=Math.Abs(Cv2.ContourArea(hull));
                if(area<gray.Total()*.008||area>gray.Total()*.65)continue;
                foreach(double epsilon in new[]{.015,.025})
                {
                    var poly=Cv2.ApproxPolyDP(hull,Cv2.ArcLength(hull,true)*epsilon,true);
                    if(poly.Length==4)result.Add(Order(poly.Select(p=>new Point2f(p.X,p.Y)).ToArray()));
                }
            }
        }
        using var detector=LineSegmentDetector.Create(LineSegmentDetectorModes.RefineStd);
        using var lines=new Mat(); detector.Detect(gray,lines);
        var horizontal=MergeLines(lines,gray.Width,gray.Height,true);
        var vertical=MergeLines(lines,gray.Width,gray.Height,false);
        var hp=Pairs(horizontal,gray.Size());var vp=Pairs(vertical,gray.Size());
        foreach(var (top,bottom) in hp)
        {
            cancellation.ThrowIfCancellationRequested();
            foreach(var (left,right) in vp)
            {
                var q=new[]{Intersect(top,left),Intersect(top,right),Intersect(bottom,right),Intersect(bottom,left)};
                if(!Plausible(q,gray.Width,gray.Height))continue;
                if(Cover(top,q[0].X,q[1].X)<.58||Cover(bottom,q[3].X,q[2].X)<.58||Cover(left,q[0].Y,q[3].Y)<.58||Cover(right,q[1].Y,q[2].Y)<.58)continue;
                result.Add(q);
            }
        }
        return result;
    }
    private static List<Line> MergeLines(Mat lines,int width,int height,bool horizontal)
    {
        var raw=new List<Line>();double center=(horizontal?width:height)/2d;
        int lineCount=lines.Rows; for(int i=0;i<lineCount;i++)
        {
            var v=lines.At<Vec4f>(i);double x1=v.Item0,y1=v.Item1,x2=v.Item2,y2=v.Item3;
            double dx=x2-x1,dy=y2-y1,len=Math.Sqrt(dx*dx+dy*dy);
            if(len<Math.Max(18,Math.Max(width,height)*.018)||(Math.Abs(dx)>=Math.Abs(dy))!=horizontal)continue;
            if(!horizontal){(x1,y1)=(y1,x1);(x2,y2)=(y2,x2);}
            double slope=(y2-y1)/(x2-x1),intercept=y1-slope*x1;
            raw.Add(new(slope,intercept,slope*center+intercept,Math.Min(x1,x2),Math.Max(x1,x2),len));
        }
        var groups=new List<List<Line>>();
        foreach(var line in raw.OrderByDescending(l=>l.Covered))
        {
            var group=groups.FirstOrDefault(g=>Math.Abs(g[0].Position-line.Position)<3.5&&Math.Abs(Math.Atan(g[0].Slope)-Math.Atan(line.Slope))<.035);
            if(group is null){group=[];groups.Add(group);}group.Add(line);
        }
        return groups.Select(g=>
        {
            double weight=g.Sum(l=>l.Covered),slope=g.Sum(l=>l.Slope*l.Covered)/weight,position=g.Sum(l=>l.Position*l.Covered)/weight;
            double end=double.NegativeInfinity,covered=0;foreach(var l in g.OrderBy(l=>l.Low)){covered+=Math.Max(0,l.High-Math.Max(l.Low,end));end=Math.Max(end,l.High);}
            return new Line(slope,position-slope*center,position,g.Min(l=>l.Low),g.Max(l=>l.High),covered);
        }).Where(l=>l.Covered>Math.Max(35,Math.Max(width,height)*.04)).OrderByDescending(l=>l.Covered).Take(18).ToList();
    }
    private static List<(Line,Line)> Pairs(List<Line> lines,Size size)
    {
        var pairs=new List<(Line,Line)>();
        for(int a=0;a<lines.Count;a++)for(int b=a+1;b<lines.Count;b++)
            if(Math.Abs(lines[a].Position-lines[b].Position)>Math.Max(40,Math.Max(size.Width,size.Height)*.05)&&Math.Abs(Math.Atan(lines[a].Slope)-Math.Atan(lines[b].Slope))<.25)
                pairs.Add(lines[a].Position<lines[b].Position?(lines[a],lines[b]):(lines[b],lines[a]));
        return pairs;
    }
    private static Point2f Intersect(Line h,Line v){double d=1-h.Slope*v.Slope;if(Math.Abs(d)<.05)return new(float.NaN,float.NaN);double x=(v.Slope*h.Intercept+v.Intercept)/d;return new((float)x,(float)(h.Slope*x+h.Intercept));}
    private static double Cover(Line l,double a,double b)=>Math.Max(0,Math.Min(l.High,Math.Max(a,b))-Math.Max(l.Low,Math.Min(a,b)))/Math.Max(1,Math.Abs(a-b));
    private static bool Plausible(Point2f[] q,int width,int height)
    {
        if(q.Any(p=>!float.IsFinite(p.X)||!float.IsFinite(p.Y)||p.X<23||p.Y<23||p.X>=width-23||p.Y>=height-23))return false;
        var sides=Enumerable.Range(0,4).Select(i=>Distance(q[i],q[(i+1)%4])).ToArray();
        if(sides.Min()<40||sides.Max()>sides.Min()*4)return false;
        for(int i=0;i<4;i++){var a=q[i];var b=q[(i+1)%4];var c=q[(i+2)%4];if((b.X-a.X)*(c.Y-b.Y)-(b.Y-a.Y)*(c.X-b.X)<=0)return false;}
        double area=Math.Abs(Cv2.ContourArea(q));return area>width*height*.008&&area<width*height*.65;
    }
    private static Point2f[] Order(Point2f[] q){float x=q.Average(p=>p.X),y=q.Average(p=>p.Y);q=q.OrderBy(p=>Math.Atan2(p.Y-y,p.X-x)).ToArray();int start=Array.FindIndex(q,p=>p.X+p.Y==q.Min(v=>v.X+v.Y));return Enumerable.Range(0,4).Select(i=>q[(start+i)%4]).ToArray();}
    private static Point2f[] Inset(Point2f[] q,float distance)
    {
        var a=new Point2f[4];var d=new Point2f[4];
        for(int i=0;i<4;i++){var p=q[i];var next=q[(i+1)%4];double len=Distance(p,next);d[i]=next-p;a[i]=p+new Point2f((float)(-(next.Y-p.Y)/len*distance),(float)((next.X-p.X)/len*distance));}
        var result=new Point2f[4];
        for(int i=0;i<4;i++){int j=(i+3)%4;double cross=d[j].X*d[i].Y-d[j].Y*d[i].X;if(Math.Abs(cross)<1e-6)return q;var delta=a[i]-a[j];double t=(delta.X*d[i].Y-delta.Y*d[i].X)/cross;result[i]=a[j]+d[j]*(float)t;}
        return result;
    }
    public static double Overlap(Point2f[] a,Point2f[] b){double intersection=Cv2.IntersectConvexConvex(a,b,out _);double union=Math.Abs(Cv2.ContourArea(a))+Math.Abs(Cv2.ContourArea(b))-intersection;return union>0?intersection/union:0;}
    private static double Distance(Point2f a,Point2f b)=>Math.Sqrt(Math.Pow(a.X-b.X,2)+Math.Pow(a.Y-b.Y,2));
    private static double Median(double[] v)=>Percentile(v,.5);
    private static double Percentile(double[] values,double p){var sorted=values.Order().ToArray();return sorted[(int)Math.Round((sorted.Length-1)*p)];}
}
