using System.Windows;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using Crop.Core;
using Point = System.Windows.Point;

namespace Crop.Desktop;
public sealed class CornerSurface : FrameworkElement
{
    private BitmapSource? image;
    private readonly List<PixelPoint> points=[];
    private double zoom=1;
    private Vector pan;
    private int dragging=-1;
    private bool panning;
    private Point last;
    public IReadOnlyList<PixelPoint> Points=>points;
    public bool IsInteracting=>dragging>=0||panning;
    public event EventHandler? PointsChanged;
    public CornerSurface(){Focusable=true;ClipToBounds=true;Cursor=Cursors.Cross;}
    public void SetImage(BitmapSource bitmap,PixelPoint[]? corners){image=bitmap;points.Clear();if(corners is not null)points.AddRange(corners);Fit();}
    public void SetPoints(IEnumerable<PixelPoint> corners){points.Clear();points.AddRange(corners);InvalidateVisual();}
    public void Clear(){image=null;points.Clear();InvalidateVisual();}
    public void Fit(){zoom=1;pan=new();InvalidateVisual();}
    public void Undo(){if(points.Count>0){points.RemoveAt(points.Count-1);InvalidateVisual();PointsChanged?.Invoke(this,EventArgs.Empty);}}
    private (double Scale,double X,double Y) View()
    {
        if(image is null)return(1,0,0);double scale=Math.Min(Math.Max(1,ActualWidth-52)/image.PixelWidth,Math.Max(1,ActualHeight-70)/image.PixelHeight)*zoom;
        return(scale,(ActualWidth-image.PixelWidth*scale)/2+pan.X,(ActualHeight-image.PixelHeight*scale)/2+pan.Y);
    }
    private Point Screen(PixelPoint p){var (s,x,y)=View();return new(x+p.X*s,y+p.Y*s);}
    private PixelPoint? Original(Point p){if(image is null)return null;var(s,x,y)=View();double ix=(p.X-x)/s,iy=(p.Y-y)/s;return ix>=0&&iy>=0&&ix<image.PixelWidth&&iy<image.PixelHeight?new(ix,iy):null;}
    protected override void OnRender(DrawingContext dc)
    {
        base.OnRender(dc);dc.DrawRectangle(new SolidColorBrush(Color.FromRgb(30,38,36)),null,new Rect(0,0,ActualWidth,ActualHeight));
        if(image is null)return;var(s,x,y)=View();dc.DrawImage(image,new Rect(x,y,image.PixelWidth*s,image.PixelHeight*s));
        if(points.Count>1)
        {
            var geometry=new StreamGeometry();using(var c=geometry.Open()){c.BeginFigure(Screen(points[0]),points.Count==4,points.Count==4);c.PolyLineTo(points.Skip(1).Select(Screen).ToArray(),true,false);}
            dc.DrawGeometry(points.Count==4?new SolidColorBrush(Color.FromArgb(18,200,230,170)):null,new Pen(new SolidColorBrush(Color.FromRgb(225,239,184)),1.5),geometry);
        }
        for(int i=0;i<points.Count;i++)
        {
            var p=Screen(points[i]);dc.DrawEllipse(new SolidColorBrush(Color.FromRgb(239,190,97)),new Pen(new SolidColorBrush(Color.FromRgb(35,45,39)),2),p,6,6);
            var text=new FormattedText((i+1).ToString(),System.Globalization.CultureInfo.InvariantCulture,FlowDirection.LeftToRight,new Typeface("Segoe UI"),12,Brushes.White,VisualTreeHelper.GetDpi(this).PixelsPerDip);dc.DrawText(text,new Point(p.X+10,p.Y-20));
        }
    }
    protected override void OnMouseDown(MouseButtonEventArgs e)
    {
        if(image is null)return;Focus();last=e.GetPosition(this);
        if(e.ChangedButton==MouseButton.Middle||(e.ChangedButton==MouseButton.Left&&Keyboard.IsKeyDown(Key.Space))){panning=true;CaptureMouse();e.Handled=true;return;}
        if(e.ChangedButton!=MouseButton.Left)return;
        for(int i=0;i<points.Count;i++)if((Screen(points[i])-last).Length<13){dragging=i;CaptureMouse();e.Handled=true;return;}
        var original=Original(last);if(original is null)return;if(points.Count==4)points.Clear();points.Add(original);InvalidateVisual();PointsChanged?.Invoke(this,EventArgs.Empty);e.Handled=true;
    }
    protected override void OnMouseMove(MouseEventArgs e)
    {
        var p=e.GetPosition(this);
        if(panning){pan+=p-last;last=p;InvalidateVisual();return;}
        if(dragging<0)return;var original=Original(p);if(original is not null){points[dragging]=original;InvalidateVisual();}
    }
    protected override void OnMouseUp(MouseButtonEventArgs e)
    {
        bool changed=dragging>=0;dragging=-1;panning=false;ReleaseMouseCapture();if(changed)PointsChanged?.Invoke(this,EventArgs.Empty);
    }
    protected override void OnMouseWheel(MouseWheelEventArgs e)
    {
        if(image is null)return;Point anchor=e.GetPosition(this);var before=Original(anchor);double next=Math.Clamp(zoom*(e.Delta>0?1.2:1/1.2),1,16);zoom=next;
        if(before is not null){var after=Screen(before);pan+=anchor-after;}InvalidateVisual();e.Handled=true;
    }
    protected override void OnRenderSizeChanged(SizeChangedInfo sizeInfo){base.OnRenderSizeChanged(sizeInfo);InvalidateVisual();}
}
