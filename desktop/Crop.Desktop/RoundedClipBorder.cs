using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace Crop.Desktop;

public sealed class RoundedClipBorder : Border
{
    protected override void OnRenderSizeChanged(SizeChangedInfo sizeInfo)
    {
        base.OnRenderSizeChanged(sizeInfo);
        double radius = CornerRadius.TopLeft;
        var bounds = new RectangleGeometry(new Rect(sizeInfo.NewSize), radius, radius);
        bounds.Freeze();
        Clip = bounds;
    }
}
