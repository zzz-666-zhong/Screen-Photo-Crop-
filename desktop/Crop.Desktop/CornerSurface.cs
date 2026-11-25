using System.Windows;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using Crop.Core;
using Point = System.Windows.Point;

namespace Crop.Desktop;

public sealed class CornerSurface : FrameworkElement
{
    private sealed record Edit(PixelPoint[] Points, int Rotation);
    private readonly Stack<Edit> undo = new(), redo = new();
    private readonly List<PixelPoint> points = [];
    private BitmapSource? image;
    private int width, height, selected = -1, dragging = -1;
    private double zoom = 1;
    private Vector pan;
    private Point last;
    private bool panning, replacing;
    private Edit? beforeDrag;
    public IReadOnlyList<PixelPoint> Points => points;
    public bool IsInteracting => dragging >= 0 || panning;
    public int Rotation { get; private set; }
    public int SelectedCorner => selected;
    public bool Magnifier { get; private set; } = true;
    public event EventHandler? PointsChanged;

    public CornerSurface()
    {
        Focusable = true;
        ClipToBounds = true;
        Cursor = Cursors.Cross;
    }

    public void SetImage(BitmapSource bitmap, PixelPoint[]? corners, int originalWidth, int originalHeight, int rotation)
    {
        image = bitmap;
        width = originalWidth;
        height = originalHeight;
        points.Clear();
        if (corners is not null) points.AddRange(corners);
        Rotation = rotation;
        selected = points.Count > 0 ? 0 : -1;
        undo.Clear();
        redo.Clear();
        replacing = false;
        Fit();
    }

    public void SetPoints(IEnumerable<PixelPoint> corners)
    {
        var next = corners.ToArray();
        if (points.SequenceEqual(next)) return;
        Remember(Capture());
        points.Clear();
        points.AddRange(next);
        selected = points.Count > 0 ? 0 : -1;
        NotifyEdit();
    }

    public void Clear()
    {
        image = null;
        points.Clear();
        undo.Clear();
        redo.Clear();
        selected = dragging = -1;
        replacing = panning = false;
        Rotation = 0;
        InvalidateVisual();
    }

    public void Fit() { zoom = 1; pan = new(); InvalidateVisual(); }
    public void ToggleMagnifier() { Magnifier = !Magnifier; InvalidateVisual(); Focus(); }

    public bool ReplaceSelected()
    {
        if (image is null || selected < 0) return false;
        replacing = true;
        Focus();
        return true;
    }

    public void ResetCorners()
    {
        if (points.Count == 0) return;
        Remember(Capture());
        points.Clear();
        selected = -1;
        NotifyEdit();
        Focus();
    }

    public void Rotate()
    {
        if (image is null) return;
        Remember(Capture());
        Rotation = (Rotation + 90) % 360;
        NotifyEdit();
    }

    public void Undo()
    {
        if (undo.TryPop(out var edit))
        {
            redo.Push(Capture());
            Restore(edit);
        }
    }

    public void Redo()
    {
        if (redo.TryPop(out var edit))
        {
            undo.Push(Capture());
            Restore(edit);
        }
    }

    private Edit Capture() => new(points.ToArray(), Rotation);
    private void Remember(Edit edit) { undo.Push(edit); redo.Clear(); }
    private void Restore(Edit edit)
    {
        points.Clear();
        points.AddRange(edit.Points);
        Rotation = edit.Rotation;
        selected = points.Count == 0 ? -1 : Math.Clamp(selected, 0, points.Count - 1);
        NotifyEdit();
    }
    private void NotifyEdit()
    {
        replacing = false;
        InvalidateVisual();
        PointsChanged?.Invoke(this, EventArgs.Empty);
    }

    private (double Scale, double X, double Y) View()
    {
        if (image is null) return (1, 0, 0);
        double scale = Math.Min(Math.Max(1, ActualWidth - 52) / width, Math.Max(1, ActualHeight - 70) / height) * zoom;
        return (scale, (ActualWidth - width * scale) / 2 + pan.X, (ActualHeight - height * scale) / 2 + pan.Y);
    }
    private Point Screen(PixelPoint p) { var (s, x, y) = View(); return new(x + p.X * s, y + p.Y * s); }
    private PixelPoint? Original(Point p)
    {
        if (image is null) return null;
        var (s, x, y) = View();
        double px = (p.X - x) / s, py = (p.Y - y) / s;
        return px >= 0 && py >= 0 && px < width && py < height ? new(Math.Min(px, width - 1), Math.Min(py, height - 1)) : null;
    }

    protected override void OnRender(DrawingContext dc)
    {
        base.OnRender(dc);
        dc.DrawRectangle(new SolidColorBrush(Color.FromRgb(30, 38, 36)), null, new Rect(0, 0, ActualWidth, ActualHeight));
        if (image is null) return;
        var (scale, x, y) = View();
        dc.DrawImage(image, new Rect(x, y, width * scale, height * scale));
        if (points.Count > 1)
        {
            var geometry = new StreamGeometry();
            using (var context = geometry.Open())
            {
                context.BeginFigure(Screen(points[0]), points.Count == 4, points.Count == 4);
                context.PolyLineTo(points.Skip(1).Select(Screen).ToArray(), true, false);
            }
            dc.DrawGeometry(points.Count == 4 ? new SolidColorBrush(Color.FromArgb(18, 200, 230, 170)) : null,
                new Pen(new SolidColorBrush(Color.FromRgb(225, 239, 184)), 1.5), geometry);
        }
        for (int i = 0; i < points.Count; i++)
        {
            var p = Screen(points[i]);
            dc.DrawEllipse(new SolidColorBrush(Color.FromRgb(239, 190, 97)), new Pen(i == selected ? Brushes.White : Brushes.DarkSlateGray, 2),
                p, i == selected ? 8 : 6, i == selected ? 8 : 6);
            var text = new FormattedText((i + 1).ToString(), System.Globalization.CultureInfo.InvariantCulture, FlowDirection.LeftToRight,
                new Typeface("Segoe UI"), 12, Brushes.White, VisualTreeHelper.GetDpi(this).PixelsPerDip);
            dc.DrawText(text, new Point(p.X + 10, p.Y - 19));
        }
        if (Magnifier && selected >= 0 && ActualWidth >= 220 && ActualHeight >= 210)
            DrawMagnifier(dc, points[selected], scale);
    }

