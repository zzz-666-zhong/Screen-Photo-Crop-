using System.Globalization;
using System.Windows;
using System.Windows.Controls;
using Crop.Core;

namespace Crop.Desktop;

internal sealed class OutputSettingsWindow : Window
{
    private readonly TextBox size;
    private readonly TextBox jpeg;
    private readonly TextBox png;
    private readonly TextBox name;
    private readonly ComboBox format;
    private readonly ComboBox detection;
    private readonly CheckBox folders;
    private readonly CheckBox depth;
    private readonly TextBlock error;
    public CropOptions Options { get; private set; }

    public OutputSettingsWindow(CropOptions existing)
    {
        Options = existing;
        Title = UiText.Text("高级输出与检测设置");
        Width = 540;
        SizeToContent = SizeToContent.Height;
        WindowStartupLocation = WindowStartupLocation.CenterOwner;
        ResizeMode = ResizeMode.NoResize;
        Style = (Style)FindResource("WindowTypography");
        var panel = new StackPanel { Margin = new Thickness(18) };
        size = Field(existing.OutputSize);
        jpeg = Field(existing.JpegQuality);
        png = Field(existing.PngCompression);
        name = new TextBox { Text = existing.NameTemplate };
        format = new ComboBox { ItemsSource = new[] { UiText.Text("PNG 无损"), "JPEG" }, SelectedIndex = (int)existing.Format };
        detection = new ComboBox { ItemsSource = new[] { UiText.Text("标准"), UiText.Text("扩展搜索（贴边、近拍、大角度）") }, SelectedIndex = (int)existing.Detection };
        folders = new CheckBox { Content = UiText.Text("保留原有子目录"), IsChecked = existing.KeepFolders, Margin = new Thickness(0, 7, 0, 6) };
        depth = new CheckBox { Content = UiText.Text("PNG 保留 16 位输入的位深"), IsChecked = existing.PreserveDepth, Margin = new Thickness(0, 0, 0, 9) };
        format.SelectionChanged += (_, _) =>
        {
            depth.IsEnabled = format.SelectedIndex == 0;
            if (!depth.IsEnabled) depth.IsChecked = false;
        };
        depth.IsEnabled = format.SelectedIndex == 0;
        AddRow("检测模式", detection);
        AddRow("输出格式", format);
        AddRow("输出长边（0 保留尺寸）", size);
        AddRow("PNG 压缩（0–9）", png);
        AddRow("JPEG 质量（1–100）", jpeg);
        AddRow("命名模板", name);
        panel.Children.Add(new TextBlock { Text = UiText.Text("{name} 是文件名，{ext} 是原扩展名。输出扩展名自动添加。"),
            TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 2, 0, 7) });
        panel.Children.Add(folders);
        panel.Children.Add(depth);
        panel.Children.Add(new TextBlock { Text = UiText.Text("导出图会应用 EXIF 方向，并移除 EXIF 与 ICC 等元数据。像素按常规 RGB 解码，未进行 ICC 色彩转换。原照片仍保留原始元数据。"),
            Foreground = System.Windows.Media.Brushes.DimGray, TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 4, 0, 9) });
        error = new TextBlock { Foreground = System.Windows.Media.Brushes.Firebrick, TextWrapping = TextWrapping.Wrap };
        panel.Children.Add(error);
        var buttons = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Right,
            Margin = new Thickness(0, 10, 0, 0) };
        var confirm = new Button { Content = UiText.Text("应用"), IsDefault = true, Margin = new Thickness(0, 0, 8, 0) };
        confirm.Click += (_, _) => Commit();
        buttons.Children.Add(confirm);
        buttons.Children.Add(new Button { Content = UiText.Text("取消"), IsCancel = true });
        panel.Children.Add(buttons);
        Content = panel;

        void AddRow(string label, FrameworkElement control)
        {
            var grid = new Grid { Margin = new Thickness(0, 0, 0, 7) };
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(190) });
            grid.ColumnDefinitions.Add(new ColumnDefinition());
            grid.Children.Add(new Label { Content = UiText.Text(label), Target = control, VerticalAlignment = VerticalAlignment.Center });
            Grid.SetColumn(control, 1);
            grid.Children.Add(control);
            panel.Children.Add(grid);
        }
    }

    private static TextBox Field(int value) => new() { Text = value.ToString(CultureInfo.InvariantCulture) };

    private void Commit()
    {
        if (!int.TryParse(size.Text, out var length) || length is < 0 or > 12000 ||
            !int.TryParse(jpeg.Text, out var quality) || quality is < 1 or > 100 ||
            !int.TryParse(png.Text, out var compression) || compression is < 0 or > 9 ||
            string.IsNullOrWhiteSpace(name.Text))
        {
            error.Text = UiText.Text("请检查输出尺寸、质量和命名模板。");
            return;
        }
        Options = Options with { OutputSize = length, JpegQuality = quality, PngCompression = compression,
            NameTemplate = name.Text.Trim(), Format = (CropFileFormat)format.SelectedIndex,
            Detection = (DetectionMode)detection.SelectedIndex, KeepFolders = folders.IsChecked == true, PreserveDepth = depth.IsChecked == true };
        DialogResult = true;
    }
}