    private void DrawMagnifier(DrawingContext dc, PixelPoint point, double scale)
    {
        var clip = new Rect(ActualWidth - 116, 12, 104, 104);
        var center = new Point(clip.X + clip.Width / 2, clip.Y + clip.Height / 2);
        double detail = Math.Max(2, scale * 3);
        dc.PushClip(new RectangleGeometry(clip));
        dc.DrawRectangle(Brushes.DarkSlateGray, null, clip);
        dc.DrawImage(image!, new Rect(center.X - point.X * detail, center.Y - point.Y * detail, width * detail, height * detail));
        var cross = new Pen(Brushes.Gold, 1);
        dc.DrawLine(cross, new Point(center.X - 12, center.Y), new Point(center.X + 12, center.Y));
        dc.DrawLine(cross, new Point(center.X, center.Y - 12), new Point(center.X, center.Y + 12));
        dc.Pop();
        dc.DrawRectangle(null, new Pen(Brushes.White, 1), clip);
    }

    protected override void OnMouseDown(MouseButtonEventArgs e)
    {
        if (image is null) return;
        Focus();
        last = e.GetPosition(this);
        if (e.ChangedButton == MouseButton.Middle || (e.ChangedButton == MouseButton.Left && Keyboard.IsKeyDown(Key.Space)))
        {
            panning = true;
            CaptureMouse();
            e.Handled = true;
            return;
        }
        if (e.ChangedButton != MouseButton.Left) return;
        var original = Original(last);
        if (replacing && selected >= 0 && original is not null)
        {
            Remember(Capture());
            points[selected] = original;
            NotifyEdit();
            e.Handled = true;
            return;
        }
        for (int i = 0; i < points.Count; i++)
        {
            if ((Screen(points[i]) - last).Length >= 13) continue;
            selected = dragging = i;
            beforeDrag = Capture();
            CaptureMouse();
            InvalidateVisual();
            e.Handled = true;
            return;
        }
        if (original is null || points.Count == 4) return;
        Remember(Capture());
        points.Add(original);
        selected = points.Count - 1;
        NotifyEdit();
        e.Handled = true;
    }

    protected override void OnMouseMove(MouseEventArgs e)
    {
        var p = e.GetPosition(this);
        if (panning) { pan += p - last; last = p; InvalidateVisual(); return; }
        if (dragging >= 0 && Original(p) is PixelPoint original)
        {
            points[dragging] = original;
            InvalidateVisual();
        }
    }

    protected override void OnMouseUp(MouseButtonEventArgs e) => EndPointer();
    protected override void OnLostMouseCapture(MouseEventArgs e)
    {
        base.OnLostMouseCapture(e);
        EndPointer();
    }

    private void EndPointer()
    {
        dragging = -1;
        panning = false;
        var edit = beforeDrag;
        beforeDrag = null;
        if (IsMouseCaptured) ReleaseMouseCapture();
        if (edit is not null && !edit.Points.SequenceEqual(points))
        {
            Remember(edit);
            NotifyEdit();
        }
    }

    protected override void OnKeyDown(KeyEventArgs e)
    {
        base.OnKeyDown(e);
        if (image is null || selected < 0) return;
        if (e.Key == Key.Tab && Keyboard.Modifiers.HasFlag(ModifierKeys.Control))
        {
            selected = (selected + 1) % points.Count;
            InvalidateVisual();
            e.Handled = true;
            return;
        }
        (int dx, int dy) = e.Key switch { Key.Left => (-1, 0), Key.Right => (1, 0), Key.Up => (0, -1), Key.Down => (0, 1), _ => (0, 0) };
        if (dx == 0 && dy == 0) return;
        int step = Keyboard.Modifiers.HasFlag(ModifierKeys.Shift) ? 10 : 1;
        var old = points[selected];
        var next = new PixelPoint(Math.Clamp(old.X + dx * step, 0, width - 1), Math.Clamp(old.Y + dy * step, 0, height - 1));
        if (old != next)
        {
            Remember(Capture());
            points[selected] = next;
            NotifyEdit();
        }
        e.Handled = true;
    }

    protected override void OnMouseWheel(MouseWheelEventArgs e)
    {
        if (image is null) return;
        Point anchor = e.GetPosition(this);
        var before = Original(anchor);
        zoom = Math.Clamp(zoom * (e.Delta > 0 ? 1.2 : 1 / 1.2), 1, 16);
        if (before is not null) pan += anchor - Screen(before);
        InvalidateVisual();
        e.Handled = true;
    }
    protected override void OnRenderSizeChanged(SizeChangedInfo info) { base.OnRenderSizeChanged(info); InvalidateVisual(); }
}
